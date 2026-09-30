import { useState } from 'react'
import { updateReportStatus } from '../api.js'
import { REPORT_STATUS, REPORT_TYPES, timeAgo } from '../constants.js'

const CODE_KEY = 'voltwatch.patrolCode'

function readCode() {
  try {
    return sessionStorage.getItem(CODE_KEY) ?? ''
  } catch {
    return ''
  }
}

function saveCode(code) {
  try {
    if (code) sessionStorage.setItem(CODE_KEY, code)
    else sessionStorage.removeItem(CODE_KEY)
  } catch {
    // storage blocked: the code just isn't remembered
  }
}

/**
 * Board for community patrol officers: open reports (urgent first), with buttons to mark
 * them dispatched or resolved. Status changes need the shared patrol code.
 */
export default function PatrolBoard({ reports, loading, onChanged, onFocus, focusedId, onClose }) {
  const [code, setCode] = useState(readCode)
  const [codeInput, setCodeInput] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState(null)

  const counts = {
    urgent: reports.filter((r) => r.is_urgent).length,
    new: reports.filter((r) => r.status === 'new').length,
    dispatched: reports.filter((r) => r.status === 'dispatched').length,
  }

  async function setStatus(report, status) {
    setBusyId(report.id)
    setError(null)
    try {
      await updateReportStatus(report.id, status, code)
      onChanged()
    } catch (err) {
      if (err.status === 403) {
        setCode('')
        saveCode('')
        setError('That patrol code was not accepted. Please enter it again.')
      } else {
        setError(err.message)
      }
    } finally {
      setBusyId(null)
    }
  }

  function signIn(e) {
    e.preventDefault()
    const value = codeInput.trim()
    if (!value) return
    setCode(value)
    saveCode(value)
    setCodeInput('')
    setError(null)
  }

  return (
    <div className="panel-body">
      <div className="panel-head">
        <div>
          <h2>Patrol board</h2>
          <p className="muted">Open community reports from the last 30 days</p>
        </div>
        <button type="button" className="close" onClick={onClose} aria-label="Close patrol board">
          ×
        </button>
      </div>

      <div className="stats">
        <div className="stat">
          <div className="stat-value" style={{ color: '#d64545' }}>{counts.urgent}</div>
          <div className="stat-label">Urgent</div>
        </div>
        <div className="stat">
          <div className="stat-value">{counts.new}</div>
          <div className="stat-label">New</div>
        </div>
        <div className="stat">
          <div className="stat-value">{counts.dispatched}</div>
          <div className="stat-label">On the way</div>
        </div>
      </div>

      {code ? (
        <p className="muted signed-in">
          ✅ Patrol code entered
          <button type="button" className="link" onClick={() => { setCode(''); saveCode('') }}>
            Sign out
          </button>
        </p>
      ) : (
        <form className="code-form" onSubmit={signIn}>
          <input
            type="password"
            value={codeInput}
            onChange={(e) => setCodeInput(e.target.value)}
            placeholder="Patrol code to update reports"
            aria-label="Patrol code"
            autoComplete="off"
          />
          <button type="submit" className="option primary">Enter</button>
        </form>
      )}
      {error && <p className="error">{error}</p>}

      <h3>Reports</h3>
      {loading && <p className="muted">Loading reports…</p>}
      {!loading && reports.length === 0 && (
        <p className="muted">No open reports. Residents' reports will appear here as they come in.</p>
      )}

      <ul className="report-list">
        {reports.map((r) => {
          const type = REPORT_TYPES[r.category]
          const status = REPORT_STATUS[r.status]
          return (
            <li
              key={r.id}
              className={`report-card ${r.is_urgent ? 'urgent' : ''} ${focusedId === r.id ? 'focused' : ''}`}
            >
              <button type="button" className="report-main" onClick={() => onFocus(r)}>
                <span className="report-emoji" style={{ background: type?.color }}>{type?.emoji}</span>
                <span className="report-text">
                  <strong>{type?.label ?? r.category}</strong>
                  <span className="muted">
                    {timeAgo(r.created_at)} · #{r.id}
                    {r.transformer_id && ` · near ${r.transformer_id}`}
                  </span>
                  {r.description && <span className="report-desc">“{r.description}”</span>}
                </span>
              </button>
              <div className="report-foot">
                <span className="pill" style={{ background: status?.color }}>{status?.label}</span>
                {r.is_urgent && <span className="pill urgent-pill">Happening now</span>}
                <span className="report-buttons">
                  {r.status === 'new' && (
                    <button type="button" className="option small" disabled={!code || busyId === r.id}
                            onClick={() => setStatus(r, 'dispatched')}>
                      Dispatch
                    </button>
                  )}
                  <button type="button" className="option small primary" disabled={!code || busyId === r.id}
                          onClick={() => setStatus(r, 'resolved')}>
                    Resolve
                  </button>
                </span>
              </div>
            </li>
          )
        })}
      </ul>

      <p className="privacy">Reports are anonymous. No names or phone numbers are collected.</p>
    </div>
  )
}
