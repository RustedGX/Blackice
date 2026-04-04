import { useEffect, useState } from 'react'
import { getTrades } from '../api/trades'
import { getSignal } from '../api/signals'
import type { Trade } from '../api/trades'
import type { Signal } from '../api/signals'
import Badge from '../components/common/Badge'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { clsx } from 'clsx'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

function SignalDetail({ signalId }: { signalId: number }) {
  const [signal, setSignal] = useState<Signal | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSignal(signalId).then(setSignal).finally(() => setLoading(false))
  }, [signalId])

  if (loading) return <div className="py-2"><LoadingSpinner size="sm" /></div>
  if (!signal) return <div className="text-gray-500 text-xs py-2">No signal data</div>

  const factors = signal.key_factors ? (JSON.parse(signal.key_factors) as string[]) : []

  return (
    <div className="bg-surface-900 rounded p-3 space-y-2 text-xs">
      <div className="flex items-center gap-2">
        <Badge value={signal.signal} size="sm" />
        <span className="text-gray-500">Confidence: {(signal.confidence * 100).toFixed(0)}%</span>
        <span className="text-gray-600">·</span>
        <Badge value={signal.risk_assessment} size="sm" />
        {signal.time_horizon && <span className="text-gray-500">{signal.time_horizon}</span>}
      </div>
      <div className="text-gray-300 leading-relaxed">{signal.reasoning}</div>
      {factors.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {factors.map((f, i) => (
            <span key={i} className="bg-surface-700 text-gray-400 px-2 py-0.5 rounded">{f}</span>
          ))}
        </div>
      )}
      <div className="grid grid-cols-3 gap-2 text-gray-500 pt-1 border-t border-surface-600">
        <div>Entry: {signal.suggested_entry ? fmt(signal.suggested_entry) : '—'}</div>
        <div>Stop: {signal.suggested_stop_loss ? fmt(signal.suggested_stop_loss) : '—'}</div>
        <div>Target: {signal.suggested_take_profit ? fmt(signal.suggested_take_profit) : '—'}</div>
      </div>
    </div>
  )
}

export default function TradeHistory() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [symbolFilter, setSymbolFilter] = useState('')
  const [sideFilter, setSideFilter] = useState('')

  useEffect(() => {
    getTrades({ limit: 100 })
      .then(setTrades)
      .finally(() => setLoading(false))
  }, [])

  const filtered = trades.filter((t) => {
    if (symbolFilter && !t.symbol.includes(symbolFilter.toUpperCase())) return false
    if (sideFilter && t.side !== sideFilter) return false
    return true
  })

  if (loading) {
    return <div className="flex justify-center pt-20"><LoadingSpinner size="lg" /></div>
  }

  return (
    <div className="space-y-4">
      <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="text-sm font-medium text-gray-300">Trade History</div>
          <div className="flex items-center gap-2">
            <input
              className="input-field text-sm w-28"
              placeholder="Symbol..."
              value={symbolFilter}
              onChange={(e) => setSymbolFilter(e.target.value)}
            />
            <select
              className="input-field text-sm"
              value={sideFilter}
              onChange={(e) => setSideFilter(e.target.value)}
            >
              <option value="">All sides</option>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="text-gray-500 text-sm text-center py-10">
            No trades yet. Place an order or use AI Auto-Trade on the Dashboard.
          </div>
        ) : (
          <div className="space-y-1">
            {filtered.map((t) => (
              <div key={t.id} className="bg-surface-700 rounded overflow-hidden">
                <div
                  className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-surface-600 transition-colors"
                  onClick={() => setExpanded(expanded === t.id ? null : t.id)}
                >
                  <div className="flex items-center gap-3">
                    <Badge value={t.side} size="sm" />
                    <span className="font-medium text-gray-100">{t.symbol}</span>
                    <span className="text-gray-400 text-sm">{t.quantity.toFixed(2)} @ {fmt(t.price)}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    {t.pnl !== null && (
                      <span className={clsx('text-sm font-medium', t.pnl >= 0 ? 'text-accent-green' : 'text-accent-red')}>
                        {fmt(t.pnl)}
                      </span>
                    )}
                    <span className="text-gray-500 text-xs">{t.executed_at.slice(0, 16).replace('T', ' ')}</span>
                    {t.signal_id && (
                      <span className="text-accent-blue text-xs">⚡ AI</span>
                    )}
                    <span className="text-gray-600 text-xs">{expanded === t.id ? '▲' : '▼'}</span>
                  </div>
                </div>
                {expanded === t.id && t.signal_id && (
                  <div className="px-4 pb-3">
                    <div className="text-xs text-gray-500 mb-1">AI Signal Reasoning</div>
                    <SignalDetail signalId={t.signal_id} />
                  </div>
                )}
                {expanded === t.id && !t.signal_id && (
                  <div className="px-4 pb-3 text-gray-500 text-xs">Manual order — no AI signal</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
