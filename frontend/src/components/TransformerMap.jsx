import { useEffect } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { RISK } from '../constants.js'

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

export default function TransformerMap({ transformers, allPoints, selectedId, onSelect }) {
  const selected = transformers.find((t) => t.id === selectedId)

  return (
    <MapContainer className="map" center={DEFAULT_CENTER} zoom={13}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitToData points={allPoints} />

      {transformers.map((t) => (
        <CircleMarker
          key={t.id}
          center={[t.lat, t.lon]}
          radius={8}
          pathOptions={{
            color: '#ffffff',
            weight: 2,
            fillColor: RISK[t.risk_level]?.color ?? '#9aa5b1',
            fillOpacity: 0.9,
          }}
          eventHandlers={{ click: () => onSelect(t.id) }}
        >
          <Tooltip>
            {t.id} · {RISK[t.risk_level]?.label ?? 'Unknown'}
          </Tooltip>
        </CircleMarker>
      ))}

      {/* Ring around the selected transformer; not clickable so it never blocks the marker. */}
      {selected && (
        <CircleMarker
          center={[selected.lat, selected.lon]}
          radius={14}
          interactive={false}
          pathOptions={{ color: '#1f2933', weight: 3, fill: false }}
        />
      )}
    </MapContainer>
  )
}
