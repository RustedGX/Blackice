import client from './client'

export interface Position {
  id: number
  portfolio_id: number
  symbol: string
  quantity: number
  avg_entry_price: number
  current_price: number
  unrealized_pnl: number
  realized_pnl: number
  stop_loss: number | null
  take_profit: number | null
  opened_at: string
  updated_at: string
  market_value: number
  pnl_pct: number
}

export interface Portfolio {
  id: number
  name: string
  initial_balance: number
  cash_balance: number
  total_value: number
  positions: Position[]
  created_at: string
  updated_at: string
  total_pnl: number
  total_pnl_pct: number
}

export interface PerformancePoint {
  timestamp: string
  value: number
  drawdown: number
}

export interface Performance {
  equity_curve: PerformancePoint[]
  total_return: number
  total_return_pct: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  total_trades: number
  winning_trades: number
}

export const getPortfolio = () => client.get<Portfolio>('/portfolio').then((r) => r.data)
export const getPositions = () => client.get<Position[]>('/portfolio/positions').then((r) => r.data)
export const getPerformance = () => client.get<Performance>('/portfolio/performance').then((r) => r.data)
export const resetPortfolio = () => client.post('/portfolio/reset').then((r) => r.data)
export const setRiskControls = (positionId: number, stopLoss: number | null, takeProfit: number | null) =>
  client.post(`/portfolio/positions/${positionId}/controls`, { stop_loss: stopLoss, take_profit: takeProfit }).then((r) => r.data)
