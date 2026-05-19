import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { useTranslation } from 'react-i18next'
import { formatTCO2e } from '../../lib/format'

const SCOPE_COLORS = ['#ef4444', '#f97316', '#eab308']
const SCOPE_LABELS = ['Scope 1\n(Direct)', 'Scope 2\n(Electricity)', 'Scope 3\n(Value Chain)']

interface ScopeBreakdownProps {
  scope1?: number
  scope2?: number
  scope3?: number
}

export function ScopeBreakdown({ scope1 = 0, scope2 = 0, scope3 = 0 }: ScopeBreakdownProps) {
  const { t } = useTranslation()
  const total = scope1 + scope2 + scope3

  const data = [
    { name: 'Scope 1', value: scope1, label: 'Direct combustion' },
    { name: 'Scope 2', value: scope2, label: 'Purchased electricity' },
    { name: 'Scope 3', value: scope3, label: 'Value chain' },
  ].filter(d => d.value > 0)

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <h2 className="text-base font-medium text-gray-900 mb-4">Scope Breakdown</h2>

      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((_, index) => (
              <Cell key={index} fill={SCOPE_COLORS[index]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(val: number) => [`${formatTCO2e(val)} tCO₂e`]}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend with percentages */}
      <div className="mt-3 space-y-2">
        {data.map((item, i) => (
          <div key={item.name} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: SCOPE_COLORS[i] }}
              />
              <span className="text-gray-600">{item.name}</span>
            </div>
            <div className="text-right">
              <span className="font-medium text-gray-900">{formatTCO2e(item.value)} t</span>
              {total > 0 && (
                <span className="ml-1 text-xs text-gray-400">
                  ({((item.value / total) * 100).toFixed(0)}%)
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 border-t pt-3">
        <div className="flex justify-between text-sm font-semibold">
          <span className="text-gray-700">Total</span>
          <span className="text-gray-900">{formatTCO2e(total)} tCO₂e</span>
        </div>
      </div>
    </div>
  )
}
