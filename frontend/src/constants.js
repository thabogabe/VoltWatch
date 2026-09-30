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

// Community report categories (must match REPORT_CATEGORIES in backend/app/models.py).
// `keywords` let the report assistant recognise a problem typed in the resident's own words.
// `safety` is shown straight away for anything that can hurt someone.
export const REPORT_TYPES = {
  outage: {
    label: 'Power outage or fault',
    emoji: '⚡',
    color: '#0f62c9',
    keywords: ['no power', 'no electricity', 'outage', 'blackout', 'dark', 'off', 'fault', 'trip', 'down'],
  },
  cable_theft: {
    label: 'Stolen or cut cables',
    emoji: '✂️',
    color: '#7c3aed',
    keywords: ['stolen', 'steal', 'theft', 'thief', 'thieves', 'cut', 'cable', 'copper', 'digging'],
    safety:
      'Do not approach or confront anyone. If it is happening now, call SAPS on 10111 (or 112 from a mobile).',
  },
  exposed_wiring: {
    label: 'Exposed or dangerous wiring',
    emoji: '⚠️',
    color: '#e8a317',
    keywords: ['exposed', 'hanging', 'loose', 'wire', 'wiring', 'illegal connection', 'izinyoka', 'low line', 'fallen'],
    safety:
      'Stay at least 10 metres away and keep children and animals back. Treat every wire as live, even if it looks dead.',
  },
  tampering: {
    label: 'Tampering with equipment',
    emoji: '🛠️',
    color: '#475569',
    keywords: ['tamper', 'open', 'broken', 'kiosk', 'meter', 'box', 'vandal', 'damaged'],
    safety: 'Do not touch the equipment. If people are tampering with it right now, call SAPS on 10111.',
  },
  sparking: {
    label: 'Sparks, fire or explosion',
    emoji: '🔥',
    color: '#d64545',
    keywords: ['spark', 'fire', 'smoke', 'burn', 'bang', 'explode', 'explosion', 'flame', 'buzzing'],
    safety:
      'Move away now and keep others back. If anything is burning or someone is hurt, call 112 (or 10177 for an ambulance).',
  },
}

export const REPORT_STATUS = {
  new: { label: 'New', color: '#d64545' },
  dispatched: { label: 'Patrol on the way', color: '#e8a317' },
  resolved: { label: 'Resolved', color: '#2e9e5b' },
}

// Best-guess report type from free text, or null when nothing matches.
export function guessReportType(text) {
  const t = text.toLowerCase()
  let best = null
  let bestHits = 0
  for (const [key, type] of Object.entries(REPORT_TYPES)) {
    const hits = type.keywords.filter((k) => t.includes(k)).length
    if (hits > bestHits) {
      best = key
      bestHits = hits
    }
  }
  return best
}

// "2026-10-01T08:15:00Z" -> "5 min ago"
export function timeAgo(iso) {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`
  return `${Math.floor(seconds / 86400)} d ago`
}
