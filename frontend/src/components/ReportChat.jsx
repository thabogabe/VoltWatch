import { useEffect, useRef, useState } from 'react'
import { submitReport } from '../api.js'
import { REPORT_TYPES, guessReportType } from '../constants.js'

// Must match SERVICE_AREA in backend/app/reports.py.
const SERVICE_AREA = { lat: [-26.4, -26.1], lon: [27.7, 28.0] }
const inServiceArea = ([lat, lon]) =>
  lat >= SERVICE_AREA.lat[0] && lat <= SERVICE_AREA.lat[1] &&
  lon >= SERVICE_AREA.lon[0] && lon <= SERVICE_AREA.lon[1]

const GREETING =
  "Hi 👋 I'm the VoltWatch report assistant. Reports are anonymous and go straight to the " +
  'community patrol. What would you like to report?'

let nextId = 0
const bot = (text, extra = {}) => ({ id: nextId++, from: 'bot', text, ...extra })
const you = (text) => ({ id: nextId++, from: 'you', text })

/**
 * Guided chat for reporting a fault or crime. Steps:
 * type -> (safety advice) -> location -> urgent -> details -> confirm -> done
 *
 * The map is used to pick a location: while `step === 'location'` and the resident chose
 * "tap the map", `onPickStart` puts the map in picking mode and `pickedLocation` comes back.
 */
export default function ReportChat({ pickedLocation, onPickStart, onPickCancel, onSubmitted, onClose }) {
  const [messages, setMessages] = useState(() => [bot(GREETING)])
  const [step, setStep] = useState('type')
  const [draft, setDraft] = useState({ category: null, location: null, is_urgent: false, description: '' })
  const [text, setText] = useState('')
  const [guess, setGuess] = useState(null)
  const [busy, setBusy] = useState(false)
  const [picking, setPicking] = useState(false)
  const logRef = useRef(null)

  const say = (...msgs) => setMessages((m) => [...m, ...msgs])

  // Keep the newest message in view by scrolling the chat log only (not the whole page).
  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTo({ top: log.scrollHeight, behavior: 'smooth' })
  }, [messages, step])

  // A location tapped on the map while we are waiting for one.
  useEffect(() => {
    if (!picking || !pickedLocation) return
    setPicking(false)
    acceptLocation(pickedLocation, 'Tapped a spot on the map')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickedLocation])

  function chooseType(category, echo) {
    const type = REPORT_TYPES[category]
    setDraft((d) => ({ ...d, category }))
    setGuess(null)
    const msgs = [you(echo ?? `${type.emoji} ${type.label}`)]
    if (type.safety) msgs.push(bot(type.safety, { tone: 'danger', title: 'Stay safe' }))
    msgs.push(bot('Where is it? You can share your location or tap the spot on the map.'))
    say(...msgs)
    setStep('location')
  }

  function handleFreeText(e) {
    e.preventDefault()
    const value = text.trim()
    if (!value) return
    setText('')
    if (step === 'type') {
      const found = guessReportType(value)
      if (found) {
        setGuess(found)
        setDraft((d) => ({ ...d, description: value }))
        say(you(value), bot(`That sounds like ${REPORT_TYPES[found].emoji} ${REPORT_TYPES[found].label}. Is that right?`))
      } else {
        setDraft((d) => ({ ...d, description: value }))
        say(you(value), bot("Thanks. I couldn't tell which kind of problem that is. Please pick the closest one:"))
      }
    } else if (step === 'details') {
      finishDetails(value)
    }
  }

  function shareMyLocation() {
    if (!navigator.geolocation) {
      say(bot("Your browser can't share its location. Please tap the spot on the map instead."))
      return startPicking()
    }
    setBusy(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setBusy(false)
        const loc = [pos.coords.latitude, pos.coords.longitude]
        if (!inServiceArea(loc)) {
          say(
            you('📍 Shared my location'),
            bot("That location is outside the area VoltWatch covers. Please tap the spot on the map instead."),
          )
          return startPicking()
        }
        acceptLocation(loc, '📍 Shared my location')
      },
      () => {
        setBusy(false)
        say(bot("I couldn't get your location. Please tap the spot on the map instead."))
        startPicking()
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  function startPicking() {
    setPicking(true)
    onPickStart()
  }

  function acceptLocation(loc, echo) {
    if (!inServiceArea(loc)) {
      say(bot('That spot is outside the area VoltWatch covers. Please tap somewhere inside it.'))
      return startPicking()
    }
    setDraft((d) => ({ ...d, location: loc }))
    say(you(echo), bot('Is it happening right now?'))
    setStep('urgent')
  }

  function chooseUrgent(isUrgent) {
    setDraft((d) => ({ ...d, is_urgent: isUrgent }))
    say(
      you(isUrgent ? 'Yes, right now' : 'No, it already happened'),
      bot(
        draft.description
          ? 'Anything else the patrol should know, like a landmark? Please leave out names and phone numbers.'
          : 'Anything the patrol should know, like a landmark or what you saw? Please leave out names and phone numbers.',
      ),
    )
    setStep('details')
  }

  function finishDetails(value) {
    const description = [draft.description, value].filter(Boolean).join(' — ').slice(0, 500)
    setDraft((d) => ({ ...d, description }))
    say(you(value || 'Nothing to add'), bot('Here is your report. Shall I send it?'))
    setStep('confirm')
  }

  async function send() {
    setBusy(true)
    try {
      const saved = await submitReport({
        category: draft.category,
        lat: draft.location[0],
        lon: draft.location[1],
        is_urgent: draft.is_urgent,
        description: draft.description || null,
      })
      say(
        bot(
          `Sent ✅ Your reference is ${saved.id}. The community patrol can see it now` +
            (saved.transformer_id ? `, linked to transformer ${saved.transformer_id}.` : '.'),
          { tone: 'success', title: 'Report received', reference: saved.id },
        ),
      )
      setStep('done')
      onSubmitted(saved)
    } catch (err) {
      say(bot(`Sorry, that didn't go through (${err.message}). Please try again.`, { tone: 'danger' }))
    } finally {
      setBusy(false)
    }
  }

  function restart() {
    onPickCancel()
    setPicking(false)
    setGuess(null)
    setDraft({ category: null, location: null, is_urgent: false, description: '' })
    setMessages([bot(GREETING)])
    setStep('type')
  }

  const type = draft.category ? REPORT_TYPES[draft.category] : null

  return (
    <div className="chat">
      <div className="chat-head">
        <div className="chat-avatar" aria-hidden="true">⚡</div>
        <div>
          <h2>Report a problem</h2>
          <p className="muted">Anonymous · goes to the community patrol</p>
        </div>
        <button type="button" className="close" onClick={onClose} aria-label="Close report">
          ×
        </button>
      </div>

      <div className="chat-log" aria-live="polite" ref={logRef}>
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.from} ${m.tone ?? ''}`}>
            {m.title && <strong className="bubble-title">{m.title}</strong>}
            {m.text}
          </div>
        ))}

        {step === 'confirm' && type && (
          <div className="summary-card">
            <div className="summary-row">
              <span>{type.emoji}</span>
              <strong>{type.label}</strong>
            </div>
            <div className="summary-row muted">
              📍 {draft.location[0].toFixed(5)}, {draft.location[1].toFixed(5)}
            </div>
            <div className="summary-row muted">{draft.is_urgent ? '🚨 Happening now' : '🕒 Already happened'}</div>
            {draft.description && <div className="summary-row">“{draft.description}”</div>}
          </div>
        )}
      </div>

      <div className="chat-actions">
        {step === 'type' && guess && (
          <div className="options">
            <button type="button" className="option primary" onClick={() => chooseType(guess, 'Yes')}>
              Yes
            </button>
            <button type="button" className="option" onClick={() => setGuess(null)}>
              No, pick another
            </button>
          </div>
        )}
        {step === 'type' && !guess && (
          <div className="options grid">
            {Object.entries(REPORT_TYPES).map(([key, t]) => (
              <button key={key} type="button" className="option" onClick={() => chooseType(key)}>
                <span className="option-emoji">{t.emoji}</span>
                {t.label}
              </button>
            ))}
          </div>
        )}
        {step === 'location' && !picking && (
          <div className="options">
            <button type="button" className="option primary" onClick={shareMyLocation} disabled={busy}>
              {busy ? 'Finding you…' : '📍 Use my location'}
            </button>
            <button type="button" className="option" onClick={startPicking}>
              🗺️ Tap the map
            </button>
          </div>
        )}
        {step === 'location' && picking && (
          <div className="picking-hint">
            👆 Tap the spot on the map
            <button type="button" className="link" onClick={() => { setPicking(false); onPickCancel() }}>
              Cancel
            </button>
          </div>
        )}
        {step === 'urgent' && (
          <div className="options">
            <button type="button" className="option primary" onClick={() => chooseUrgent(true)}>
              🚨 Yes, right now
            </button>
            <button type="button" className="option" onClick={() => chooseUrgent(false)}>
              No, it already happened
            </button>
          </div>
        )}
        {step === 'details' && (
          <div className="options">
            <button type="button" className="option" onClick={() => finishDetails('')}>
              Skip
            </button>
          </div>
        )}
        {step === 'confirm' && (
          <div className="options">
            <button type="button" className="option primary" onClick={send} disabled={busy}>
              {busy ? 'Sending…' : 'Send report'}
            </button>
            <button type="button" className="option" onClick={restart} disabled={busy}>
              Start over
            </button>
          </div>
        )}
        {step === 'done' && (
          <div className="options">
            <button type="button" className="option primary" onClick={restart}>
              Report something else
            </button>
            <button type="button" className="option" onClick={onClose}>
              Back to the map
            </button>
          </div>
        )}

        {(step === 'type' || step === 'details') && (
          <form className="chat-input" onSubmit={handleFreeText}>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={300}
              placeholder={step === 'type' ? 'Or describe it in your own words…' : 'Type details…'}
              aria-label={step === 'type' ? 'Describe the problem' : 'Details for the patrol'}
            />
            <button type="submit" className="send" aria-label="Send" disabled={!text.trim()}>
              ➤
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
