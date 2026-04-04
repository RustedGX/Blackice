import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '⬡' },
  { to: '/portfolio', label: 'Portfolio', icon: '◈' },
  { to: '/backtest', label: 'Backtesting', icon: '◷' },
  { to: '/history', label: 'Trade History', icon: '≡' },
]

export default function Sidebar() {
  return (
    <aside className="w-52 bg-surface-800 border-r border-surface-600 flex flex-col flex-shrink-0">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-surface-600">
        <div className="text-accent-blue font-bold text-lg tracking-widest">BLACKICE</div>
        <div className="text-gray-500 text-xs mt-0.5">AI Trading System</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded text-sm transition-colors',
                isActive
                  ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/30'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-surface-700',
              )
            }
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-surface-600">
        <div className="text-gray-600 text-xs">Paper Trading Mode</div>
        <div className="text-gray-600 text-xs">No real money</div>
      </div>
    </aside>
  )
}
