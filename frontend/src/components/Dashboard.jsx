import IncidentCard from './IncidentCard'

export default function Dashboard({ incidents, lastUpdated }) {
  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.heading}>Live Incidents</h2>
        <div style={styles.meta}>
          {lastUpdated && (
            <span style={styles.updated}>
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <span style={styles.count}>{incidents.length} showing</span>
        </div>
      </div>

      {incidents.length === 0 && (
        <p style={styles.empty}>No incidents match the current filters.</p>
      )}

      <div style={styles.list}>
        {incidents.map((incident) => (
          <IncidentCard key={incident.id} incident={incident} />
        ))}
      </div>
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  heading: {
    color: '#4fc3f7',
    margin: 0,
    fontSize: '1.2rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  meta: {
    display: 'flex',
    gap: 12,
    alignItems: 'center',
  },
  updated: {
    color: '#666',
    fontSize: '0.8rem',
  },
  count: {
    color: '#888',
    fontSize: '0.8rem',
    background: '#1a1a2e',
    padding: '2px 8px',
    borderRadius: 4,
    border: '1px solid #333',
  },
  empty: {
    color: '#555',
    textAlign: 'center',
    padding: '40px 0',
    fontSize: '0.9rem',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
}
