import { clsx } from 'clsx'

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  positive?: boolean | null
  className?: string
}

export default function StatCard({ label, value, sub, positive, className }: StatCardProps) {
  return (
    <div className={clsx('stat-card', className)}>
      <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">{label}</div>
      <div
        className={clsx(
          'text-xl font-semibold',
          positive === true
            ? 'text-accent-green'
            : positive === false
              ? 'text-accent-red'
              : 'text-gray-100',
        )}
      >
        {value}
      </div>
      {sub && <div className="text-gray-500 text-xs mt-0.5">{sub}</div>}
    </div>
  )
}
