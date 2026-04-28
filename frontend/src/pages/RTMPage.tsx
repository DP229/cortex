import { useState, useEffect } from 'react'
import { CheckCircle, XCircle, Clock } from 'lucide-react'
import { api } from '../utils/api'
import './RTMPage.css'

interface RTMRequirement {
  id: string
  requirement_id: string
  title: string
  status: string
  safety_class: string
  sil_level: string
  verification_status: string
  citations: RTMCitation[]
  test_records: RTMTestRecord[]
}

interface RTMCitation {
  id: string
  citation_type: string
  source_req_id: string
  target_req_id: string
  verified: boolean
  citation_text?: string
}

interface RTMTestRecord {
  id: string
  test_id: string
  status: string
  passed_count: number
  failed_count: number
}

interface ComplianceSummary {
  total: number
  verified: number
  failed: number
  pending: number
  not_applicable: number
  coverage_pct: number
}

export default function RTMPage() {
  const [requirements, setRequirements] = useState<RTMRequirement[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedReq, setSelectedReq] = useState<RTMRequirement | null>(null)
  const [error, setError] = useState('')
  const [summary, setSummary] = useState<ComplianceSummary>({ total: 0, verified: 0, failed: 0, pending: 0, not_applicable: 0, coverage_pct: 0 })

  useEffect(() => { loadRTM() }, [])

  const loadRTM = async () => {
    setLoading(true)
    try {
      const reqsRes = await api.get('/v1/requirements')
      const reqs: RTMRequirement[] = Array.isArray(reqsRes) ? reqsRes : (reqsRes.requirements ?? [])

      const enriched = await Promise.allSettled(
        reqs.map(async (r) => {
          try {
            const full = await api.get(`/v1/requirements/${r.id}`)
            return Array.isArray(full) ? r : { ...r, citations: (full as any).citations ?? [], test_records: (full as any).test_records ?? [] }
          } catch {
            return { ...r, citations: [], test_records: [] }
          }
        })
      )

      const finalReqs = enriched
        .filter((r): r is PromiseFulfilledResult<RTMRequirement> => r.status === 'fulfilled')
        .map(r => r.value)

      setRequirements(finalReqs)

      const verified = finalReqs.filter(r => r.verification_status === 'passed').length
      const failed = finalReqs.filter(r => ['failed', 'blocked'].includes(r.verification_status)).length
      const pending = finalReqs.filter(r => r.verification_status === 'pending').length
      const na = finalReqs.filter(r => r.verification_status === 'not_applicable').length
      setSummary({
        total: finalReqs.length,
        verified,
        failed,
        pending,
        not_applicable: na,
        coverage_pct: finalReqs.length > 0 ? Math.round((verified / finalReqs.length) * 100) : 0,
      })
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const getReqStatus = (req: RTMRequirement) => {
    if (req.verification_status === 'passed') return 'verified'
    if (['failed', 'blocked'].includes(req.verification_status)) return 'failed'
    if (req.verification_status === 'not_applicable') return 'na'
    if (req.citations.length > 0 && req.citations.every(c => c.verified)) return 'cited_and_verified'
    return 'pending'
  }

  const statusColor = (s: string) => {
    switch (s) {
      case 'verified': return 'var(--green)'
      case 'failed': return 'var(--red)'
      case 'na': return 'var(--accent)'
      case 'cited_and_verified': return '#66bb6a'
      default: return 'var(--amber)'
    }
  }

  const statusLabel = (s: string) => {
    switch (s) {
      case 'verified': return 'Verified'
      case 'failed': return 'Failed'
      case 'na': return 'N/A'
      case 'cited_and_verified': return 'Cited'
      default: return 'Pending'
    }
  }

  return (
    <div className="rtm-page">
      <div className="page-header">
        <h1>Requirements Traceability Matrix</h1>
        <p>EN 50128 bidirectional traceability — requirements, citations, and tests</p>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="stats-row" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
        <div className="stat-card">
          <div className="stat-card__label">Total Requirements</div>
          <div className="stat-card__value">{loading ? '…' : summary.total}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label"><CheckCircle size={10} style={{ display: 'inline', marginRight: 4 }} />Verified</div>
          <div className="stat-card__value" style={{ color: 'var(--green)' }}>{loading ? '…' : summary.verified}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label"><XCircle size={10} style={{ display: 'inline', marginRight: 4 }} />Failed</div>
          <div className="stat-card__value" style={{ color: 'var(--red)' }}>{loading ? '…' : summary.failed}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label"><Clock size={10} style={{ display: 'inline', marginRight: 4 }} />Pending</div>
          <div className="stat-card__value" style={{ color: 'var(--amber)' }}>{loading ? '…' : summary.pending}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">N/A</div>
          <div className="stat-card__value">{loading ? '…' : summary.not_applicable}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Coverage</div>
          <div className="stat-card__value" style={{ color: summary.coverage_pct >= 80 ? 'var(--green)' : summary.coverage_pct >= 50 ? 'var(--amber)' : 'var(--red)' }}>
            {loading ? '…' : `${summary.coverage_pct}%`}
          </div>
          <div className="stat-card__sub">verified</div>
        </div>
      </div>

      <div className="card mb-16">
        <div className="flex gap-16 items-center flex-wrap">
          <span className="text-sm text-muted">Legend:</span>
          <div className="flex gap-8 items-center"><div style={{ width: 12, height: 12, borderRadius: 3, background: 'var(--green)' }} /><span className="text-sm">Verified</span></div>
          <div className="flex gap-8 items-center"><div style={{ width: 12, height: 12, borderRadius: 3, background: 'var(--red)' }} /><span className="text-sm">Failed</span></div>
          <div className="flex gap-8 items-center"><div style={{ width: 12, height: 12, borderRadius: 3, background: 'var(--amber)' }} /><span className="text-sm">Pending</span></div>
          <div className="flex gap-8 items-center"><div style={{ width: 12, height: 12, borderRadius: 3, background: 'var(--accent)' }} /><span className="text-sm">N/A</span></div>
          <div className="flex gap-8 items-center"><div style={{ width: 12, height: 12, borderRadius: 3, background: '#66bb6a' }} /><span className="text-sm">Cited &amp; Verified</span></div>
        </div>
      </div>

      {loading ? (
        <div className="card"><p className="text-muted text-sm">Loading RTM data…</p></div>
      ) : requirements.length === 0 ? (
        <div className="card"><p className="text-muted text-sm">No requirements found. Create requirements first.</p></div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table className="rtm-table">
              <thead>
                <tr>
                  <th style={{ minWidth: 120 }}>Req ID</th>
                  <th style={{ minWidth: 200 }}>Title</th>
                  <th>SIL</th>
                  <th>Verification</th>
                  <th style={{ minWidth: 140 }}>Status</th>
                  <th>Citations</th>
                  <th>Tests</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {requirements.map(req => {
                  const status = getReqStatus(req)
                  return (
                    <tr key={req.id} className="clickable-row" onClick={() => setSelectedReq(req)}>
                      <td><code style={{ fontSize: 11 }}>{req.requirement_id}</code></td>
                      <td><span style={{ maxWidth: 200, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{req.title}</span></td>
                      <td><span className={`badge ${req.sil_level === 'sil3' || req.sil_level === 'sil4' ? 'badge-red' : req.sil_level === 'sil2' ? 'badge-amber' : 'badge-green'}`}>{req.sil_level.toUpperCase()}</span></td>
                      <td><span className="text-sm text-muted">{req.verification_status}</span></td>
                      <td>
                        <div className="flex items-center gap-6">
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: statusColor(status) }} />
                          <span className="text-sm" style={{ color: statusColor(status) }}>{statusLabel(status)}</span>
                        </div>
                      </td>
                      <td>
                        <span className="text-sm">{req.citations.length}</span>
                        {req.citations.length > 0 && (
                          <span className="text-sm text-muted"> ({req.citations.filter(c => c.verified).length} ok)</span>
                        )}
                      </td>
                      <td><span className="text-sm">{req.test_records.length}</span></td>
                      <td>
                        {req.test_records.length === 0 ? (
                          <span className="text-muted text-sm">—</span>
                        ) : (
                          <div className="flex gap-4">
                            {req.test_records.some(t => t.status === 'passed') && <CheckCircle size={12} style={{ color: 'var(--green)' }} />}
                            {req.test_records.some(t => t.status === 'failed') && <XCircle size={12} style={{ color: 'var(--red)' }} />}
                            {req.test_records.some(t => t.status === 'pending') && <Clock size={12} style={{ color: 'var(--amber)' }} />}
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedReq && (
        <div className="modal-overlay" onClick={() => setSelectedReq(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{selectedReq.title}</h3>
                <code style={{ fontSize: 11, color: 'var(--text-muted)' }}>{selectedReq.requirement_id}</code>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelectedReq(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Status</label><span className="text-sm">{selectedReq.status}</span></div>
                <div><label>Safety Class</label><span>{selectedReq.safety_class}</span></div>
                <div><label>SIL Level</label><span>{selectedReq.sil_level.toUpperCase()}</span></div>
                <div><label>Verification</label><span className="text-sm">{selectedReq.verification_status}</span></div>
              </div>

              {selectedReq.citations.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <h4>Traceability Citations ({selectedReq.citations.length})</h4>
                  <div className="citation-list mt-8">
                    {selectedReq.citations.map(c => (
                      <div key={c.id} className="citation-item">
                        <div className="flex items-center gap-8">
                          <span className="badge badge-purple">{c.citation_type}</span>
                          <code style={{ fontSize: 11 }}>{c.source_req_id?.slice(0, 8)}… → {c.target_req_id?.slice(0, 8)}…</code>
                          {c.verified
                            ? <CheckCircle size={14} style={{ color: 'var(--green)' }} />
                            : <span className="text-muted text-sm">unverified</span>
                          }
                        </div>
                        {c.citation_text && <p className="text-sm text-muted" style={{ marginTop: 4 }}>{c.citation_text}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedReq.test_records.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <h4>Test Records ({selectedReq.test_records.length})</h4>
                  <div className="table-wrap mt-8">
                    <table>
                      <thead><tr><th>Test ID</th><th>Status</th><th>Passed</th><th>Failed</th></tr></thead>
                      <tbody>
                        {selectedReq.test_records.map(t => (
                          <tr key={t.id}>
                            <td><code style={{ fontSize: 11 }}>{t.test_id}</code></td>
                            <td><span className={`badge ${t.status === 'passed' ? 'badge-green' : t.status === 'failed' ? 'badge-red' : 'badge-amber'}`}>{t.status}</span></td>
                            <td><span style={{ color: 'var(--green)' }}>{t.passed_count}</span></td>
                            <td><span style={{ color: 'var(--red)' }}>{t.failed_count}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <a href="/requirements" className="btn btn-ghost">Open in Requirements</a>
              <button className="btn btn-ghost" onClick={() => setSelectedReq(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
