import { useState } from 'react'
import { createIncident } from '../api'

const INCIDENT_TYPES = ['medical', 'fire', 'crime', 'other']

const SESSION_ID = `anon-${Math.random().toString(36).slice(2, 10)}`

export default function PanicButton({ onIncidentCreated }) {
  const [incidentType, setIncidentType] = useState('medical')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState('idle') // idle | locating | submitting | success | error
  const [errorMsg, setErrorMsg] = useState('')

  async function handlePanic() {
    setStatus('locating')
    setErrorMsg('')

    let latitude, longitude
    try {
      const position = await new Promise((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000 })
      )
      latitude = position.coords.latitude
      longitude = position.coords.longitude
    } catch {
      setStatus('error')
      setErrorMsg('Could not get location. Please allow location access and try again.')
      return
    }

    setStatus('submitting')
    try {
      const incident = await createIncident({
        incident_type: incidentType,
        description: description.trim() || null,
        latitude,
        longitude,
        caller_id: SESSION_ID,
      })
      setStatus('success')
      setDescription('')
      onIncidentCreated?.(incident)
      setTimeout(() => setStatus('idle'), 3000)
    } catch (err) {
      setStatus('error')
      setErrorMsg(err?.response?.data?.detail || 'Failed to submit incident.')
    }
  }

  const busy = status === 'locating' || status === 'submitting'

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Report an Emergency</h2>

      <label style={styles.label}>Incident Type</label>
      <select
        value={incidentType}
        onChange={(e) => setIncidentType(e.target.value)}
        disabled={busy}
        style={styles.select}
      >
        {INCIDENT_TYPES.map((t) => (
          <option key={t} value={t}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </option>
        ))}
      </select>

      <label style={styles.label}>Description (optional)</label>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        disabled={busy}
        placeholder="Additional details..."
        rows={3}
        style={styles.textarea}
      />

      <button onClick={handlePanic} disabled={busy} style={styles.button(busy, status)}>
        {status === 'locating' && 'Getting Location...'}
        {status === 'submitting' && 'Submitting...'}
        {status === 'success' && 'Incident Reported!'}
        {status === 'idle' && 'PANIC — Report Emergency'}
        {status === 'error' && 'PANIC — Report Emergency'}
      </button>

      {status === 'error' && <p style={styles.error}>{errorMsg}</p>}
      {status === 'success' && (
        <p style={styles.success}>Incident submitted and being triaged by AI.</p>
      )}
    </div>
  )
}

const styles = {
  container: {
    background: '#1a1a2e',
    border: '1px solid #e94560',
    borderRadius: 12,
    padding: '24px',
    maxWidth: 480,
    margin: '0 auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  heading: {
    color: '#e94560',
    margin: 0,
    fontSize: '1.2rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  label: {
    color: '#aaa',
    fontSize: '0.8rem',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  select: {
    padding: '10px',
    borderRadius: 6,
    border: '1px solid #444',
    background: '#16213e',
    color: '#fff',
    fontSize: '1rem',
  },
  textarea: {
    padding: '10px',
    borderRadius: 6,
    border: '1px solid #444',
    background: '#16213e',
    color: '#fff',
    fontSize: '0.95rem',
    resize: 'vertical',
  },
  button: (busy, status) => ({
    padding: '16px',
    borderRadius: 8,
    border: 'none',
    background: status === 'success' ? '#28a745' : busy ? '#555' : '#e94560',
    color: '#fff',
    fontSize: '1.1rem',
    fontWeight: 700,
    cursor: busy ? 'not-allowed' : 'pointer',
    textTransform: 'uppercase',
    letterSpacing: 2,
    marginTop: 8,
    transition: 'background 0.2s',
  }),
  error: { color: '#e94560', fontSize: '0.9rem', margin: 0 },
  success: { color: '#28a745', fontSize: '0.9rem', margin: 0 },
}
