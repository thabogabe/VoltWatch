import { useCallback, useEffect, useMemo, useState } from 'react'
import { USE_MOCK, fetchHealth, fetchReports, fetchTransformer, fetchTransformers } from './api.js'
import DetailPanel from './components/DetailPanel.jsx'
import PatrolBoard from './components/PatrolBoard.jsx'
import ReportChat from './components/ReportChat.jsx'
import TransformerMap from './components/TransformerMap.jsx'
import { RISK, RISK_ORDER } from './constants.js'

// Reports refresh on their own so the patrol board stays current.
const REPORT_REFRESH_MS = 30_000

export default function App() {
  const [health, setHealth] = useState(null)
  const [transformers, setTransformers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [hidden, setHidden] = useState(() => new Set()) // risk levels switched off
  const [selectedId, setSelectedId] = useState(null)
  const [fetched, setFetched] = useState({ id: null, data: null, error: null })
  const [detailVersion, setDetailVersion] = useState(0) // bump to re-fetch the open detail

  // Side panel: transformer details ('map'), the report assistant or the patrol board.
  // ?view=report opens the report assistant directly (e.g. from a QR code on a poster).
  const [view, setView] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('view')
    return requested === 'report' || requested === 'patrol' ? requested : 'map'
  })
  const [reports, setReports] = useState([])
  const [reportsLoading, setReportsLoading] = useState(true)
  const [focusedReportId, setFocusedReportId] = useState(null)
  const [picking, setPicking] = useState(false)
  const [pickedLocation, setPickedLocation] = useState(null)

  useEffect(() => {
    if (USE_MOCK) return
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'unreachable' }))
  }, [])

  const loadTransformers = useCallback(
    () =>
      fetchTransformers()
        .then(setTransformers)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false)),
    [],
  )

  const loadReports = useCallback(
    () =>
      fetchReports()
        .then(setReports)
        .catch(() => {}) // the map still works without reports
        .finally(() => setReportsLoading(false)),
    [],
  )

  useEffect(() => {
    loadTransformers()
    loadReports()
    const timer = setInterval(loadReports, REPORT_REFRESH_MS)
    return () => clearInterval(timer)
  }, [loadTransformers, loadReports])

  // After a report is sent or its status changes: refresh reports, counts and open detail.
  const refreshAfterReportChange = useCallback(() => {
    loadReports()
    loadTransformers()
    setDetailVersion((v) => v + 1)
  }, [loadReports, loadTransformers])

  // Load the history and forecast for the clicked transformer.
  useEffect(() => {
    if (!selectedId) return
    let ignore = false
    fetchTransformer(selectedId)
      .then((data) => !ignore && setFetched({ id: selectedId, data, error: null }))
      .catch((e) => !ignore && setFetched({ id: selectedId, data: null, error: e.message }))
    return () => {
      ignore = true
    }
  }, [selectedId, detailVersion])

  // Only use the fetched detail if it belongs to the transformer that is selected now.
  const current = fetched.id === selectedId ? fetched : null
  const detail = current?.data ?? null
  const detailError = current?.error ?? null
  const detailLoading = Boolean(selectedId) && current === null

  const counts = useMemo(() => {
    const c = { green: 0, amber: 0, red: 0 }
    for (const t of transformers) if (t.risk_level in c) c[t.risk_level]++
    return c
  }, [transformers])

  const visible = useMemo(
    () => transformers.filter((t) => !hidden.has(t.risk_level)),
    [transformers, hidden],
  )
  const allPoints = useMemo(() => transformers.map((t) => [t.lat, t.lon]), [transformers])
  const topRisk = useMemo(
    () => [...transformers].sort((a, b) => b.risk_score - a.risk_score).slice(0, 5),
    [transformers],
  )
  const selected = transformers.find((t) => t.id === selectedId) ?? null

  const selectTransformer = (id) => {
    setView('map')
    setSelectedId(id)
  }

  const openView = (next) => {
    setPicking(false)
    setPickedLocation(null)
    setView((current) => (current === next ? 'map' : next))
  }

  const openReport = (report) => {
    setView('patrol')
    setFocusedReportId(report.id)
  }

  const openReportCount = reports.length
  const urgentCount = reports.filter((r) => r.is_urgent && r.status === 'new').length

  const toggleLevel = (level) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(level)) next.delete(level)
      else next.add(level)
      return next
    })

  return (
    <div className="app">
      <header>
        <h1>VoltWatch · GridGuard</h1>

        <div className="chips" role="group" aria-label="Filter by risk level">
          {RISK_ORDER.map((level) => (
            <button
              key={level}
              type="button"
              className="chip"
              aria-pressed={!hidden.has(level)}
              onClick={() => toggleLevel(level)}
            >
              <span className="dot" style={{ background: RISK[level].color }} />
              {RISK[level].label} {counts[level]}
            </button>
          ))}
        </div>

        <nav className="actions" aria-label="Community">
          <button
            type="button"
            className={`action-btn report ${view === 'report' ? 'active' : ''}`}
            onClick={() => openView('report')}
          >
            📣 Report a problem
          </button>
          <button
            type="button"
            className={`action-btn ${view === 'patrol' ? 'active' : ''}`}
            onClick={() => openView('patrol')}
          >
            🛡️ Patrol board
            {openReportCount > 0 && (
              <span className={`count ${urgentCount > 0 ? 'urgent' : ''}`}>{openReportCount}</span>
            )}
          </button>
        </nav>

        <span className="status">
          {USE_MOCK ? (
            'Demo data'
          ) : (
            <>
              API: {health?.status ?? '…'}
              {health?.database && ` · DB: ${health.database}`}
            </>
          )}
        </span>
      </header>

      {error && (
        <div className="banner error" role="alert">
          Could not load transformers: {error}. Is the API running? To try the map without it, set{' '}
          <code>VITE_USE_MOCK=true</code> in <code>frontend/.env</code> and restart{' '}
          <code>npm run dev</code>.
        </div>
      )}

      <main>
        <div className="map-wrap">
          {loading && <div className="overlay">Loading transformers…</div>}
          {picking && <div className="map-banner">👆 Tap where the problem is</div>}
          <TransformerMap
            transformers={visible}
            allPoints={allPoints}
            selectedId={selectedId}
            onSelect={selectTransformer}
            reports={reports}
            focusedReportId={view === 'patrol' ? focusedReportId : null}
            onReportClick={openReport}
            picking={picking}
            pickedLocation={view === 'report' ? pickedLocation : null}
            onPick={(loc) => {
              setPickedLocation(loc)
              setPicking(false)
            }}
          />
        </div>
        <aside className="panel">
          {view === 'report' && (
            <ReportChat
              pickedLocation={pickedLocation}
              onPickStart={() => {
                setPickedLocation(null)
                setPicking(true)
              }}
              onPickCancel={() => {
                setPicking(false)
                setPickedLocation(null)
              }}
              onSubmitted={refreshAfterReportChange}
              onClose={() => openView('map')}
            />
          )}
          {view === 'patrol' && (
            <PatrolBoard
              reports={reports}
              loading={reportsLoading}
              onChanged={refreshAfterReportChange}
              onFocus={(r) => setFocusedReportId(r.id)}
              focusedId={focusedReportId}
              onClose={() => openView('map')}
            />
          )}
          {view === 'map' && (
            <DetailPanel
              summary={selected}
              detail={detail}
              loading={detailLoading}
              error={detailError}
              topRisk={topRisk}
              onSelect={selectTransformer}
              onClose={() => setSelectedId(null)}
              onReport={() => openView('report')}
              onOpenReport={openReport}
            />
          )}
        </aside>
      </main>
    </div>
  )
}
