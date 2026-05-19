import { AlertCircle, Calendar, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { formatEUR } from '../../lib/format'
import { differenceInDays, parseISO } from 'date-fns'
import { clsx } from 'clsx'

interface CBAMExposureWidgetProps {
  exposure_eur?: number
  certificates?: number
  next_deadline?: string  // ISO date
  certificate_price?: number
}

export function CBAMExposureWidget({
  exposure_eur, certificates, next_deadline, certificate_price
}: CBAMExposureWidgetProps) {
  const { t } = useTranslation()
  const daysUntilDeadline = next_deadline
    ? differenceInDays(parseISO(next_deadline), new Date())
    : null

  const urgency = daysUntilDeadline !== null
    ? daysUntilDeadline < 14 ? 'critical'
    : daysUntilDeadline < 30 ? 'warning'
    : 'ok'
    : 'ok'

  return (
    <div className={clsx(
      'rounded-xl border p-5',
      urgency === 'critical' ? 'border-red-200 bg-red-50'
      : urgency === 'warning' ? 'border-amber-200 bg-amber-50'
      : 'border-blue-100 bg-blue-50'
    )}>
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle className={clsx(
          'h-4 w-4',
          urgency === 'critical' ? 'text-red-600'
          : urgency === 'warning' ? 'text-amber-600'
          : 'text-blue-600'
        )} />
        <h3 className="text-sm font-semibold text-gray-800">CBAM Exposure</h3>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Financial Exposure</span>
          <span className="font-semibold text-gray-900">{formatEUR(exposure_eur)} EUR</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Certificates Required</span>
          <span className="font-semibold text-gray-900">{certificates?.toFixed(1) ?? '—'} tCO₂e</span>
        </div>
        {certificate_price && (
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Certificate Price</span>
            <span className="font-medium text-gray-700">€{certificate_price.toFixed(2)}/t</span>
          </div>
        )}
      </div>

      {daysUntilDeadline !== null && (
        <div className={clsx(
          'mt-3 flex items-center gap-2 rounded-lg px-3 py-2 text-xs',
          urgency === 'critical' ? 'bg-red-100 text-red-700'
          : urgency === 'warning' ? 'bg-amber-100 text-amber-700'
          : 'bg-blue-100 text-blue-700'
        )}>
          <Calendar className="h-3 w-3 flex-shrink-0" />
          <span>
            {daysUntilDeadline > 0
              ? `${daysUntilDeadline} days until Q deadline`
              : 'Deadline passed — submit now!'
            }
          </span>
        </div>
      )}

      <a
        href="/cbam"
        className="mt-3 flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
      >
        View CBAM Reports
        <ExternalLink className="h-3 w-3" />
      </a>
    </div>
  )
}
