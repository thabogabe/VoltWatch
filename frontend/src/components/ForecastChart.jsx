import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { monthLabel, nextMonth } from '../constants.js'

// Monthly peak load (kVA) with next month's forecast, against the transformer's
// capacity and the 90% "at risk" line.
export default function ForecastChart({ history, forecast, capacityKva }) {
  const peaks = history.filter((h) => h.peak_kva != null)
  if (peaks.length === 0 || !forecast) {
    return <p className="muted">No peak-load data available.</p>
  }

  const last = peaks[peaks.length - 1]
  const data = peaks.map((h) => ({ month: monthLabel(h.month), peak: h.peak_kva }))
  // Start the dashed forecast line from the last real peak so the two lines join up.
  data[data.length - 1].forecast = last.peak_kva
  data.push({
    month: monthLabel(forecast.month ?? nextMonth(last.month)),
    forecast: forecast.predicted_peak_kva,
  })

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e4e7eb" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis
          tick={{ fontSize: 11 }}
          width={44}
          domain={[0, (max) => Math.ceil(Math.max(max, capacityKva) * 1.1)]}
          tickFormatter={(v) => Math.round(v)}
        />
        <Tooltip formatter={(v) => `${Number(v).toFixed(1)} kVA`} />
        <Legend />
        <ReferenceLine
          y={capacityKva}
          stroke="#d64545"
          strokeWidth={2}
          label={{ value: 'Capacity', position: 'insideTopLeft', fontSize: 11, fill: '#d64545' }}
        />
        <ReferenceLine
          y={capacityKva * 0.9}
          stroke="#e8a317"
          strokeDasharray="4 3"
          label={{ value: '90%', position: 'insideBottomLeft', fontSize: 11, fill: '#b77b00' }}
        />
        <Line
          type="monotone"
          dataKey="peak"
          name="Monthly peak"
          stroke="#2563eb"
          strokeWidth={2}
          dot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="forecast"
          name="Forecast"
          stroke="#2563eb"
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={{ r: 4 }}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
