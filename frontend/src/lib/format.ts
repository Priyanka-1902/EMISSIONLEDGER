const EUR_FORMATTER = new Intl.NumberFormat('en-IN', {
  style: 'decimal',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

const TCO2E_FORMATTER = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

export function formatTCO2e(val: number | undefined | null): string {
  if (val === undefined || val === null) return '—'
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `${(val / 1_000).toFixed(1)}k`
  return TCO2E_FORMATTER.format(val)
}

export function formatEUR(val: number | undefined | null): string {
  if (val === undefined || val === null) return '—'
  return EUR_FORMATTER.format(val)
}

export function formatPct(val: number | undefined | null): string {
  if (val === undefined || val === null) return '—'
  return val.toFixed(1)
}

export function formatDate(iso: string | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric'
  })
}
