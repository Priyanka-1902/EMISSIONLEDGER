import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell
} from 'recharts'
import { TrendingDown, AlertTriangle, CheckCircle2, Euro, Leaf } from 'lucide-react'
import { api } from '../lib/api'
import { useTenantStore } from '../stores/tenant'
import { MetricCard } from '../components/dashboard/MetricCard'
import { ScopeBreakdown } from '../components/dashboard/ScopeBreakdown'
import { CBAMExposureWidget } from '../components/dashboard/CBAMExposureWidget'
import { HotspotList } from '../components/dashboard/HotspotList'
import { ComplianceStatus } from '../components/dashboard/ComplianceStatus'
import { formatTCO2e, formatEUR, formatPct } from '../lib/format'

const SCOPE_COLORS = {
  scope_1: '#ef4444',
  scope_2: '#f97316',
  scope_3: '#eab308',
}

export default function Dashboard() {
  const { t } = useTranslation()
  const { tenant } = useTenantStore()

  const { data: summary, isLoading } = useQuery({
    queryKey: ['dashboard-summary', tenant?.id],
    queryFn: () => api.get('/v1/dashboard/summary').then(r => r.data),
    enabled: !!tenant,
  })

  const { data: trend } = useQuery({
    queryKey: ['dashboard-trend', tenant?.id],
    queryFn: () => api.get('/v1/dashboard/trend?months=12').then(r => r.data),
    enabled: !!tenant,
  })

  const { data: hotspots } = useQuery({
    queryKey: ['dashboard-hotspots', tenant?.id],
    queryFn: () => api.get('/v1/dashboard/hotspots?limit=10').then(r => r.data),
    enabled: !!tenant,
  })

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-32 bg-gray-100 rounded-xl" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{t('dashboard.title')}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t('dashboard.subtitle', { period: summary?.reporting_period })}
        </p>
      </div>

      {/* Top-level metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title={t('dashboard.total_emissions')}
          value={formatTCO2e(summary?.total_tco2e)}
          unit="tCO₂e"
          trend={summary?.yoy_change_pct}
          icon={<Leaf className="h-5 w-5 text-green-600" />}
          color="green"
        />
        <MetricCard
          title={t('dashboard.cbam_exposure')}
          value={formatEUR(summary?.cbam_financial_exposure_eur)}
          unit="EUR"
          subtitle={t('dashboard.cbam_certificates', { count: summary?.cbam_certificates_required })}
          icon={<Euro className="h-5 w-5 text-blue-600" />}
          color="blue"
          highlight={summary?.cbam_financial_exposure_eur > 10000}
        />
        <MetricCard
          title={t('dashboard.data_completeness')}
          value={formatPct(summary?.data_completeness_pct)}
          unit="%"
          icon={
            summary?.data_completeness_pct >= 95
              ? <CheckCircle2 className="h-5 w-5 text-green-600" />
              : <AlertTriangle className="h-5 w-5 text-amber-500" />
          }
          color={summary?.data_completeness_pct >= 95 ? 'green' : 'amber'}
        />
        <MetricCard
          title={t('dashboard.emission_intensity')}
          value={summary?.intensity_per_revenue_tco2e_per_cr?.toFixed(2)}
          unit="tCO₂e/Cr Revenue"
          trend={summary?.intensity_yoy_change_pct}
          icon={<TrendingDown className="h-5 w-5 text-purple-600" />}
          color="purple"
        />
      </div>

      {/* Main charts row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* 12-month emissions trend */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-base font-medium text-gray-900 mb-4">
            {t('dashboard.emissions_trend')}
          </h2>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trend?.monthly || []}>
              <defs>
                <linearGradient id="s1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="s2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="s3" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#eab308" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#eab308" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} unit=" t" />
              <Tooltip formatter={(val: number) => [`${val.toFixed(1)} tCO₂e`]} />
              <Legend />
              <Area type="monotone" dataKey="scope_1" stroke="#ef4444" fill="url(#s1)" name="Scope 1" />
              <Area type="monotone" dataKey="scope_2" stroke="#f97316" fill="url(#s2)" name="Scope 2" />
              <Area type="monotone" dataKey="scope_3" stroke="#eab308" fill="url(#s3)" name="Scope 3" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Scope breakdown pie */}
        <ScopeBreakdown
          scope1={summary?.scope_1_tco2e}
          scope2={summary?.scope_2_tco2e}
          scope3={summary?.scope_3_tco2e}
        />
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Top 10 emission hotspots */}
        <div className="lg:col-span-2">
          <HotspotList hotspots={hotspots?.items || []} />
        </div>

        {/* Compliance status + CBAM deadlines */}
        <div className="space-y-4">
          <CBAMExposureWidget
            exposure_eur={summary?.cbam_financial_exposure_eur}
            certificates={summary?.cbam_certificates_required}
            next_deadline={summary?.cbam_next_deadline}
            certificate_price={summary?.cbam_certificate_price_eur}
          />
          <ComplianceStatus rules={summary?.compliance_status || []} />
        </div>
      </div>
    </div>
  )
}
