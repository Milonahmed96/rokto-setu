import axios from 'axios'

const BASE = 'http://localhost:8000'

// ── Auth ──────────────────────────────────────────────────────────────────────
export const register = (phone, blood_group) =>
  axios.post(`${BASE}/auth/register`, { phone, blood_group, notification_range: 'UPAZILA' })

export const verifyOtp = (phone, otp) =>
  axios.post(`${BASE}/auth/verify-otp`, { phone, otp })

// ── Requests ──────────────────────────────────────────────────────────────────
export const createRequest = (token, data) =>
  axios.post(`${BASE}/requests/create`, data, {
    headers: { Authorization: `Bearer ${token}` }
  })

// ── Forecast ──────────────────────────────────────────────────────────────────
export const getForecast = (token, districtId, divisionId = 1) =>
  axios.get(`${BASE}/forecast/district/${districtId}?division_id=${divisionId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })

export const getModelInfo = (token) =>
  axios.get(`${BASE}/forecast/model-info`, {
    headers: { Authorization: `Bearer ${token}` }
  })

// ── Anomaly ───────────────────────────────────────────────────────────────────
export const scoreRequest = (token, data) =>
  axios.post(`${BASE}/anomaly/score`, data, {
    headers: { Authorization: `Bearer ${token}` }
  })

export const getAnomalyInfo = (token) =>
  axios.get(`${BASE}/anomaly/model-info`, {
    headers: { Authorization: `Bearer ${token}` }
  })

// ── Health ────────────────────────────────────────────────────────────────────
export const getHealth = () =>
  axios.get(`${BASE}/health`)