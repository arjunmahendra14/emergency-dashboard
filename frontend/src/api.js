import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

export async function createIncident(payload) {
  const { data } = await api.post('/incident', payload)
  return data
}

export async function fetchIncidents(status = null, limit = 100) {
  const params = { limit }
  if (status) params.status = status
  const { data } = await api.get('/incidents', { params })
  return data
}

export async function fetchIncident(incidentId) {
  const { data } = await api.get(`/incident/${incidentId}`)
  return data
}

export async function resolveIncident(incidentId) {
  const { data } = await api.patch(`/incident/${incidentId}/resolve`)
  return data
}
