import { useEffect, useState } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { usePortfolioStore, useSignalStore } from '../store'
import { getPortfolio } from '../api/portfolio'
import { getOHLCV } from '../api/market'
import { getSignals, analyzeSymbol } from '../api/signals'
import type { Candle } from '../api/market'
import type { Signal } from '../api/signals'
import StatCard from '../components/common/StatCard'
import CandlestickChart from '../components/charts/CandlestickChart'
import SignalCard from '../components/trading/SignalCard'
import TradePanel from '../components/trading/TradePanel'
import PositionRow from '../components/trading/PositionRow'
import LoadingSpinner from '../components/common/LoadingSpinner'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`

const SYMBOLS = ['AAPL', 'TSLA', 'NVDA', 'SPY', 'BTC-USD', 'ETH-USD']

export default function Dashboard() {
  useWebSocket()
  const portfolio = usePortfolioStore((s) => s.portfolio)
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio)
  const signals = useSignalStore((s) => s.signals)
  const setSignals = useSignalStore((s) => s.setSignals)

  const [symbol, setSymbol] = useState('AAPL')
  const [candles, setCandles] = useState<Candle[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getPortfolio().then(setPortfolio).catch(console.error)
    getSignals({ limit: 20 }).then(setSignals).catch(console.error)
  }, [setPortfolio, setSignals])

  useEffect(() => {
    setChartLoading(true)
    setError('')
    getOHLCV(symbol)
      .then((r) => setCandles(r.candles))
      .catch((e) => setError(e.message))
      .finally(() => setChartLoading(false))
  }, [symbol])

  const handleAnalyze = async () => {
    setAnalyzing(true)
    try {
      const sig = await analyzeSymbol(symbol)
      setSignals([sig, ...signals].slice(0, 100))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  const pnl = portfolio?.total_pnl ?? 0
  const pnlPct = portfolio?.total_pnl_pct ?? 0

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Portfolio Value" value={fmt(portfolio?.total_value ?? 0)} />
        <StatCard label="Cash Balance" value={fmt(portfolio?.cash_balance ?? 0)} />
        <StatCard
          label="Total P&L"
          value={fmt(pnl)}
          sub={fmtPct(pnlPct)}
          positive={pnl >= 0}
        />
        <StatCard label="Open Positions" value={portfolio?.positions.length ?? 0} />
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Chart + signal feed */}
        <div className="xl:col-span-2 space-y-4">
          {/* Chart card */}
          <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <select
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="input-field text-sm"
                >
                  {SYMBOLS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <input
                  className="input-field text-sm w-24"
                  placeholder="Custom..."
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') setSymbol((e.target as HTMLInputElement).value.toUpperCase())
                  }}
                />
              </div>
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="btn-primary flex items-center gap-2 text-xs"
              >
                {analyzing ? <LoadingSpinner size="sm" /> : '⚡'}
                {analyzing ? 'Analyzing...' : 'AI Analyze'}
              </button>
            </div>
            {chartLoading ? (
              <div className="flex justify-center py-12"><LoadingSpinner /></div>
            ) : error ? (
              <div className="text-accent-red text-sm py-4 text-center">{error}</div>
            ) : (
              <CandlestickChart candles={candles} symbol={symbol} />
            )}
          </div>

          {/* Signal feed */}
          <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-300 mb-3 flex items-center justify-between">
              <span>AI Signal Feed</span>
              <span className="text-gray-500 text-xs">{signals.length} signals</span>
            </div>
            {signals.length === 0 ? (
              <div className="text-gray-500 text-sm text-center py-6">
                No signals yet. Click "AI Analyze" to generate a signal.
              </div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {signals.slice(0, 10).map((s) => (
                  <SignalCard key={s.id} signal={s} compact />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          <TradePanel />

          {/* Positions */}
          <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
            <div className="text-sm font-medium text-gray-300 mb-3">Open Positions</div>
            {!portfolio?.positions.length ? (
              <div className="text-gray-500 text-sm text-center py-4">No open positions</div>
            ) : (
              <div>
                {portfolio.positions.map((p) => (
                  <PositionRow key={p.id} position={p} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
