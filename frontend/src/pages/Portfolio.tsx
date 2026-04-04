import { useEffect, useState } from 'react'
import { getPerformance, getPositions, setRiskControls } from '../api/portfolio'
import type { Performance, Position } from '../api/portfolio'
import StatCard from '../components/common/StatCard'
import PortfolioChart from '../components/charts/PortfolioChart'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { clsx } from 'clsx'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`

function RiskControlModal({
  position,
  onClose,
  onSave,
}: {
  position: Position
  onClose: () => void
  onSave: () => void
}) {
  const [sl, setSl] = useState(String(position.stop_loss ?? ''))
  const [tp, setTp] = useState(String(position.take_profit ?? ''))
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await setRiskControls(position.id, sl ? Number(sl) : null, tp ? Number(tp) : null)
      onSave()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-surface-800 border border-surface-600 rounded-lg p-5 w-72 space-y-4">
        <div className="font-medium text-gray-100">Risk Controls — {position.symbol}</div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Stop Loss ($)</label>
          <input className="input-field w-full" value={sl} onChange={(e) => setSl(e.target.value)} placeholder="e.g. 150.00" />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Take Profit ($)</label>
          <input className="input-field w-full" value={tp} onChange={(e) => setTp(e.target.value)} placeholder="e.g. 200.00" />
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost flex-1" onClick={onClose}>Cancel</button>
          <button className="btn-primary flex-1" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Portfolio() {
  const [perf, setPerf] = useState<Performance | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [loading, setLoading] = useState(true)
  const [chartMode, setChartMode] = useState<'equity' | 'drawdown'>('equity')
  const [selected, setSelected] = useState<Position | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [p, pos] = await Promise.all([getPerformance(), getPositions()])
      setPerf(p)
      setPositions(pos)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) {
    return <div className="flex justify-center pt-20"><LoadingSpinner size="lg" /></div>
  }

  return (
    <div className="space-y-4">
      {selected && (
        <RiskControlModal position={selected} onClose={() => setSelected(null)} onSave={load} />
      )}

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Total Return"
          value={fmt(perf?.total_return ?? 0)}
          sub={fmtPct(perf?.total_return_pct ?? 0)}
          positive={(perf?.total_return ?? 0) >= 0}
        />
        <StatCard label="Max Drawdown" value={`${perf?.max_drawdown?.toFixed(2)}%`} positive={false} />
        <StatCard label="Sharpe Ratio" value={perf?.sharpe_ratio?.toFixed(3) ?? '—'} />
        <StatCard label="Win Rate" value={`${perf?.win_rate?.toFixed(1)}%`} sub={`${perf?.winning_trades}/${perf?.total_trades} trades`} />
      </div>

      {/* Equity chart */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium text-gray-300">Performance</div>
          <div className="flex gap-1">
            {(['equity', 'drawdown'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setChartMode(m)}
                className={clsx(
                  'px-3 py-1 rounded text-xs font-medium transition-colors',
                  chartMode === m ? 'bg-accent-blue text-white' : 'bg-surface-700 text-gray-400 hover:text-gray-200',
                )}
              >
                {m === 'equity' ? 'Equity Curve' : 'Drawdown'}
              </button>
            ))}
          </div>
        </div>
        <PortfolioChart data={perf?.equity_curve ?? []} mode={chartMode} />
      </div>

      {/* Positions table */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
        <div className="text-sm font-medium text-gray-300 mb-3">Open Positions</div>
        {positions.length === 0 ? (
          <div className="text-gray-500 text-sm text-center py-6">No open positions</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-surface-600">
                <th className="text-left pb-2">Symbol</th>
                <th className="text-right pb-2">Qty</th>
                <th className="text-right pb-2">Avg Entry</th>
                <th className="text-right pb-2">Current</th>
                <th className="text-right pb-2">Market Value</th>
                <th className="text-right pb-2">Unrealized P&L</th>
                <th className="text-right pb-2">Stop / Target</th>
                <th className="text-right pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.id} className="table-row text-gray-300">
                  <td className="py-2 font-medium text-gray-100">{p.symbol}</td>
                  <td className="py-2 text-right">{p.quantity.toFixed(2)}</td>
                  <td className="py-2 text-right">{fmt(p.avg_entry_price)}</td>
                  <td className="py-2 text-right">{fmt(p.current_price)}</td>
                  <td className="py-2 text-right">{fmt(p.market_value)}</td>
                  <td className={clsx('py-2 text-right font-medium', p.unrealized_pnl >= 0 ? 'text-accent-green' : 'text-accent-red')}>
                    {fmt(p.unrealized_pnl)} <span className="text-xs">({fmtPct(p.pnl_pct)})</span>
                  </td>
                  <td className="py-2 text-right text-xs">
                    <span className="text-accent-red">{p.stop_loss ? fmt(p.stop_loss) : '—'}</span>
                    {' / '}
                    <span className="text-accent-green">{p.take_profit ? fmt(p.take_profit) : '—'}</span>
                  </td>
                  <td className="py-2 text-right">
                    <button className="text-xs text-accent-blue hover:text-blue-400" onClick={() => setSelected(p)}>
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
