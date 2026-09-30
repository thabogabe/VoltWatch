import { useEffect, useState } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Soweto, Johannesburg: default view for the synthetic township data
const DEFAULT_CENTER = [-26.2485, 27.854]

export default function App() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'unreachable' }))
  }, [])

  return (
    <div className="app">
      <header>
        <h1>VoltWatch · GridGuard</h1>
        <span className="status">
          API: {health?.status ?? '…'}
          {health?.database && ` · DB: ${health.database}`}
        </span>
      </header>
      <MapContainer className="map" center={DEFAULT_CENTER} zoom={13}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
      </MapContainer>
    </div>
  )
}
