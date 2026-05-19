import { useState, useEffect } from 'react'
import { Download, Search } from 'lucide-react'
import { api } from '../utils/api'
import './AuditLog.css'

interface AuditEvent {
  id: string
  timestamp: string
  user: string
  action: string
  resource: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  detail: string
}

const SEV_MAP: Record<string, string> = { low: 'badge-green', medium: 'badge-amber', high: 'badge-red', critical: 'badge-red' }
const SEV_COLOUR: Record<string, string> = { low: 'var(--green)', medium: 'var(--amber)', high: 'var(--red)', critical: '#ff1744' }

function severityForAction(action: string): 'low' | 'medium' | 'high' | 'critical' {
  const a = action.toLowerCase()
  if (a.includes('delete') || a.includes('login_failed')) return 'high'
  if (a.includes('create') || a.includes('approve') || a.includes('upload')) return 'medium'
  if (a.includes('login')) return 'low'
  return 'low'
}

function formatDetail(details: any): string {
  if (!details) return ''
  if (typeof details === 'string') return details
  try { return JSON.stringify(details) } catch { return String(details) }
}

export default function AuditLog() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState<keyof AuditEvent>('timestamp')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  useEffect(() => { loadLogs() }, [])

  const loadLogs = async () => {
    setLoading(true)
    try {
      const data = await api.get('/audit/logs?limit=500')
      const mapped: AuditEvent[] = (Array.isArray(data) ? data : (data.logs ?? [])).map((entry: any) => ({
        id: entry.id,
        timestamp: entry.timestamp,
        user: entry.user_id ? entry.user_id.slice(0, 8) : 'system',
        action: entry.action,
        resource: entry.resource_type || '',
        severity: severityForAction(entry.action),
        detail: formatDetail(entry.details),
      }))
      setEvents(mapped)
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const filtered = events.filter(e => {
    if (!search) return true
    const s = search.toLowerCase()
    return e.action.toLowerCase().includes(s) || e.resource.toLowerCase().includes(s) || e.detail.toLowerCase().includes(s) || e.user.toLowerCase().includes(s)
  })

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortCol] ?? ''
    const bv = b[sortCol] ?? ''
    return sortDir === 'asc' ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
  })

  const toggleSort = (col: keyof AuditEvent) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('desc') }
  }

  const exportCsv = () => {
    const cols: (keyof AuditEvent)[] = ['timestamp', 'user', 'action', 'resource', 'severity', 'detail']
    const header = cols.join(',')
    const rows = sorted.map(e => cols.map(c => `"${String(e[c]).replace(/"/g, '""')}"`).join(','))
    const csv = [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'audit_log.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const th = (col: keyof AuditEvent, label: string) => (
    <th onClick={() => toggleSort(col)} style={{ cursor: 'pointer' }}>{label} {sortCol === col ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
  )

  return (
    <div className="audit-log">
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Audit Log</h1>
          <p>Immutable, signed audit trail of all Cortex operations.</p>
        </div>
        <button className="btn btn-ghost" onClick={exportCsv}><Download size={14} /> Export CSV</button>
      </div>

      <div className="flex gap-8 mb-24" style={{ maxWidth: 400 }}>
        <div className="search-bar" style={{ flex: 1 }}>
          <Search size={16} className="search-icon" />
          <input className="input search-input" placeholder="Search by action, resource, user…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{th('timestamp', 'Timestamp')}{th('user', 'User')}{th('action', 'Action')}{th('resource', 'Resource')}{th('severity', 'Severity')}{th('detail', 'Detail')}</tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="text-muted text-sm">Loading…</td></tr>
              ) : sorted.length === 0 ? (
                <tr><td colSpan={6} className="text-muted text-sm">No audit events found.</td></tr>
              ) : sorted.map(e => (
                <tr key={e.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: 12 }}>{e.timestamp.replace('T', ' ').replace('Z', '').slice(0, 19)}</td>
                  <td><span className="badge badge-purple">{e.user}</span></td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{e.action}</td>
                  <td className="text-muted text-sm">{e.resource}</td>
                  <td><span className={`badge ${SEV_MAP[e.severity]}`} style={{ color: SEV_COLOUR[e.severity] }}>{e.severity}</span></td>
                  <td className="text-sm">{e.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
