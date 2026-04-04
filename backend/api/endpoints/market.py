from fastapi import APIRouter, Query, HTTPException

from backend.services.market_data import get_quote, get_ohlcv, ohlcv_to_list

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/quote/{symbol}")
async def get_symbol_quote(symbol: str):
    try:
        quote = await get_quote(symbol.upper())
        return quote
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {str(e)}")


@router.get("/ohlcv/{symbol}")
async def get_symbol_ohlcv(
    symbol: str,
    period: str = Query("3mo", description="yfinance period: 1d,5d,1mo,3mo,6mo,1y,2y,5y"),
    interval: str = Query("1d", description="yfinance interval: 1m,5m,15m,1h,1d,1wk"),
):
    try:
        df = await get_ohlcv(symbol.upper(), period=period, interval=interval)
        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "count": len(df),
            "candles": ohlcv_to_list(df),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {str(e)}")


@router.get("/search")
async def search_symbols(q: str = Query(..., min_length=1)):
    """Basic symbol search — returns the yfinance info for the given ticker."""
    import yfinance as yf
    try:
        ticker = yf.Ticker(q.upper())
        info = ticker.info
        if not info:
            return {"results": []}
        return {
            "results": [
                {
                    "symbol": q.upper(),
                    "name": info.get("longName") or info.get("shortName") or q.upper(),
                    "exchange": info.get("exchange"),
                    "currency": info.get("currency"),
                }
            ]
        }
    except Exception:
        return {"results": []}
