import { useState, useEffect, useRef } from 'react'
import { Plus, Search, CheckCircle, Upload, RefreshCw, X } from 'lucide-react'
import { api } from '../utils/api'
import './RequirementsPage.css'

interface Requirement {
  id: string; requirement_id: string; title: string; description: string
  rationale?: string; requirement_type?: string; priority: string; status: string
  safety_class: string; sil_level: string; category?: string; source?: string
  compliance_ref?: string; stakeholder?: string; acceptance_criteria?: string
  allocation?: string; version: number; change_history?: any[]
  verification_method?: string; verification_status: string
  created_by: string; created_at: string; updated_at?: string
  approved_at?: string; approved_by?: string; citations?: RequirementCitation[]
}

interface RequirementCitation {
  id: string; citation_type: string; citation_text?: string; verified: boolean
  target_requirement_id?: string
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'badge-amber', review: 'badge-amber', approved: 'badge-green',
  verified: 'badge-green', implemented: 'badge-purple', rejected: 'badge-red',
}
const VERIF_COLORS: Record<string, string> = {
  pending: 'badge-amber', passed: 'badge-green', failed: 'badge-red', blocked: 'badge-red', not_applicable: 'badge-purple',
}
const CITATION_TYPES = ['verifies', 'satisfies', 'conflicts_with', 'refines']
const REQ_TYPES = ['functional', 'performance', 'interface', 'design_constraint', 'security', 'safety', 'usability', 'maintainability', 'regulatory', 'environmental', 'other']
const SAFETY_CLASSES = ['class_a', 'class_b', 'class_c']
const SIL_LEVELS = ['sil0', 'sil1', 'sil2', 'sil3', 'sil4']

export default function RequirementsPage() {
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [selectedReq, setSelectedReq] = useState<Requirement | null>(null)
  const [showCitationModal, setShowCitationModal] = useState(false)
  const [citationTarget, setCitationTarget] = useState('')
  const [citationType, setCitationType] = useState('verifies')
  const [citationText, setCitationText] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [importType, setImportType] = useState<'doc' | 'batch'>('doc')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importPreview, setImportPreview] = useState<any[]>([])
  const [importSaving, setImportSaving] = useState(false)
  const [batchJson, setBatchJson] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState({
    requirement_id: '', title: '', description: '', priority: 'shall',
    requirement_type: '', rationale: '', source: '', compliance_ref: '',
    stakeholder: '', acceptance_criteria: '', allocation: '',
    safety_class: 'class_b', sil_level: 'sil2', category: 'functional',
    verification_method: 'inspection',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { loadRequirements() }, [])

  const loadRequirements = async () => {
    setLoading(true)
    try {
      const data = await api.get('/requirements')
      setRequirements(Array.isArray(data) ? data : (data.requirements ?? []))
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const filtered = requirements.filter(r => {
    if (search && !r.title.toLowerCase().includes(search.toLowerCase()) &&
        !r.requirement_id.toLowerCase().includes(search.toLowerCase())) return false
    if (statusFilter && r.status !== statusFilter) return false
    if (typeFilter && r.requirement_type !== typeFilter) return false
    return true
  })

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      const payload: any = { ...form }
      if (!payload.requirement_type) delete payload.requirement_type
      if (!payload.rationale) delete payload.rationale
      if (!payload.source) delete payload.source
      if (!payload.compliance_ref) delete payload.compliance_ref
      if (!payload.stakeholder) delete payload.stakeholder
      if (!payload.acceptance_criteria) delete payload.acceptance_criteria
      if (!payload.allocation) delete payload.allocation
      await api.post('/requirements', payload)
      setShowModal(false)
      setForm({ requirement_id: '', title: '', description: '', priority: 'shall',
        requirement_type: '', rationale: '', source: '', compliance_ref: '',
        stakeholder: '', acceptance_criteria: '', allocation: '',
        safety_class: 'class_b', sil_level: 'sil2', category: 'functional',
        verification_method: 'inspection' })
      loadRequirements()
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleApprove = async (id: string) => {
    try {
      await api.post(`/requirements/${id}/approve`, { justification: 'Approved via UI' })
      loadRequirements()
    } catch (e: any) { setError(e.message) }
  }

  const handleAddCitation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedReq) return
    setSaving(true)
    try {
      await api.post('/requirements/citations', {
        source_requirement_id: selectedReq.id,
        target_requirement_id: citationTarget,
        citation_type: citationType,
        citation_text: citationText,
      })
      setShowCitationModal(false); setCitationTarget(''); setCitationText('')
      loadRequirements()
      const updated = await api.get(`/requirements/${selectedReq.id}`)
      setSelectedReq(updated.requirement !== undefined ? updated.requirement : updated)
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleVerifyCitation = async (citationId: string) => {
    try {
      await api.patch(`/requirements/citations/${citationId}/verify`, {})
      loadRequirements()
    } catch (e: any) { setError(e.message) }
  }

  const handleDocImport = async () => {
    if (!importFile) return
    setImportSaving(true); setError('')
    try {
      const formData = new FormData()
      formData.append('file', importFile)
      const resp = await fetch('/api/requirements/import-document', {
        method: 'POST', credentials: 'include', body: formData,
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Import failed')
      setImportPreview(data.requirements || data.preview || data)
    } catch (e: any) { setError(e.message) }
    finally { setImportSaving(false) }
  }

  const handleBatchImport = async () => {
    setImportSaving(true); setError('')
    try {
      const json = JSON.parse(batchJson)
      const resp = await api.post('/requirements/import-batch', { items: Array.isArray(json) ? json : [] })
      setImportPreview(resp.preview || resp.requirements || resp)
    } catch (e: any) { setError(e.message) }
    finally { setImportSaving(false) }
  }

  const saveImported = async () => {
    setImportSaving(true); setError('')
    try {
      await api.post('/requirements/import-batch/save', { items: importPreview })
      setImportPreview([]); setShowImport(false)
      loadRequirements()
    } catch (e: any) { setError(e.message) }
    finally { setImportSaving(false) }
  }

  const deleteImportedItem = (idx: number) => {
    setImportPreview(prev => prev.filter((_, i) => i !== idx))
  }

  return (
    <div className="requirements-page">
      <div className="page-header">
        <h1>Requirements</h1>
        <p>INCOSE / ISO 29148 requirements specification. Import documents, extract with LLM, export to ReqIF (IBM DOORS).</p>
      </div>

      <div className="flex justify-between items-center gap-12 mb-24" style={{ flexWrap: 'wrap' }}>
        <div className="flex gap-8" style={{ flex: 1, minWidth: 400 }}>
          <div className="search-bar" style={{ flex: 1 }}>
            <Search size={16} className="search-icon" />
            <input className="input search-input" placeholder="Search requirements…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 110 }}>
            <option value="">All Status</option>
            {['draft', 'review', 'approved', 'verified', 'implemented', 'rejected'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="input" value={typeFilter} onChange={e => setTypeFilter(e.target.value)} style={{ width: 120 }}>
            <option value="">All Types</option>
            {REQ_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
          </select>
        </div>
        <div className="flex gap-8">
          <button className="btn btn-ghost" onClick={() => setShowImport(true)}><Upload size={14} /> Import</button>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={16} /> New Requirement</button>
        </div>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Title</th><th>Type</th><th>Priority</th><th>Status</th>
                <th>Safety Class</th><th>SIL</th><th>Verification</th>
                <th>Version</th><th>Links</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="text-muted text-sm">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={10} className="text-muted text-sm">No requirements found.</td></tr>
              ) : filtered.map(req => (
                <tr key={req.id} className="clickable-row" onClick={() => setSelectedReq(req)}>
                  <td><code style={{ fontSize: 12 }}>{req.requirement_id}</code></td>
                  <td><span style={{ maxWidth: 180, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{req.title}</span></td>
                  <td><span className="badge badge-purple">{req.requirement_type || req.category || '—'}</span></td>
                  <td><span className={`badge ${req.priority === 'shall' ? 'badge-red' : req.priority === 'must' ? 'badge-amber' : 'badge-purple'}`}>{req.priority}</span></td>
                  <td><span className={`badge ${STATUS_COLORS[req.status] || 'badge-purple'}`}>{req.status}</span></td>
                  <td><span className="badge badge-purple">{req.safety_class}</span></td>
                  <td><span className={`badge ${['sil3','sil4'].includes(req.sil_level) ? 'badge-red' : req.sil_level === 'sil2' ? 'badge-amber' : 'badge-green'}`}>{req.sil_level.toUpperCase()}</span></td>
                  <td><span className={`badge ${VERIF_COLORS[req.verification_status] || 'badge-purple'}`}>{req.verification_status}</span></td>
                  <td><span className="badge badge-purple">v{req.version}</span></td>
                  <td><span className="text-muted text-sm">{(req.citations ?? []).length} link(s)</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedReq && (
        <div className="modal-overlay" onClick={() => setSelectedReq(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{selectedReq.title}</h3>
                <code style={{ fontSize: 11, color: 'var(--text-muted)' }}>{selectedReq.requirement_id} — v{selectedReq.version}</code>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelectedReq(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Status</label><span className={`badge ${STATUS_COLORS[selectedReq.status]}`}>{selectedReq.status}</span></div>
                <div><label>Type</label><span>{selectedReq.requirement_type || selectedReq.category || '—'}</span></div>
                <div><label>Priority</label><span>{selectedReq.priority}</span></div>
                <div><label>Safety Class</label><span>{selectedReq.safety_class}</span></div>
                <div><label>SIL Level</label><span>{selectedReq.sil_level.toUpperCase()}</span></div>
                <div><label>Verification</label><span className={`badge ${VERIF_COLORS[selectedReq.verification_status]}`}>{selectedReq.verification_status} ({selectedReq.verification_method||'—'})</span></div>
                <div><label>Source</label><span>{selectedReq.source || '—'}</span></div>
                <div><label>Stakeholder</label><span>{selectedReq.stakeholder || '—'}</span></div>
                <div><label>Allocation</label><span>{selectedReq.allocation || '—'}</span></div>
                <div><label>Compliance</label><span>{selectedReq.compliance_ref || '—'}</span></div>
                <div><label>Created</label><span>{new Date(selectedReq.created_at).toLocaleString()}</span></div>
                {selectedReq.approved_at && <div><label>Approved</label><span>{new Date(selectedReq.approved_at).toLocaleString()}</span></div>}
              </div>

              {selectedReq.rationale && (
                <div style={{ marginTop: 16 }}>
                  <label>Rationale</label>
                  <p className="text-sm" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{selectedReq.rationale}</p>
                </div>
              )}

              <div style={{ marginTop: 16 }}>
                <label>Description</label>
                <p className="text-sm" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{selectedReq.description}</p>
              </div>

              {selectedReq.acceptance_criteria && (
                <div style={{ marginTop: 12 }}>
                  <label>Acceptance Criteria</label>
                  <p className="text-sm" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{selectedReq.acceptance_criteria}</p>
                </div>
              )}

              <div style={{ marginTop: 20 }}>
                <div className="flex justify-between items-center mb-12">
                  <h4>Traceability Citations</h4>
                  <button className="btn btn-ghost btn-sm" onClick={() => setShowCitationModal(true)}>+ Add Citation</button>
                </div>
                {!selectedReq.citations || selectedReq.citations.length === 0 ? (
                  <p className="text-muted text-sm">No traceability links.</p>
                ) : (
                  <div className="citation-list">
                    {selectedReq.citations.map(c => (
                      <div key={c.id} className="citation-item">
                        <div className="flex items-center gap-8">
                          <span className="badge badge-purple">{c.citation_type}</span>
                          <code style={{ fontSize: 11 }}>{c.target_requirement_id}</code>
                          {c.verified
                            ? <CheckCircle size={14} style={{ color: 'var(--green)' }} />
                            : <button className="btn btn-ghost btn-sm" onClick={() => handleVerifyCitation(c.id)}>Verify</button>
                          }
                        </div>
                        {c.citation_text && <p className="text-sm text-muted" style={{ marginTop: 4 }}>{c.citation_text}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {selectedReq.change_history && selectedReq.change_history.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <label>Change History</label>
                  <div className="text-sm" style={{ maxHeight: 150, overflowY: 'auto', marginTop: 4 }}>
                    {[...(selectedReq.change_history)].reverse().slice(0, 5).map((ch: any, i: number) => (
                      <div key={i} className="text-muted" style={{ marginBottom: 4 }}>
                        v{ch.version} — {ch.when?.slice(0, 19)} — {Object.keys(ch.what || {}).join(', ')}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="modal-footer">
              {['draft','review'].includes(selectedReq.status) && (
                <button className="btn btn-primary" onClick={() => handleApprove(selectedReq.id)}><CheckCircle size={14} /> Approve</button>
              )}
              <button className="btn btn-ghost" onClick={() => setSelectedReq(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {showCitationModal && selectedReq && (
        <div className="modal-overlay" onClick={() => setShowCitationModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Add Citation</h3><button className="btn btn-ghost" onClick={() => setShowCitationModal(false)}><X size={16} /></button></div>
            <form onSubmit={handleAddCitation}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Citation Type *</label>
                  <select className="input" value={citationType} onChange={e => setCitationType(e.target.value)}>
                    {CITATION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="form-group" style={{ marginTop: 12 }}>
                  <label>Target Requirement UUID *</label>
                  <input className="input" placeholder="UUID" value={citationTarget} onChange={e => setCitationTarget(e.target.value)} required />
                </div>
                <div className="form-group" style={{ marginTop: 12 }}>
                  <label>Citation Text</label>
                  <textarea className="input" rows={3} value={citationText} onChange={e => setCitationText(e.target.value)} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCitationModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Adding…' : 'Add Citation'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>New Requirement</h3><button className="btn btn-ghost" onClick={() => setShowModal(false)}><X size={16} /></button></div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                {error && <div className="alert-error mb-16">{error}</div>}
                <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
                  <div className="form-group"><label>Requirement ID *</label><input className="input" placeholder="e.g., REQ-SIG-001" value={form.requirement_id} onChange={e => setForm({ ...form, requirement_id: e.target.value })} required /></div>
                  <div className="form-group"><label>Title *</label><input className="input" placeholder="Brief title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required /></div>
                  <div className="form-group">
                    <label>Type (INCOSE)</label>
                    <select className="input" value={form.requirement_type} onChange={e => setForm({ ...form, requirement_type: e.target.value })}>
                      <option value="">—</option>
                      {REQ_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Priority</label>
                    <select className="input" value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}>
                      {['shall', 'must', 'should', 'may'].map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Safety Class</label>
                    <select className="input" value={form.safety_class} onChange={e => setForm({ ...form, safety_class: e.target.value })}>
                      {SAFETY_CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>SIL Level</label>
                    <select className="input" value={form.sil_level} onChange={e => setForm({ ...form, sil_level: e.target.value })}>
                      {SIL_LEVELS.map(s => <option key={s} value={s}>{s.toUpperCase()}</option>)}
                    </select>
                  </div>
                  <div className="form-group"><label>Source</label><input className="input" placeholder="Stakeholder, regulation clause, derived-from" value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} /></div>
                  <div className="form-group"><label>Stakeholder</label><input className="input" placeholder="Who needs this?" value={form.stakeholder} onChange={e => setForm({ ...form, stakeholder: e.target.value })} /></div>
                  <div className="form-group"><label>Compliance Ref</label><input className="input" placeholder="e.g., EN 50128 §5.2.3" value={form.compliance_ref} onChange={e => setForm({ ...form, compliance_ref: e.target.value })} /></div>
                  <div className="form-group"><label>Allocation</label><input className="input" placeholder="Subsystem / component" value={form.allocation} onChange={e => setForm({ ...form, allocation: e.target.value })} /></div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}><label>Description *</label><textarea className="input" rows={3} placeholder="Full SHALL statement" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} required /></div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}><label>Rationale</label><textarea className="input" rows={3} placeholder="Why this requirement exists" value={form.rationale} onChange={e => setForm({ ...form, rationale: e.target.value })} /></div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}><label>Acceptance Criteria</label><textarea className="input" rows={3} placeholder="Pass/fail conditions" value={form.acceptance_criteria} onChange={e => setForm({ ...form, acceptance_criteria: e.target.value })} /></div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Creating…' : 'Create Requirement'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showImport && (
        <div className="modal-overlay" onClick={() => setShowImport(false)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Import Requirements</h3><button className="btn btn-ghost" onClick={() => { setShowImport(false); setImportPreview([]) }}><X size={16} /></button></div>
            <div className="modal-body">
              <div className="flex gap-8 mb-16">
                <button className={`btn ${importType === 'doc' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setImportType('doc')}>Document (LLM)</button>
                <button className={`btn ${importType === 'batch' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setImportType('batch')}>Batch JSON</button>
              </div>

              {importType === 'doc' && (
                <div>
                  <p className="text-sm text-muted mb-12">
                    Upload a .docx, .pdf, or .md file. LLM will extract INCOSE-compliant requirements using the product knowledge base.
                  </p>
                  <div className="flex gap-8 mb-12">
                    <input ref={fileRef} type="file" accept=".docx,.pdf,.md,.txt,.html" onChange={e => setImportFile(e.target.files?.[0] ?? null)} className="input" style={{ flex: 1 }} />
                    <button className="btn btn-primary" onClick={handleDocImport} disabled={!importFile || importSaving}>
                      <RefreshCw size={14} /> {importSaving ? 'Extracting…' : 'Extract'}
                    </button>
                  </div>
                </div>
              )}

              {importType === 'batch' && (
                <div>
                  <p className="text-sm text-muted mb-12">Paste JSON array of requirement objects:</p>
                  <textarea className="input" rows={8} style={{ fontFamily: 'monospace', fontSize: 11 }}
                    placeholder='[{"requirement_id":"REQ-001","title":"…","description":"…","requirement_type":"functional","priority":"shall"},…]'
                    value={batchJson} onChange={e => setBatchJson(e.target.value)} />
                  <div className="mt-12">
                    <button className="btn btn-primary" onClick={handleBatchImport} disabled={!batchJson || importSaving}>
                      <RefreshCw size={14} /> Parse
                    </button>
                  </div>
                </div>
              )}

              {importPreview.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <h4 className="mb-12">{importPreview.length} requirements extracted</h4>
                  <div style={{ maxHeight: 350, overflowY: 'auto' }}>
                    {importPreview.map((item: any, i: number) => (
                      <div key={i} className="flex gap-12 mb-8" style={{ alignItems: 'flex-start', padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                        <div style={{ flex: 1 }}>
                          <strong style={{ fontSize: 13 }}>{item.requirement_id}</strong>
                          <span className="badge badge-purple" style={{ marginLeft: 8 }}>{item.requirement_type || '—'}</span>
                          <span className={`badge ${item.priority === 'shall' ? 'badge-red' : 'badge-amber'}`} style={{ marginLeft: 4 }}>{item.priority}</span>
                          <p className="text-sm" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{item.description || item.title}</p>
                          {(item.rationale || item.source || item.acceptance_criteria) && (
                            <div className="text-sm text-muted flex gap-12 mt-4">
                              {item.rationale && <span>Rationale: {item.rationale.slice(0, 80)}…</span>}
                              {item.source && <span>Source: {item.source}</span>}
                            </div>
                          )}
                        </div>
                        <button className="btn btn-ghost btn-sm" onClick={() => deleteImportedItem(i)} style={{ color: 'var(--red)' }}><X size={12} /></button>
                      </div>
                    ))}
                  </div>
                  <div className="mt-16"><button className="btn btn-primary" onClick={saveImported} disabled={importSaving}>{importSaving ? 'Saving…' : `Save ${importPreview.length} Requirements`}</button></div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
