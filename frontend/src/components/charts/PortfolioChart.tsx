import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import type { PerformancePoint } from '../../api/portfolio'
import { format, parseISO } from 'date-fns'

interface Props {
  data: PerformancePoint[]
  mode?: 'equity' | 'drawdown'
}

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)

export default function PortfolioChart({ data, mode = 'equity' }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500 text-sm">
        No performance data yet
      </div>
    )
  }

  const chartData = data.map((pt) => ({
    date: pt.timestamp.slice(0, 10),
    value: mode === 'equity' ? pt.value : -pt.drawdown,
    raw: pt,
  }))

  const color = mode === 'equity' ? '#10b981' : '#ef4444'

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
        <XAxis
          dataKey="date"
          tick={{ fill: '#6b7280', fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => v.slice(5)}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: '#6b7280', fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => mode === 'equity' ? fmt(v) : `${v.toFixed(1)}%`}
          width={mode === 'equity' ? 75 : 45}
        />
        <Tooltip
          contentStyle={{ background: '#0f1629', border: '1px solid #1c2847', borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: '#9ca3af' }}
          formatter={(v: number) => [mode === 'equity' ? fmt(v) : `${(-v).toFixed(2)}%`, mode === 'equity' ? 'Value' : 'Drawdown']}
        />
        {mode === 'drawdown' && <ReferenceLine y={0} stroke="#374151" strokeDasharray="3 3" />}
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          dot={false}
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
