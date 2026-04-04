import type { Position } from '../../api/portfolio'
import { clsx } from 'clsx'

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`

interface Props {
  position: Position
}

export default function PositionRow({ position }: Props) {
  const pnlPositive = position.unrealized_pnl >= 0
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-surface-600 last:border-0 text-sm">
      <div className="flex-1">
        <span className="text-gray-100 font-medium">{position.symbol}</span>
        <span className="text-gray-500 ml-2 text-xs">{position.quantity.toFixed(2)} shares</span>
      </div>
      <div className="text-right">
        <div className="text-gray-300">{fmt(position.current_price)}</div>
        <div className="text-gray-500 text-xs">avg {fmt(position.avg_entry_price)}</div>
      </div>
      <div className="text-right ml-4 w-28">
        <div className={clsx('font-medium', pnlPositive ? 'text-accent-green' : 'text-accent-red')}>
          {fmt(position.unrealized_pnl)}
        </div>
        <div className={clsx('text-xs', pnlPositive ? 'text-accent-green' : 'text-accent-red')}>
          {fmtPct(position.pnl_pct)}
        </div>
      </div>
    </div>
  )
}
