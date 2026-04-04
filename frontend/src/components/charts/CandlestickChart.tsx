import { useEffect, useRef } from 'react'
import { createChart, CandlestickSeries, HistogramSeries, ColorType } from 'lightweight-charts'
import type { Candle } from '../../api/market'

interface Props {
  candles: Candle[]
  symbol: string
}

export default function CandlestickChart({ candles, symbol }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null)

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0f1629' },
        textColor: '#6b7280',
      },
      grid: {
        vertLines: { color: '#151e36' },
        horzLines: { color: '#151e36' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#1c2847' },
      timeScale: {
        borderColor: '#1c2847',
        timeVisible: true,
      },
      width: containerRef.current.clientWidth,
      height: 280,
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    })

    const volSeries = chart.addSeries(HistogramSeries, {
      color: '#3b82f6',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

    const ohlcData = candles.map((c) => ({
      time: c.time as number,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))

    const volData = candles.map((c) => ({
      time: c.time as number,
      value: c.volume,
      color: c.close >= c.open ? '#10b98140' : '#ef444440',
    }))

    candleSeries.setData(ohlcData)
    volSeries.setData(volData)
    chart.timeScale().fitContent()

    chartRef.current = chart

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
    }
  }, [candles])

  if (candles.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500 text-sm">
        No chart data for {symbol}
      </div>
    )
  }

  return <div ref={containerRef} className="w-full" />
}
