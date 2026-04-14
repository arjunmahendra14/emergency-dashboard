import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const PRIORITY_COLORS = {
  CRITICAL: '#e94560',
  HIGH:     '#ff9f43',
  MEDIUM:   '#28a745',
}

const PRIORITY_RADIUS = {
  CRITICAL: 10,
  HIGH:     8,
  MEDIUM:   6,
}

const TYPE_ICONS = {
  medical: '🏥',
  fire:    '🔥',
  crime:   '🚔',
  other:   '⚠️',
}

// Seattle center
const SEATTLE = [47.6062, -122.3321]

export default function MapView({ incidents, onResolve }) {
  const active = incidents.filter(
    (i) => i.status !== 'resolved' && i.latitude && i.longitude
  )

  return (
    <MapContainer
      center={SEATTLE}
      zoom={12}
      style={{ height: '100%', width: '100%' }}
      zoomControl={true}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
        subdomains="abcd"
        maxZoom={19}
      />

      {active.map((incident) => {
        const color = PRIORITY_COLORS[incident.priority] || '#888'
        const radius = PRIORITY_RADIUS[incident.priority] || 7

        return (
          <CircleMarker
            key={incident.id}
            center={[incident.latitude, incident.longitude]}
            radius={radius}
            pathOptions={{
              color: color,
              fillColor: color,
              fillOpacity: 0.85,
              weight: 2,
            }}
          >
            <Popup>
              <div style={popupStyles.container}>
                <div style={popupStyles.header}>
                  <span style={{ ...popupStyles.badge, background: color }}>
                    {incident.priority || 'UNKNOWN'}
                  </span>
                  <span style={popupStyles.type}>
                    {TYPE_ICONS[incident.incident_type]} {incident.incident_type}
                  </span>
                </div>
                <p style={popupStyles.summary}>
                  {incident.ai_summary || incident.description || 'No details'}
                </p>
                {incident.suggested_action && (
                  <p style={popupStyles.action}>{incident.suggested_action}</p>
                )}
                <button
                  style={popupStyles.resolveBtn}
                  onClick={() => onResolve(incident.id)}
                >
                  ✓ Resolve Incident
                </button>
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}

const popupStyles = {
  container: {
    minWidth: 220,
    maxWidth: 280,
    fontFamily: "'Segoe UI', system-ui, sans-serif",
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  badge: {
    color: '#fff',
    fontSize: '0.7rem',
    fontWeight: 700,
    padding: '2px 8px',
    borderRadius: 4,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  type: {
    fontSize: '0.85rem',
    fontWeight: 600,
    textTransform: 'capitalize',
  },
  summary: {
    fontSize: '0.85rem',
    margin: '0 0 6px',
    lineHeight: 1.4,
    color: '#333',
  },
  action: {
    fontSize: '0.8rem',
    margin: '0 0 10px',
    color: '#555',
    borderLeft: '3px solid #4fc3f7',
    paddingLeft: 8,
  },
  resolveBtn: {
    width: '100%',
    padding: '8px',
    background: '#28a745',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: '0.85rem',
    fontWeight: 700,
    cursor: 'pointer',
  },
}
