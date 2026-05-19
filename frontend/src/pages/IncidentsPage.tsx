import { useState, useEffect } from 'react'
import { AlertTriangle, CheckCircle, Search, XCircle } from 'lucide-react'
import { api } from '../utils/api'
import './IncidentsPage.css'

interface Incident {
  id: string; incident_id: string; title: string; incident_type: string
  severity: string; status: string; description: string; asset_id?: string
  detected_at?: string; is_safety_critical: boolean; is_reportable: boolean
  root_cause?: string; mitigation_steps?: string; closed_at?: string; created_at: string
}

const SEV_COLORS: Record<string, string> = { critical: 'badge-red', major: 'badge-red', minor: 'badge-amber', insignificant: 'badge-green' }
const STATUS_COLORS: Record<string, string> = { open: 'badge-red', investigating: 'badge-amber', resolved: 'badge-green', closed: 'badge-purple' }

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selected, setSelected] = useState<Incident | null>(null)

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await api.get('/audit/incidents')
      setIncidents(Array.isArray(data) ? data : [])
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const filtered = incidents.filter(i => {
    if (search && !i.title?.toLowerCase().includes(search.toLowerCase()) && !i.incident_id?.toLowerCase().includes(search.toLowerCase())) return false
    if (statusFilter && i.status !== statusFilter) return false
    return true
  })

  return (
    <div className="incidents-page">
      <div className="page-header">
        <h1>Safety Incidents</h1>
        <p>EN 50128 / ISO 9001 — Railway safety incident tracking</p>
      </div>

      <div className="flex justify-between items-center gap-12 mb-24">
        <div className="flex gap-8" style={{ flex: 1, maxWidth: 500 }}>
          <div className="search-bar" style={{ flex: 1 }}>
            <Search size={16} className="search-icon" />
            <input className="input search-input" placeholder="Search incidents…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 140 }}>
            <option value="">All Status</option>
            {['open', 'investigating', 'resolved', 'closed'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Incident ID</th><th>Type</th><th>Severity</th><th>Status</th><th>Safety Critical</th><th>Detected</th></tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="text-muted text-sm">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={6} className="text-muted text-sm">No incidents reported.</td></tr>
              ) : filtered.map(i => (
                <tr key={i.id} className="clickable-row" onClick={() => setSelected(i)}>
                  <td><code style={{ fontSize: 12 }}>{i.incident_id}</code></td>
                  <td><span className="badge badge-purple">{i.incident_type?.replace('_', ' ')}</span></td>
                  <td><span className={`badge ${SEV_COLORS[i.severity]}`}>{i.severity}</span></td>
                  <td><span className={`badge ${STATUS_COLORS[i.status]}`}>{i.status}</span></td>
                  <td>{i.is_safety_critical ? <AlertTriangle size={14} style={{ color: 'var(--red)' }} /> : <CheckCircle size={14} style={{ color: 'var(--green)' }} />}</td>
                  <td className="text-muted text-sm">{i.detected_at ? new Date(i.detected_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div><h3>{selected.incident_id}</h3><span className={`badge ${SEV_COLORS[selected.severity]}`} style={{ marginLeft: 8 }}>{selected.severity}</span></div>
              <button className="btn btn-ghost" onClick={() => setSelected(null)}><XCircle size={16} /></button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Status</label><span className={`badge ${STATUS_COLORS[selected.status]}`}>{selected.status}</span></div>
                <div><label>Type</label><span>{selected.incident_type?.replace('_', ' ')}</span></div>
                <div><label>Safety Critical</label><span>{selected.is_safety_critical ? 'Yes' : 'No'}</span></div>
                <div><label>Reportable</label><span>{selected.is_reportable ? 'Yes' : 'No'}</span></div>
                <div><label>Detected</label><span>{selected.detected_at ? new Date(selected.detected_at).toLocaleString() : '—'}</span></div>
                {selected.closed_at && <div><label>Closed</label><span>{new Date(selected.closed_at).toLocaleString()}</span></div>}
              </div>
              <div style={{ marginTop: 16 }}>
                <label>Description</label>
                <p className="text-sm" style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{selected.description}</p>
              </div>
              {selected.root_cause && <div style={{ marginTop: 12 }}><label>Root Cause</label><p className="text-sm" style={{ marginTop: 4 }}>{selected.root_cause}</p></div>}
              {selected.mitigation_steps && <div style={{ marginTop: 12 }}><label>Mitigation Steps</label><p className="text-sm" style={{ marginTop: 4 }}>{selected.mitigation_steps}</p></div>}
            </div>
            <div className="modal-footer"><button className="btn btn-ghost" onClick={() => setSelected(null)}>Close</button></div>
          </div>
        </div>
      )}
    </div>
  )
}
