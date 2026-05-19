import { TrendingDown, TrendingUp } from 'lucide-react'
import { clsx } from 'clsx'

interface MetricCardProps {
  title: string
  value: string | number | undefined
  unit?: string
  subtitle?: string
  trend?: number        // YoY % change; negative = improvement for emissions
  icon?: React.ReactNode
  color?: 'green' | 'blue' | 'amber' | 'red' | 'purple'
  highlight?: boolean   // draw attention (e.g. high CBAM exposure)
}

const COLOR_MAP = {
  green:  { bg: 'bg-green-50',  border: 'border-green-100',  text: 'text-green-700' },
  blue:   { bg: 'bg-blue-50',   border: 'border-blue-100',   text: 'text-blue-700' },
  amber:  { bg: 'bg-amber-50',  border: 'border-amber-100',  text: 'text-amber-700' },
  red:    { bg: 'bg-red-50',    border: 'border-red-100',    text: 'text-red-700' },
  purple: { bg: 'bg-purple-50', border: 'border-purple-100', text: 'text-purple-700' },
}

export function MetricCard({
  title, value, unit, subtitle, trend, icon, color = 'green', highlight
}: MetricCardProps) {
  const colors = COLOR_MAP[color]
  const isImprovement = trend !== undefined && trend < 0  // for emissions, decrease is good

  return (
    <div className={clsx(
      'rounded-xl border p-5 transition-shadow hover:shadow-md',
      colors.bg, colors.border,
      highlight && 'ring-2 ring-amber-400 ring-offset-1'
    )}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-gray-500 truncate">{title}</p>
          <div className="mt-1 flex items-baseline gap-1">
            <span className={clsx('text-2xl font-bold', colors.text)}>
              {value ?? '—'}
            </span>
            {unit && <span className="text-xs text-gray-500">{unit}</span>}
          </div>
          {subtitle && <p className="mt-1 text-xs text-gray-500">{subtitle}</p>}
          {trend !== undefined && (
            <div className={clsx(
              'mt-2 flex items-center gap-1 text-xs',
              isImprovement ? 'text-green-600' : 'text-red-500'
            )}>
              {isImprovement
                ? <TrendingDown className="h-3 w-3" />
                : <TrendingUp className="h-3 w-3" />
              }
              <span>{Math.abs(trend).toFixed(1)}% vs last year</span>
            </div>
          )}
        </div>
        {icon && (
          <div className={clsx('p-2 rounded-lg', colors.bg)}>
            {icon}
          </div>
        )}
      </div>
    </div>
  )
}
