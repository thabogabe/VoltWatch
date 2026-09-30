/**
 * API client for the VoltWatch backend.
 *
 * The map expects these step 7 endpoints (field names follow backend/gridguard/risk.py,
 * forecast.py and the database columns):
 *
 * GET /transformers
 *   -> [{ id, lat, lon, capacity_kva, ward?,
 *         risk_level: "green" | "amber" | "red", risk_score,
 *         loss_score, overload_score, utilization_pct,
 *         driver: "loss" | "overload" | "both" | "none" }]
 *
 * GET /transformers/{id}
 *   -> everything above, plus
 *      customer_count?, indigent_count?          (counts only, never individual households)
 *      history: [{ month: "2026-07-01", supplied_kwh, billed_kwh,
 *                  unexplained_loss_pct?, peak_kva? }]        (oldest first)
 *      forecast: { month?, predicted_peak_kva, utilization_pct, at_risk }
 *
 * GET /summary is not needed by the map (it counts the /transformers list itself).
 *
 * Community reports: GET /reports, POST /reports, PATCH /reports/{id} (see below).
 *
 * Set VITE_USE_MOCK=true in frontend/.env to use built-in demo data instead.
 */

import { getMockTransformer, listMockTransformers } from './mockData.js'

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

async function get(path) {
  const response = await fetch(`${API_URL}${path}`)
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} for ${path}`)
  }
  return response.json()
}

export function fetchHealth() {
  return get('/health')
}

export function fetchTransformers() {
  return USE_MOCK ? listMockTransformers() : get('/transformers')
}

export function fetchTransformer(id) {
  return USE_MOCK ? getMockTransformer(id) : get(`/transformers/${encodeURIComponent(id)}`)
}

async function send(method, path, body, headers = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') detail = data.detail
      else if (Array.isArray(data.detail)) detail = data.detail.map((d) => d.msg).join('; ')
    } catch {
      // keep the status text
    }
    const error = new Error(detail)
    error.status = response.status
    throw error
  }
  return response.json()
}

// --- Community reports -------------------------------------------------------
// In mock mode reports live in memory so the flows can be tried without the API.
const mockReports = []
const mockCode = () =>
  Array.from({ length: 6 }, () => 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[Math.floor(Math.random() * 32)]).join('')

/** GET /reports -> open reports, urgent first. */
export function fetchReports() {
  if (USE_MOCK) return Promise.resolve(mockReports.filter((r) => r.status !== 'resolved'))
  return get('/reports')
}

/** POST /reports { category, lat, lon, is_urgent, description? } -> report with its reference id. */
export function submitReport(report) {
  if (USE_MOCK) {
    const row = { ...report, id: mockCode(), status: 'new', transformer_id: null,
                  created_at: new Date().toISOString(), updated_at: null }
    mockReports.unshift(row)
    return Promise.resolve(row)
  }
  return send('POST', '/reports', report)
}

/** PATCH /reports/{id} { status } with the patrol code. */
export function updateReportStatus(id, status, patrolCode) {
  if (USE_MOCK) {
    const row = mockReports.find((r) => r.id === id)
    Object.assign(row, { status, updated_at: new Date().toISOString() })
    return Promise.resolve(row)
  }
  return send('PATCH', `/reports/${encodeURIComponent(id)}`, { status }, { 'X-Patrol-Code': patrolCode })
}
