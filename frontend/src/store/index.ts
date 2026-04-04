import { create } from 'zustand'
import type { Portfolio, Position } from '../api/portfolio'
import type { Signal } from '../api/signals'

interface PortfolioState {
  portfolio: Portfolio | null
  setPortfolio: (p: Portfolio) => void
  updateBalances: (cash: number, total: number) => void
}

interface MarketState {
  prices: Record<string, number>
  updatePrice: (symbol: string, price: number) => void
  updatePrices: (updates: Record<string, number>) => void
}

interface SignalState {
  signals: Signal[]
  latestBySymbol: Record<string, Signal>
  addSignal: (s: Signal) => void
  setSignals: (signals: Signal[]) => void
}

interface WSState {
  connected: boolean
  setConnected: (v: boolean) => void
}

export const usePortfolioStore = create<PortfolioState>((set) => ({
  portfolio: null,
  setPortfolio: (p) => set({ portfolio: p }),
  updateBalances: (cash, total) =>
    set((state) =>
      state.portfolio
        ? { portfolio: { ...state.portfolio, cash_balance: cash, total_value: total } }
        : {}
    ),
}))

export const useMarketStore = create<MarketState>((set) => ({
  prices: {},
  updatePrice: (symbol, price) =>
    set((state) => ({ prices: { ...state.prices, [symbol]: price } })),
  updatePrices: (updates) =>
    set((state) => ({ prices: { ...state.prices, ...updates } })),
}))

export const useSignalStore = create<SignalState>((set) => ({
  signals: [],
  latestBySymbol: {},
  addSignal: (s) =>
    set((state) => ({
      signals: [s, ...state.signals].slice(0, 100),
      latestBySymbol: { ...state.latestBySymbol, [s.symbol]: s },
    })),
  setSignals: (signals) => {
    const latest: Record<string, Signal> = {}
    for (const s of signals) {
      if (!latest[s.symbol] || s.created_at > latest[s.symbol].created_at) {
        latest[s.symbol] = s
      }
    }
    set({ signals, latestBySymbol: latest })
  },
}))

export const useWSStore = create<WSState>((set) => ({
  connected: false,
  setConnected: (v) => set({ connected: v }),
}))
