const PRIORITY_STYLES = {
  CRITICAL: { background: '#e94560', color: '#fff' },
  HIGH:     { background: '#ff9f43', color: '#fff' },
  MEDIUM:   { background: '#28a745', color: '#fff' },
}

const STATUS_LABELS = {
  pending:       { label: 'Pending',       color: '#aaa' },
  triaged:       { label: 'Triaged',       color: '#4fc3f7' },
  triage_failed: { label: 'Triage Failed', color: '#e94560' },
  dispatched:    { label: 'Dispatched',    color: '#ff9f43' },
  resolved:      { label: 'Resolved',      color: '#28a745' },
}

const TYPE_ICONS = {
  medical: '🏥',
  fire:    '🔥',
  crime:   '🚔',
  other:   '⚠️',
}

function formatTime(isoString) {
  try { return new Date(isoString).toLocaleTimeString() }
  catch { return isoString }
}

export default function IncidentCard({ incident, onResolve }) {
  const {
    id, incident_type, description, latitude, longitude,
    timestamp, status, ai_summary, priority, suggested_action, confidence,
  } = incident

  const resolved = status === 'resolved'
  const priorityStyle = priority ? PRIORITY_STYLES[priority] : { background: '#555', color: '#fff' }
  const statusMeta = STATUS_LABELS[status] || { label: status, color: '#aaa' }
  const mapsUrl = `https://www.google.com/maps?q=${latitude},${longitude}`

  return (
    <div style={styles.card(resolved)}>
      <div style={styles.header}>
        <div style={styles.leftHeader}>
          {priority && (
            <span style={{ ...styles.badge, ...priorityStyle }}>{priority}</span>
          )}
          <span style={styles.typeLabel}>
            {TYPE_ICONS[incident_type]} {incident_type}
          </span>
        </div>
        <span style={{ ...styles.statusLabel, color: statusMeta.color }}>
          {statusMeta.label}
        </span>
      </div>

      <p style={styles.summary}>
        {ai_summary || description || 'No details'}
      </p>

      {suggested_action && !resolved && (
        <div style={styles.actionBox}>
          <p style={styles.actionText}>{suggested_action}</p>
        </div>
      )}

      <div style={styles.footer}>
        <div style={styles.meta}>
          <span>{formatTime(timestamp)}</span>
          {confidence != null && status === 'triaged' && (
            <span>{(confidence * 100).toFixed(0)}% conf</span>
          )}
          <a href={mapsUrl} target="_blank" rel="noopener noreferrer" style={styles.mapLink}>
            Map ↗
          </a>
        </div>

        {!resolved && (
          <button style={styles.resolveBtn} onClick={() => onResolve(id)}>
            ✓ Resolve
          </button>
        )}
      </div>
    </div>
  )
}

const styles = {
  card: (resolved) => ({
    background: resolved ? '#0f0f1a' : '#16213e',
    border: `1px solid ${resolved ? '#1a1a2e' : '#2a2a5a'}`,
    borderRadius: 8,
    padding: '12px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    opacity: resolved ? 0.5 : 1,
    transition: 'opacity 0.3s',
  }),
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  leftHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  badge: {
    padding: '2px 7px',
    borderRadius: 4,
    fontSize: '0.65rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: 1,
    flexShrink: 0,
  },
  typeLabel: {
    color: '#ccc',
    fontWeight: 600,
    fontSize: '0.85rem',
    textTransform: 'capitalize',
  },
  statusLabel: {
    fontSize: '0.7rem',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    flexShrink: 0,
  },
  summary: {
    color: '#ccc',
    margin: 0,
    fontSize: '0.82rem',
    lineHeight: 1.45,
  },
  actionBox: {
    background: '#0f3460',
    borderRadius: 4,
    padding: '7px 10px',
    borderLeft: '3px solid #4fc3f7',
  },
  actionText: {
    color: '#e0e0e0',
    margin: 0,
    fontSize: '0.78rem',
    lineHeight: 1.4,
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  meta: {
    display: 'flex',
    gap: 10,
    color: '#666',
    fontSize: '0.72rem',
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  mapLink: {
    color: '#4fc3f7',
    textDecoration: 'none',
    fontSize: '0.72rem',
  },
  resolveBtn: {
    padding: '5px 12px',
    borderRadius: 5,
    border: '1px solid #28a745',
    background: 'transparent',
    color: '#28a745',
    fontSize: '0.75rem',
    fontWeight: 700,
    cursor: 'pointer',
    flexShrink: 0,
    transition: 'all 0.15s',
  },
}
