import { useEffect, useState } from 'react'
import { runBacktest, getBacktests, getBacktest, deleteBacktest } from '../api/backtest'
import type { Backtest } from '../api/backtest'
import PortfolioChart from '../components/charts/PortfolioChart'
import StatCard from '../components/common/StatCard'
import Badge from '../components/common/Badge'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { clsx } from 'clsx'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)

function BacktestResults({ bt }: { bt: Backtest }) {
  const equityCurve = bt.results_json
    ? (() => {
        try {
          const parsed = JSON.parse(bt.results_json)
          return (parsed.equity_curve as number[]).map((v, i) => ({
            timestamp: new Date(Date.now() - (parsed.equity_curve.length - i) * 86400000).toISOString(),
            value: v,
            drawdown: 0,
          }))
        } catch {
          return []
        }
      })()
    : []

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-gray-100 font-semibold">{bt.symbol}</span>
          <span className="text-gray-500 text-sm ml-2">{bt.start_date} → {bt.end_date}</span>
        </div>
        <Badge value={bt.status} />
      </div>

      {bt.status === 'COMPLETE' && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="Final Balance" value={fmt(bt.final_balance ?? 0)} />
            <StatCard
              label="Total Return"
              value={`${bt.total_return?.toFixed(2)}%`}
              positive={(bt.total_return ?? 0) >= 0}
            />
            <StatCard label="Max Drawdown" value={`${bt.max_drawdown?.toFixed(2)}%`} positive={false} />
            <StatCard label="Win Rate" value={`${bt.win_rate?.toFixed(1)}%`} sub={`${bt.winning_trades}/${bt.total_trades} trades`} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <StatCard label="Sharpe Ratio" value={bt.sharpe_ratio?.toFixed(3) ?? '—'} />
            <StatCard label="Total Trades" value={bt.total_trades ?? 0} />
          </div>
          {equityCurve.length > 0 && <PortfolioChart data={equityCurve} mode="equity" />}
        </>
      )}

      {bt.status === 'RUNNING' && (
        <div className="flex items-center gap-2 text-gray-400 text-sm">
          <LoadingSpinner size="sm" /> Running backtest...
        </div>
      )}

      {bt.status === 'FAILED' && (
        <div className="text-accent-red text-sm">{bt.error_message || 'Backtest failed'}</div>
      )}
    </div>
  )
}

export default function Backtesting() {
  const [backtests, setBacktests] = useState<Backtest[]>([])
  const [selected, setSelected] = useState<Backtest | null>(null)
  const [loading, setLoading] = useState(false)
  const [listLoading, setListLoading] = useState(true)

  // Form state
  const [symbol, setSymbol] = useState('AAPL')
  const [startDate, setStartDate] = useState('2023-01-01')
  const [endDate, setEndDate] = useState('2024-01-01')
  const [initialBalance, setInitialBalance] = useState('100000')
  const [maxPosPct, setMaxPosPct] = useState('0.20')
  const [nBars, setNBars] = useState('5')

  const loadList = async () => {
    setListLoading(true)
    const list = await getBacktests().catch(() => [])
    setBacktests(list)
    setListLoading(false)
  }

  useEffect(() => {
    loadList()
  }, [])

  // Poll running backtests
  useEffect(() => {
    const running = backtests.some((b) => b.status === 'RUNNING')
    if (!running) return
    const timer = setInterval(async () => {
      const updated = await Promise.all(
        backtests.map((b) => (b.status === 'RUNNING' ? getBacktest(b.id).catch(() => b) : Promise.resolve(b)))
      )
      setBacktests(updated)
      if (selected && selected.status === 'RUNNING') {
        const upd = updated.find((b) => b.id === selected.id)
        if (upd) setSelected(upd)
      }
    }, 5000)
    return () => clearInterval(timer)
  }, [backtests, selected])

  const handleRun = async () => {
    setLoading(true)
    try {
      const bt = await runBacktest({
        symbol: symbol.toUpperCase(),
        start_date: startDate,
        end_date: endDate,
        initial_balance: Number(initialBalance),
        max_position_pct: Number(maxPosPct),
        signal_every_n_bars: Number(nBars),
      })
      setBacktests([bt, ...backtests])
      setSelected(bt)
    } catch (e: any) {
      alert(`Backtest failed: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    await deleteBacktest(id).catch(console.error)
    setBacktests(backtests.filter((b) => b.id !== id))
    if (selected?.id === id) setSelected(null)
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Config form */}
        <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 space-y-3">
          <div className="text-sm font-medium text-gray-300">Backtest Configuration</div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Symbol</label>
            <input className="input-field w-full" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Start Date</label>
              <input type="date" className="input-field w-full" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">End Date</label>
              <input type="date" className="input-field w-full" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Initial Balance ($)</label>
            <input type="number" className="input-field w-full" value={initialBalance} onChange={(e) => setInitialBalance(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Max Position %</label>
              <input type="number" step="0.05" min="0.01" max="1" className="input-field w-full" value={maxPosPct} onChange={(e) => setMaxPosPct(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Signal Every N Bars</label>
              <input type="number" min="1" className="input-field w-full" value={nBars} onChange={(e) => setNBars(e.target.value)} />
            </div>
          </div>
          <div className="text-xs text-gray-600">
            Signals use Claude AI (claude-sonnet-4-6) with RSI/MACD fallback when rate-limited.
          </div>
          <button onClick={handleRun} disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2">
            {loading ? <LoadingSpinner size="sm" /> : null}
            {loading ? 'Starting...' : 'Run Backtest'}
          </button>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-4">
          {selected ? (
            <BacktestResults bt={selected} />
          ) : (
            <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 flex items-center justify-center h-32 text-gray-500 text-sm">
              Select a backtest or run a new one
            </div>
          )}
        </div>
      </div>

      {/* Backtest list */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
        <div className="text-sm font-medium text-gray-300 mb-3">Backtest History</div>
        {listLoading ? (
          <div className="flex justify-center py-4"><LoadingSpinner /></div>
        ) : backtests.length === 0 ? (
          <div className="text-gray-500 text-sm text-center py-6">No backtests yet</div>
        ) : (
          <div className="space-y-1">
            {backtests.map((bt) => (
              <div
                key={bt.id}
                className={clsx(
                  'flex items-center justify-between px-4 py-3 rounded cursor-pointer transition-colors',
                  selected?.id === bt.id ? 'bg-accent-blue/10 border border-accent-blue/30' : 'bg-surface-700 hover:bg-surface-600',
                )}
                onClick={() => setSelected(bt)}
              >
                <div className="flex items-center gap-3">
                  <Badge value={bt.status} size="sm" />
                  <span className="font-medium text-gray-100">{bt.symbol}</span>
                  <span className="text-gray-500 text-xs">{bt.start_date} → {bt.end_date}</span>
                </div>
                <div className="flex items-center gap-3">
                  {bt.total_return !== null && (
                    <span className={clsx('text-sm font-medium', (bt.total_return ?? 0) >= 0 ? 'text-accent-green' : 'text-accent-red')}>
                      {bt.total_return?.toFixed(2)}%
                    </span>
                  )}
                  <span className="text-gray-600 text-xs">{bt.created_at.slice(0, 10)}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(bt.id) }}
                    className="text-gray-600 hover:text-accent-red text-xs transition-colors"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
