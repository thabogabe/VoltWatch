import { useEffect, useMemo } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { REPORT_STATUS, REPORT_TYPES, RISK, timeAgo } from '../constants.js'

// Soweto, Johannesburg: default view for the synthetic township data
const DEFAULT_CENTER = [-26.2485, 27.854]

// Zoom to fit all transformers once they have loaded.
function FitToData({ points }) {
  const map = useMap()
  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(L.latLngBounds(points), { padding: [30, 30] })
    }
  }, [map, points])
  return null
}

// While reporting, a tap on the map sets the report location.
function PickLocation({ active, onPick }) {
  const map = useMapEvents({
    click: (e) => {
      if (active) onPick([e.latlng.lat, e.latlng.lng])
    },
  })
  useEffect(() => {
    map.getContainer().classList.toggle('picking', active)
  }, [map, active])
  return null
}

function FlyTo({ target }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo(target, Math.max(map.getZoom(), 16), { duration: 0.8 })
  }, [map, target])
  return null
}

function reportIcon(report, focused) {
  const type = REPORT_TYPES[report.category]
  const classes = ['report-pin', report.is_urgent && 'urgent', focused && 'focused'].filter(Boolean)
  return L.divIcon({
    className: '',
    html: `<div class="${classes.join(' ')}" style="--pin:${type?.color ?? '#475569'}"><span>${type?.emoji ?? '!'}</span></div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })
}

const pickedIcon = L.divIcon({
  className: '',
  html: '<div class="picked-pin">📍</div>',
  iconSize: [32, 32],
  iconAnchor: [16, 30],
})

export default function TransformerMap({
  transformers,
  allPoints,
  selectedId,
  onSelect,
  reports = [],
  focusedReportId = null,
  onReportClick,
  picking = false,
  pickedLocation = null,
  onPick,
}) {
  const selected = transformers.find((t) => t.id === selectedId)
  const focused = reports.find((r) => r.id === focusedReportId)
  const flyTarget = useMemo(() => (focused ? [focused.lat, focused.lon] : null), [focused])

  return (
    <MapContainer className="map" center={DEFAULT_CENTER} zoom={13}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitToData points={allPoints} />
      <PickLocation active={picking} onPick={onPick} />
      <FlyTo target={flyTarget} />

      {transformers.map((t) => (
        <CircleMarker
          // Re-created when picking starts/stops: Leaflet only reads `interactive` once,
          // and while picking a tap must reach the map instead of the marker.
          key={`${t.id}-${picking}`}
          center={[t.lat, t.lon]}
          radius={8}
          interactive={!picking}
          pathOptions={{
            color: '#ffffff',
            weight: 2,
            fillColor: RISK[t.risk_level]?.color ?? '#9aa5b1',
            fillOpacity: picking ? 0.55 : 0.9,
          }}
          eventHandlers={{ click: () => onSelect(t.id) }}
        >
          <Tooltip>
            {t.id} · {RISK[t.risk_level]?.label ?? 'Unknown'}
            {t.open_reports > 0 && ` · ${t.open_reports} report${t.open_reports > 1 ? 's' : ''}`}
          </Tooltip>
        </CircleMarker>
      ))}

      {/* Ring around the selected transformer; not clickable so it never blocks the marker. */}
      {selected && (
        <CircleMarker
          center={[selected.lat, selected.lon]}
          radius={14}
          interactive={false}
          pathOptions={{ color: '#04245a', weight: 3, fill: false }}
        />
      )}

      {!picking &&
        reports.map((r) => (
          <Marker
            key={r.id}
            position={[r.lat, r.lon]}
            icon={reportIcon(r, r.id === focusedReportId)}
            zIndexOffset={r.is_urgent ? 1000 : 500}
            eventHandlers={{ click: () => onReportClick?.(r) }}
          >
            <Tooltip direction="top" offset={[0, -14]}>
              {REPORT_TYPES[r.category]?.label ?? r.category} · {timeAgo(r.created_at)} ·{' '}
              {REPORT_STATUS[r.status]?.label}
            </Tooltip>
          </Marker>
        ))}

      {pickedLocation && <Marker position={pickedLocation} icon={pickedIcon} interactive={false} />}
    </MapContainer>
  )
}
