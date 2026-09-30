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
