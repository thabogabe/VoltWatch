export const RISK = {
  green: { label: 'Green', color: '#2e9e5b' },
  amber: { label: 'Amber', color: '#e8a317' },
  red: { label: 'Red', color: '#d64545' },
}

// Order used in the header chips and the "highest risk" list.
export const RISK_ORDER = ['red', 'amber', 'green']

export const fmtNumber = (v) => (v == null ? '–' : Math.round(v).toLocaleString('en-ZA'))

export const fmtPct = (fraction, digits = 1) =>
  fraction == null ? '–' : `${(fraction * 100).toFixed(digits)}%`

export const fmtScore = (v) => (v == null ? '–' : Number(v).toFixed(2))

// "2026-07-01" -> "Jul 26"
export const monthLabel = (iso) =>
  new Date(iso).toLocaleDateString('en-GB', { month: 'short', year: '2-digit', timeZone: 'UTC' })

// "2026-08-01" -> "2026-09-01"
export const nextMonth = (iso) => {
  const d = new Date(iso)
  d.setUTCMonth(d.getUTCMonth() + 1)
  return d.toISOString().slice(0, 10)
}
