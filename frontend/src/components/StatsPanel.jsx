const PRIORITY_COLORS = {
  CRITICAL: '#e94560',
  HIGH: '#ff9f43',
  MEDIUM: '#28a745',
}

const TYPE_ICONS = {
  medical: '🏥',
  fire: '🔥',
  crime: '🚔',
  other: '⚠️',
}

export default function StatsPanel({ incidents, filters, onFilterChange, lastUpdated }) {
  const total = incidents.length
  const criticalCount = incidents.filter((i) => i.priority === 'CRITICAL').length
  const highCount = incidents.filter((i) => i.priority === 'HIGH').length
  const mediumCount = incidents.filter((i) => i.priority === 'MEDIUM').length

  const typeCounts = ['medical', 'fire', 'crime', 'other'].map((type) => ({
    type,
    count: incidents.filter((i) => i.incident_type === type).length,
  }))

  function toggleFilter(key, value) {
    onFilterChange((prev) => ({
      ...prev,
      [key]: prev[key] === value ? null : value,
    }))
  }

  function clearFilters() {
    onFilterChange({ priority: null, type: null })
  }

  const hasActiveFilter = filters.priority || filters.type

  return (
    <div style={styles.container}>
      {/* Feed status */}
      <div style={styles.feedStatus}>
        <span style={styles.dot} />
        <span style={styles.feedLabel}>Seattle 911 Feed Live</span>
      </div>
      {lastUpdated && (
        <p style={styles.lastUpdated}>
          Last updated {lastUpdated.toLocaleTimeString()}
        </p>
      )}

      {/* Total */}
      <div style={styles.totalBox}>
        <span style={styles.totalNumber}>{total}</span>
        <span style={styles.totalLabel}>Active Incidents</span>
      </div>

      {/* Priority breakdown */}
      <div style={styles.section}>
        <p style={styles.sectionLabel}>Filter by Priority</p>
        {[
          { key: 'CRITICAL', count: criticalCount },
          { key: 'HIGH', count: highCount },
          { key: 'MEDIUM', count: mediumCount },
        ].map(({ key, count }) => (
          <button
            key={key}
            onClick={() => toggleFilter('priority', key)}
            style={styles.filterBtn(filters.priority === key, PRIORITY_COLORS[key])}
          >
            <span style={styles.filterBtnLabel}>{key}</span>
            <span style={styles.filterBtnCount}>{count}</span>
          </button>
        ))}
      </div>

      {/* Type breakdown */}
      <div style={styles.section}>
        <p style={styles.sectionLabel}>Filter by Type</p>
        {typeCounts.map(({ type, count }) => (
          <button
            key={type}
            onClick={() => toggleFilter('type', type)}
            style={styles.filterBtn(filters.type === type, '#4fc3f7')}
          >
            <span style={styles.filterBtnLabel}>
              {TYPE_ICONS[type]} {type.charAt(0).toUpperCase() + type.slice(1)}
            </span>
            <span style={styles.filterBtnCount}>{count}</span>
          </button>
        ))}
      </div>

      {hasActiveFilter && (
        <button onClick={clearFilters} style={styles.clearBtn}>
          Clear Filters
        </button>
      )}
    </div>
  )
}

const styles = {
  container: {
    background: '#1a1a2e',
    border: '1px solid #2a2a5a',
    borderRadius: 12,
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  feedStatus: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: '#28a745',
    boxShadow: '0 0 6px #28a745',
    animation: 'pulse 2s infinite',
    flexShrink: 0,
  },
  feedLabel: {
    color: '#28a745',
    fontSize: '0.8rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  lastUpdated: {
    color: '#555',
    fontSize: '0.75rem',
    margin: 0,
    marginTop: -8,
  },
  totalBox: {
    background: '#16213e',
    borderRadius: 8,
    padding: '16px',
    textAlign: 'center',
    border: '1px solid #2a2a5a',
  },
  totalNumber: {
    display: 'block',
    fontSize: '2.5rem',
    fontWeight: 800,
    color: '#4fc3f7',
    lineHeight: 1,
  },
  totalLabel: {
    display: 'block',
    color: '#888',
    fontSize: '0.75rem',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginTop: 4,
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  sectionLabel: {
    color: '#555',
    fontSize: '0.7rem',
    textTransform: 'uppercase',
    letterSpacing: 1,
    margin: 0,
  },
  filterBtn: (active, color) => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 14px',
    borderRadius: 6,
    border: `1px solid ${active ? color : '#2a2a5a'}`,
    background: active ? `${color}22` : '#16213e',
    color: active ? color : '#aaa',
    fontSize: '0.85rem',
    fontWeight: 600,
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'all 0.15s',
  }),
  filterBtnLabel: {
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  filterBtnCount: {
    background: '#0a0a1a',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: '0.8rem',
    fontWeight: 700,
  },
  clearBtn: {
    padding: '10px',
    borderRadius: 6,
    border: '1px solid #444',
    background: 'transparent',
    color: '#888',
    fontSize: '0.8rem',
    cursor: 'pointer',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
}
