import { useState, useEffect, useCallback } from 'react'
import MapView from './components/MapView'
import IncidentCard from './components/IncidentCard'
import { fetchIncidents, resolveIncident } from './api'

const POLL_INTERVAL_MS = 5000

const PRIORITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2 }

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [lastUpdated, setLastUpdated] = useState(null)
  const [selectedId, setSelectedId] = useState(null)

  const load = useCallback(async () => {
    try {
      const data = await fetchIncidents()
      setIncidents(data)
      setLastUpdated(new Date())
    } catch {
      // retry on next poll
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [load])

  async function handleResolve(incidentId) {
    // Optimistic update — mark resolved instantly in UI
    setIncidents((prev) =>
      prev.map((i) => (i.id === incidentId ? { ...i, status: 'resolved' } : i))
    )
    try {
      await resolveIncident(incidentId)
    } catch {
      // Roll back on failure
      load()
    }
  }

  const active = incidents.filter((i) => i.status !== 'resolved')
  const resolved = incidents.filter((i) => i.status === 'resolved')

  const sorted = [
    ...active.sort(
      (a, b) =>
        (PRIORITY_ORDER[a.priority] ?? 3) - (PRIORITY_ORDER[b.priority] ?? 3) ||
        new Date(b.timestamp) - new Date(a.timestamp)
    ),
    ...resolved,
  ]

  const criticalCount = active.filter((i) => i.priority === 'CRITICAL').length
  const highCount = active.filter((i) => i.priority === 'HIGH').length

  return (
    <div style={styles.root}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.logo}>
          <span style={styles.logoIcon}>🚨</span>
          <span style={styles.logoText}>Emergency Dispatch</span>
          <span style={styles.tagline}>Seattle 911 — Live</span>
        </div>
        <div style={styles.headerStats}>
          {criticalCount > 0 && (
            <span style={styles.statBadge('#e94560')}>
              {criticalCount} CRITICAL
            </span>
          )}
          {highCount > 0 && (
            <span style={styles.statBadge('#ff9f43')}>
              {highCount} HIGH
            </span>
          )}
          <span style={styles.activeCount}>{active.length} active</span>
          {lastUpdated && (
            <span style={styles.lastUpdated}>
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </header>

      {/* Body */}
      <div style={styles.body}>
        {/* Map — 65% */}
        <div style={styles.mapPane}>
          <MapView incidents={incidents} onResolve={handleResolve} selectedId={selectedId} onSelect={setSelectedId} />
        </div>

        {/* Incident list — 35% */}
        <div style={styles.listPane}>
          <div style={styles.listHeader}>
            <span style={styles.listTitle}>Live Incidents</span>
            <span style={styles.listCount}>{sorted.length} total</span>
          </div>

          {sorted.length === 0 && (
            <p style={styles.empty}>No incidents yet.</p>
          )}

          <div style={styles.list}>
            {sorted.map((incident) => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                onResolve={handleResolve}
                selected={incident.id === selectedId}
                onSelect={setSelectedId}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

const styles = {
  root: {
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    background: '#0a0a1a',
    color: '#e0e0e0',
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    overflow: 'hidden',
  },
  header: {
    background: '#0f0f2d',
    borderBottom: '1px solid #1a1a4a',
    padding: '10px 24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexShrink: 0,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  logoIcon: {
    fontSize: '1.3rem',
  },
  logoText: {
    color: '#e94560',
    fontWeight: 800,
    fontSize: '1.1rem',
    textTransform: 'uppercase',
    letterSpacing: 2,
  },
  tagline: {
    color: '#444',
    fontSize: '0.75rem',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginLeft: 4,
  },
  headerStats: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  statBadge: (color) => ({
    background: color,
    color: '#fff',
    fontSize: '0.7rem',
    fontWeight: 700,
    padding: '3px 10px',
    borderRadius: 4,
    textTransform: 'uppercase',
    letterSpacing: 1,
  }),
  activeCount: {
    color: '#4fc3f7',
    fontSize: '0.8rem',
    fontWeight: 600,
  },
  lastUpdated: {
    color: '#444',
    fontSize: '0.75rem',
  },
  body: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  mapPane: {
    flex: '0 0 65%',
    position: 'relative',
  },
  listPane: {
    flex: '0 0 35%',
    display: 'flex',
    flexDirection: 'column',
    borderLeft: '1px solid #1a1a4a',
    overflow: 'hidden',
  },
  listHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    borderBottom: '1px solid #1a1a4a',
    flexShrink: 0,
  },
  listTitle: {
    color: '#4fc3f7',
    fontSize: '0.85rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  listCount: {
    color: '#555',
    fontSize: '0.75rem',
    background: '#1a1a2e',
    padding: '2px 8px',
    borderRadius: 4,
    border: '1px solid #2a2a5a',
  },
  empty: {
    color: '#444',
    textAlign: 'center',
    padding: '40px 0',
    fontSize: '0.85rem',
  },
  list: {
    overflowY: 'auto',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    padding: '12px',
  },
}
