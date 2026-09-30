import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fmtNumber, monthLabel } from '../constants.js'

// Energy supplied to the transformer vs energy billed to its customers, per month.
// The space between the lines is the loss (technical + unexplained).
export default function SuppliedBilledChart({ history }) {
  const data = history.map((h) => ({
    month: monthLabel(h.month),
    supplied: h.supplied_kwh,
    billed: h.billed_kwh,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e4e7eb" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis
          tick={{ fontSize: 11 }}
          width={44}
          tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
        />
        <Tooltip formatter={(v) => `${fmtNumber(v)} kWh`} />
        <Legend />
        <Line
          type="monotone"
          dataKey="supplied"
          name="Supplied"
          stroke="#2563eb"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="billed"
          name="Billed"
          stroke="#7c3aed"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
