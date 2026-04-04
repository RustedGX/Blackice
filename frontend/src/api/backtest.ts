import client from './client'

export interface Backtest {
  id: number
  portfolio_id: number
  symbol: string
  start_date: string
  end_date: string
  initial_balance: number
  final_balance: number | null
  total_trades: number | null
  winning_trades: number | null
  max_drawdown: number | null
  sharpe_ratio: number | null
  total_return: number | null
  win_rate: number | null
  status: string
  error_message: string | null
  created_at: string
  completed_at: string | null
  results_json?: string | null
}

export const runBacktest = (params: {
  symbol: string
  start_date: string
  end_date: string
  initial_balance?: number
  signal_every_n_bars?: number
  max_position_pct?: number
}) => client.post<Backtest>('/backtest/run', params).then((r) => r.data)

export const getBacktests = () => client.get<Backtest[]>('/backtest').then((r) => r.data)

export const getBacktest = (id: number) => client.get<Backtest>(`/backtest/${id}`).then((r) => r.data)

export const deleteBacktest = (id: number) => client.delete(`/backtest/${id}`).then((r) => r.data)
