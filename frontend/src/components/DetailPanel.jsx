import { RISK, fmtNumber, fmtPct, fmtScore } from '../constants.js'
import ForecastChart from './ForecastChart.jsx'
import SuppliedBilledChart from './SuppliedBilledChart.jsx'

// A red or amber flag leads to support for the community, not to accusations or
// disconnections: loss -> regularisation queue, overload -> capacity work.
const ACTIONS = {
  loss: {
    title: 'Regularisation queue',
    body: 'Energy losses that cannot be explained by normal technical losses have persisted here. Plan a legal connection drive, prepaid meter installation and Free Basic Electricity registration.',
  },
  overload: {
    title: 'Capacity check',
    body: 'The forecast peak is close to or above capacity. Plan load balancing or an upgrade before the next peak to avoid an outage.',
  },
  both: {
    title: 'Regularisation queue and capacity check',
    body: 'Unexplained losses and a high forecast load. Regularise connections in the area and check capacity before the next peak.',
  },
  none: {
    title: 'No action needed',
    body: 'Losses and forecast load are within the normal range.',
  },
}

function RiskBadge({ level }) {
  const risk = RISK[level]
  return (
    <span className="badge" style={{ background: risk?.color ?? '#9aa5b1' }}>
      {risk?.label ?? 'Unknown'}
    </span>
  )
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

// Mean unexplained loss over the last 3 months that have it.
function recentUnexplained(history) {
  const values = history
    .map((h) => h.unexplained_loss_pct)
    .filter((v) => v != null)
    .slice(-3)
  if (values.length === 0) return null
  return values.reduce((a, b) => a + b, 0) / values.length
}

function EmptyState({ topRisk, onSelect }) {
  return (
    <div className="panel-body">
      <h2>Select a transformer</h2>
      <p className="muted">
        Click a marker on the map to see its supplied vs billed energy and its overload forecast.
      </p>
      {topRisk.length > 0 && (
        <>
          <h3>Highest risk</h3>
          <ul className="top-list">
            {topRisk.map((t) => (
              <li key={t.id}>
                <button type="button" onClick={() => onSelect(t.id)}>
                  <span className="dot" style={{ background: RISK[t.risk_level]?.color }} />
                  <span className="top-id">{t.id}</span>
                  <span className="muted">risk {fmtScore(t.risk_score)}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="privacy">Transformer-level view only. No household is identified.</p>
    </div>
  )
}

export default function DetailPanel({ summary, detail, loading, error, topRisk, onSelect, onClose }) {
  if (!summary) return <EmptyState topRisk={topRisk} onSelect={onSelect} />

  const t = detail ?? summary
  const action = ACTIONS[t.driver] ?? ACTIONS.none
  const mentionsLoss = t.driver === 'loss' || t.driver === 'both'
  const unexplained = detail ? recentUnexplained(detail.history) : null

  return (
    <div className="panel-body">
      <div className="panel-head">
        <div>
          <h2>{t.id}</h2>
          <p className="muted">
            {t.ward ? `${t.ward} · ` : ''}
            {fmtNumber(t.capacity_kva)} kVA
          </p>
        </div>
        <div className="panel-head-right">
          <RiskBadge level={t.risk_level} />
          <button type="button" className="close" onClick={onClose} aria-label="Close details">
            ×
          </button>
        </div>
      </div>

      <div className="stats">
        <Stat label="Risk score" value={fmtScore(t.risk_score)} />
        <Stat label="Loss score" value={fmtScore(t.loss_score)} />
        <Stat label="Overload score" value={fmtScore(t.overload_score)} />
      </div>

      <section className="action">
        <h3>{action.title}</h3>
        <p>{action.body}</p>
        {mentionsLoss && t.indigent_count != null && t.customer_count != null && (
          <p className="muted">
            {t.indigent_count} of {t.customer_count} connected households are flagged indigent
            (eligible for Free Basic Electricity).
          </p>
        )}
      </section>

      {loading && <p className="muted">Loading history…</p>}
      {error && <p className="error">Could not load details: {error}</p>}

      {detail && (
        <>
          <section>
            <h3>Supplied vs billed</h3>
            {unexplained != null && (
              <p className="muted">
                Unexplained loss, last 3 months: <strong>{fmtPct(unexplained)}</strong> of supplied
                energy
              </p>
            )}
            <SuppliedBilledChart history={detail.history} />
          </section>

          <section>
            <h3>Overload forecast</h3>
            {detail.forecast && (
              <p className="muted">
                Next month: <strong>{fmtNumber(detail.forecast.predicted_peak_kva)} kVA</strong> (
                <strong>{Number(detail.forecast.utilization_pct).toFixed(0)}%</strong> of capacity)
                {detail.forecast.at_risk && <span className="at-risk"> · at risk of overload</span>}
              </p>
            )}
            <ForecastChart
              history={detail.history}
              forecast={detail.forecast}
              capacityKva={detail.capacity_kva}
            />
          </section>
        </>
      )}

      <p className="privacy">Transformer-level view only. No household is identified.</p>
    </div>
  )
}
