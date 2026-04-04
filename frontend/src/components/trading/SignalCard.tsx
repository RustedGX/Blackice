import Badge from '../common/Badge'
import type { Signal } from '../../api/signals'
import { clsx } from 'clsx'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

interface Props {
  signal: Signal
  compact?: boolean
}

export default function SignalCard({ signal, compact = false }: Props) {
  const factors = signal.key_factors ? JSON.parse(signal.key_factors) as string[] : []

  return (
    <div
      className={clsx(
        'bg-surface-800 border rounded-lg',
        signal.signal === 'BUY'
          ? 'border-accent-green/30'
          : signal.signal === 'SELL'
            ? 'border-accent-red/30'
            : 'border-surface-600',
        compact ? 'p-3' : 'p-4',
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-gray-100 font-semibold">{signal.symbol}</span>
          <Badge value={signal.signal} />
          {signal.risk_assessment && <Badge value={signal.risk_assessment} size="sm" />}
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500">{signal.created_at.slice(0, 16).replace('T', ' ')}</div>
          <div className="text-xs text-gray-400">Conf: {(signal.confidence * 100).toFixed(0)}%</div>
        </div>
      </div>

      <div className="text-gray-300 text-xs mb-2 leading-relaxed line-clamp-3">{signal.reasoning}</div>

      {!compact && factors.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {factors.map((f, i) => (
            <span key={i} className="text-xs bg-surface-700 text-gray-400 px-2 py-0.5 rounded">
              {f}
            </span>
          ))}
        </div>
      )}

      {!compact && (
        <div className="grid grid-cols-3 gap-2 text-xs text-gray-500 border-t border-surface-600 pt-2 mt-2">
          <div>
            <span className="text-gray-600">Entry</span>
            <div>{signal.suggested_entry ? fmt(signal.suggested_entry) : '—'}</div>
          </div>
          <div>
            <span className="text-gray-600">Stop</span>
            <div className="text-accent-red">{signal.suggested_stop_loss ? fmt(signal.suggested_stop_loss) : '—'}</div>
          </div>
          <div>
            <span className="text-gray-600">Target</span>
            <div className="text-accent-green">{signal.suggested_take_profit ? fmt(signal.suggested_take_profit) : '—'}</div>
          </div>
        </div>
      )}

      <div className="mt-2 text-xs text-gray-600">
        @ {fmt(signal.price_at_signal)} · {signal.time_horizon ?? '—'}
      </div>
    </div>
  )
}
