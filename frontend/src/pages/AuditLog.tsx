import { useState } from 'react'
import { Download } from 'lucide-react'
import './AuditLog.css'

interface AuditEvent {
  id: number
  timestamp: string
  user: string
  action: string
  resource: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  detail: string
}

const FAKE_EVENTS: AuditEvent[] = [
  { id: 1, timestamp: '2026-04-21T02:15:00Z', user: 'admin', action: 'LOGIN', resource: 'auth', severity: 'low', detail: 'Successful JWT login' },
  { id: 2, timestamp: '2026-04-21T02:18:00Z', user: 'admin', action: 'QUERY', resource: 'agent', severity: 'low', detail: 'Agent query: "summarize IEC 62304 requirements"' },
  { id: 3, timestamp: '2026-04-21T02:20:00Z', user: 'admin', action: 'MEMORY_ADD', resource: 'memory', severity: 'low', detail: 'Added memory entry: compliance framework' },
  { id: 4, timestamp: '2026-04-21T02:25:00Z', user: 'system', action: 'AUDIT_EXPORT', resource: 'audit', severity: 'medium', detail: 'Audit log exported by admin' },
  { id: 5, timestamp: '2026-04-21T02:30:00Z', user: 'admin', action: 'MODEL_QUERY', resource: 'brain', severity: 'low', detail: 'Model llama3 latency: 420ms' },
  { id: 6, timestamp: '2026-04-20T18:00:00Z', user: 'system', action: 'COMPLIANCE_CHECK', resource: 'knowledgebase', severity: 'high', detail: 'Citation verification failed for entry #42' },
  { id: 7, timestamp: '2026-04-20T16:00:00Z', user: 'researcher', action: 'LOGIN', resource: 'auth', severity: 'low', detail: 'Successful JWT login' },
  { id: 8, timestamp: '2026-04-20T16:05:00Z', user: 'researcher', action: 'RTM_GENERATE', resource: 'compliance', severity: 'medium', detail: 'Requirements traceability matrix generated' },
]

const sevClass: Record<string, string> = {
  low: 'badge-green', medium: 'badge-amber', high: 'badge-red', critical: 'badge-red',
}
const sevColour: Record<string, string> = {
  low: 'var(--green)', medium: 'var(--amber)', high: 'var(--red)', critical: '#ff1744',
}

export default function AuditLog() {
  const [events] = useState<AuditEvent[]>(FAKE_EVENTS)
  const [sortCol, setSortCol] = useState<keyof AuditEvent>('timestamp')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const sorted = [...events].sort((a, b) => {
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

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{th('timestamp', 'Timestamp')}{th('user', 'User')}{th('action', 'Action')}{th('resource', 'Resource')}{th('severity', 'Severity')}{th('detail', 'Detail')}</tr>
            </thead>
            <tbody>
              {sorted.map(e => (
                <tr key={e.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: 12 }}>{e.timestamp.replace('T', ' ').replace('Z', '')}</td>
                  <td><span className="badge badge-purple">{e.user}</span></td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{e.action}</td>
                  <td className="text-muted text-sm">{e.resource}</td>
                  <td><span className={`badge ${sevClass[e.severity]}`} style={{ color: sevColour[e.severity] }}>{e.severity}</span></td>
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