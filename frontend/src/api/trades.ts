import client from './client'

export interface Trade {
  id: number
  portfolio_id: number
  symbol: string
  side: string
  quantity: number
  price: number
  total_value: number
  status: string
  signal_id: number | null
  pnl: number | null
  executed_at: string
}

export const getTrades = (params?: { limit?: number; offset?: number; symbol?: string }) =>
  client.get<Trade[]>('/trades', { params }).then((r) => r.data)

export const getTrade = (id: number) => client.get<Trade>(`/trades/${id}`).then((r) => r.data)

export const placeOrder = (order: { symbol: string; side: string; quantity: number; price?: number }) =>
  client.post<Trade>('/trades/order', order).then((r) => r.data)
