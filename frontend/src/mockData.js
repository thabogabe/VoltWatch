// Demo data so the map works before the step 7 API exists (VITE_USE_MOCK=true).
// Shapes match api.js; the scoring mirrors backend/gridguard/risk.py so the colours
// behave like the real thing. It is random-looking but deterministic (fixed seed).

function mulberry32(seed) {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const clip = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

// Piecewise-linear interpolation, clamped at both ends (like numpy.interp).
function interp(x, xs, ys) {
  if (x <= xs[0]) return ys[0]
  for (let i = 1; i < xs.length; i++) {
    if (x <= xs[i]) return ys[i - 1] + ((x - xs[i - 1]) / (xs[i] - xs[i - 1])) * (ys[i] - ys[i - 1])
  }
  return ys[ys.length - 1]
}

// 12 months ending Aug 2026, like the generator (Sep 2025 start, 365 days).
const MONTHS = Array.from({ length: 12 }, (_, i) =>
  new Date(Date.UTC(2025, 8 + i, 1)).toISOString().slice(0, 10),
)

function nextMonthIso(iso) {
  const d = new Date(iso)
  d.setUTCMonth(d.getUTCMonth() + 1)
  return d.toISOString().slice(0, 10)
}

function build() {
  const rand = mulberry32(2026)
  const uniform = (a, b) => a + (b - a) * rand()

  return Array.from({ length: 100 }, (_, i) => {
    const id = `TX_${String(i + 1).padStart(3, '0')}`
    const capacity = [50, 100, 200, 315][Math.floor(rand() * 4)]
    const illegal = rand() < 0.1
    const technical = uniform(0.05, 0.08)
    const customerCount = 20
    let indigentCount = 0
    for (let c = 0; c < customerCount; c++) if (rand() < 0.2) indigentCount++

    const loadFactor = rand() < 0.08 ? uniform(0.8, 0.95) : uniform(0.4, 0.78)
    const illegalShare = illegal ? uniform(0.3, 0.5) : 0

    const history = MONTHS.map((month) => {
      const m = Number(month.slice(5, 7))
      const season = 1 + 0.25 * Math.cos(((m - 7) * Math.PI) / 6) // winter (Jul) highest
      const billed = customerCount * uniform(230, 320) * season
      const supplied = (billed / (1 - technical)) * (1 + illegalShare)
      const lossPct = (supplied - billed) / supplied
      const winterBoost = 0.9 + (0.2 * (season - 0.75)) / 0.5
      return {
        month,
        supplied_kwh: Math.round(supplied),
        billed_kwh: Math.round(billed),
        unexplained_loss_pct: lossPct - technical,
        peak_kva: Math.round(capacity * loadFactor * winterBoost * uniform(0.97, 1.03) * 10) / 10,
      }
    })

    // Next-month forecast from the last two peaks, like forecast.py.
    const lastTwo = history.slice(-2)
    const predicted = ((lastTwo[0].peak_kva + lastTwo[1].peak_kva) / 2) * 1.05
    const utilization = (predicted / capacity) * 100

    // Persistent gap: 3+ consecutive months above 4%.
    let run = 0
    let longest = 0
    for (const h of history) {
      run = h.unexplained_loss_pct > 0.04 ? run + 1 : 0
      longest = Math.max(longest, run)
    }
    const meanGap = history.reduce((s, h) => s + h.unexplained_loss_pct, 0) / history.length
    const confirmed = longest >= 3

    const gapScore = clip(meanGap / 0.2, 0, 1)
    const lossScore = confirmed ? gapScore : gapScore * 0.5
    const overloadScore = interp(utilization, [60, 90, 100], [0, 0.7, 1])
    const riskScore = 1 - (1 - lossScore) * (1 - overloadScore)
    const riskLevel = riskScore >= 0.7 ? 'red' : riskScore >= 0.4 ? 'amber' : 'green'
    const lossHigh = lossScore >= 0.4
    const overHigh = overloadScore >= 0.4
    const driver = lossHigh && overHigh ? 'both' : lossHigh ? 'loss' : overHigh ? 'overload' : 'none'

    return {
      id,
      ward: `Ward ${10 + Math.floor(rand() * 20)}`,
      lat: uniform(-26.3, -26.2),
      lon: uniform(27.8, 27.9),
      capacity_kva: capacity,
      risk_level: riskLevel,
      risk_score: riskScore,
      loss_score: lossScore,
      overload_score: overloadScore,
      utilization_pct: Math.round(utilization * 100) / 100,
      driver,
      // detail-only fields
      customer_count: customerCount,
      indigent_count: indigentCount,
      history,
      forecast: {
        month: nextMonthIso(MONTHS[MONTHS.length - 1]),
        predicted_peak_kva: Math.round(predicted * 100) / 100,
        utilization_pct: Math.round(utilization * 100) / 100,
        at_risk: utilization > 90,
      },
    }
  })
}

const DATA = build()
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// /transformers: the list without the heavy per-transformer history.
export async function listMockTransformers() {
  await delay(150)
  return DATA.map(
    // eslint-disable-next-line no-unused-vars
    ({ history, forecast, customer_count, indigent_count, ...summary }) => summary,
  )
}

// /transformers/{id}: full detail.
export async function getMockTransformer(id) {
  await delay(150)
  const found = DATA.find((t) => t.id === id)
  if (!found) throw new Error(`404 Not Found for /transformers/${id}`)
  return found
}
