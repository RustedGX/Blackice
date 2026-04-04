import { clsx } from 'clsx'

interface BadgeProps {
  value: 'BUY' | 'SELL' | 'HOLD' | string
  size?: 'sm' | 'md'
}

export default function Badge({ value, size = 'md' }: BadgeProps) {
  const colorMap: Record<string, string> = {
    BUY: 'bg-accent-green/20 text-accent-green border-accent-green/40',
    SELL: 'bg-accent-red/20 text-accent-red border-accent-red/40',
    HOLD: 'bg-accent-amber/20 text-accent-amber border-accent-amber/40',
    FILLED: 'bg-accent-blue/20 text-accent-blue border-accent-blue/40',
    RUNNING: 'bg-accent-amber/20 text-accent-amber border-accent-amber/40',
    COMPLETE: 'bg-accent-green/20 text-accent-green border-accent-green/40',
    FAILED: 'bg-accent-red/20 text-accent-red border-accent-red/40',
    LOW: 'bg-accent-green/20 text-accent-green border-accent-green/40',
    MEDIUM: 'bg-accent-amber/20 text-accent-amber border-accent-amber/40',
    HIGH: 'bg-accent-red/20 text-accent-red border-accent-red/40',
  }
  const sizeClass = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-xs'
  const color = colorMap[value] ?? 'bg-gray-700 text-gray-300 border-gray-600'
  return (
    <span className={clsx('inline-flex border rounded font-medium tracking-wider', sizeClass, color)}>
      {value}
    </span>
  )
}
