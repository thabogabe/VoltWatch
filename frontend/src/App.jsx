import { useEffect, useMemo, useState } from 'react'
import { USE_MOCK, fetchHealth, fetchTransformer, fetchTransformers } from './api.js'
import DetailPanel from './components/DetailPanel.jsx'
import TransformerMap from './components/TransformerMap.jsx'
import { RISK, RISK_ORDER } from './constants.js'

export default function App() {
  const [health, setHealth] = useState(null)
  const [transformers, setTransformers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [hidden, setHidden] = useState(() => new Set()) // risk levels switched off
  const [selectedId, setSelectedId] = useState(null)
  const [fetched, setFetched] = useState({ id: null, data: null, error: null })

  useEffect(() => {
    if (USE_MOCK) return
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'unreachable' }))
  }, [])

  useEffect(() => {
    fetchTransformers()
      .then(setTransformers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

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
  }, [selectedId])

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
          <TransformerMap
            transformers={visible}
            allPoints={allPoints}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>
        <aside className="panel">
          <DetailPanel
            summary={selected}
            detail={detail}
            loading={detailLoading}
            error={detailError}
            topRisk={topRisk}
            onSelect={setSelectedId}
            onClose={() => setSelectedId(null)}
          />
        </aside>
      </main>
    </div>
  )
}
