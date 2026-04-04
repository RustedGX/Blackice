import client from './client'

export interface Quote {
  symbol: string
  current_price: number
  prev_close: number
  day_change: number
  day_change_pct: number
  volume: number
  market_cap: number | null
  fifty_two_week_high: number | null
  fifty_two_week_low: number | null
  avg_volume: number | null
  name: string
  currency: string
}

export interface Candle {
  time: number
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface OHLCVResponse {
  symbol: string
  period: string
  interval: string
  count: number
  candles: Candle[]
}

export const getQuote = (symbol: string) =>
  client.get<Quote>(`/market/quote/${symbol}`).then((r) => r.data)

export const getOHLCV = (symbol: string, period = '3mo', interval = '1d') =>
  client.get<OHLCVResponse>(`/market/ohlcv/${symbol}`, { params: { period, interval } }).then((r) => r.data)

export const searchSymbols = (q: string) =>
  client.get<{ results: { symbol: string; name: string }[] }>('/market/search', { params: { q } }).then((r) => r.data)
