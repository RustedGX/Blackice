import client from './client'

export interface Signal {
  id: number
  portfolio_id: number
  symbol: string
  signal: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  reasoning: string
  key_factors: string | null
  risk_assessment: string
  suggested_entry: number | null
  suggested_stop_loss: number | null
  suggested_take_profit: number | null
  suggested_position_size_pct: number | null
  time_horizon: string | null
  sentiment_score: number | null
  price_at_signal: number
  created_at: string
}

export const analyzeSymbol = (symbol: string, portfolioId = 1) =>
  client.post<Signal>('/signals/analyze', { symbol, portfolio_id: portfolioId }).then((r) => r.data)

export const autoTrade = (symbol: string, maxPositionPct = 0.1, portfolioId = 1) =>
  client.post('/signals/auto-trade', { symbol, max_position_pct: maxPositionPct, portfolio_id: portfolioId }).then((r) => r.data)

export const getSignals = (params?: { limit?: number; offset?: number; symbol?: string }) =>
  client.get<Signal[]>('/signals', { params }).then((r) => r.data)

export const getSignal = (id: number) => client.get<Signal>(`/signals/${id}`).then((r) => r.data)
