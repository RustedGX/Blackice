import { useEffect } from 'react'
import { usePortfolioStore, useWSStore } from '../../store'
import { getPortfolio } from '../../api/portfolio'
import { clsx } from 'clsx'

function fmt(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
}

function fmtPct(n: number) {
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

export default function TopBar() {
  const portfolio = usePortfolioStore((s) => s.portfolio)
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio)
  const connected = useWSStore((s) => s.connected)

  useEffect(() => {
    getPortfolio().then(setPortfolio).catch(console.error)
    const interval = setInterval(() => {
      getPortfolio().then(setPortfolio).catch(console.error)
    }, 30000)
    return () => clearInterval(interval)
  }, [setPortfolio])

  const pnl = portfolio?.total_pnl ?? 0
  const pnlPct = portfolio?.total_pnl_pct ?? 0

  return (
    <header className="bg-surface-800 border-b border-surface-600 px-4 py-2 flex items-center justify-between flex-shrink-0">
      <div className="flex items-center gap-6 text-sm">
        <div>
          <span className="text-gray-500 text-xs">Portfolio</span>
          <div className="text-gray-100 font-medium">{fmt(portfolio?.total_value ?? 0)}</div>
        </div>
        <div>
          <span className="text-gray-500 text-xs">Cash</span>
          <div className="text-gray-100">{fmt(portfolio?.cash_balance ?? 0)}</div>
        </div>
        <div>
          <span className="text-gray-500 text-xs">Total P&L</span>
          <div className={clsx('font-medium', pnl >= 0 ? 'text-accent-green' : 'text-accent-red')}>
            {fmt(pnl)} <span className="text-xs">({fmtPct(pnlPct)})</span>
          </div>
        </div>
        <div>
          <span className="text-gray-500 text-xs">Positions</span>
          <div className="text-gray-100">{portfolio?.positions.length ?? 0}</div>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        <div
          className={clsx(
            'w-2 h-2 rounded-full',
            connected ? 'bg-accent-green animate-pulse' : 'bg-accent-red',
          )}
        />
        <span className={connected ? 'text-accent-green' : 'text-gray-500'}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>
    </header>
  )
}
