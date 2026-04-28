import { useState, useEffect } from 'react'
import { Plus, Search, CheckCircle, Clock, Play } from 'lucide-react'
import { api } from '../utils/api'
import './TestRecordsPage.css'

interface TestRecord {
  id: string
  test_id: string
  requirement_id: string
  test_type: string
  test_description: string
  test_results?: string
  expected_results?: string
  status: string
  executed_by?: string
  executed_at?: string
  test_environment?: string
  passed_count: number
  failed_count: number
  blocked_count: number
  is_closed: boolean
  created_at: string
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'badge-amber', passed: 'badge-green', failed: 'badge-red', blocked: 'badge-red', not_applicable: 'badge-purple',
}
const TEST_TYPES = ['unit_test', 'integration_test', 'system_test', 'acceptance_test']

export default function TestRecordsPage() {
  const [records, setRecords] = useState<TestRecord[]>([])
  const [requirements, setRequirements] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [selectedRecord, setSelectedRecord] = useState<TestRecord | null>(null)
  const [showExecuteModal, setShowExecuteModal] = useState(false)
  const [executeResult, setExecuteResult] = useState({ passed: 0, failed: 0, blocked: 0, results: '', new_status: 'pending' })
  const [form, setForm] = useState({
    test_id: '', requirement_id: '', test_type: 'unit_test', test_description: '',
    expected_results: '', test_environment: '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [testsRes, reqsRes] = await Promise.allSettled([
        api.get('/v1/test-records'),
        api.get('/v1/requirements'),
      ])
      setRecords(testsRes.status === 'fulfilled' ? (Array.isArray(testsRes.value) ? testsRes.value : (testsRes.value ?? [])) : [])
      setRequirements(reqsRes.status === 'fulfilled' ? (Array.isArray(reqsRes.value) ? reqsRes.value : (reqsRes.value ?? [])) : [])
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const filtered = records.filter(r => {
    if (search && !r.test_id.toLowerCase().includes(search.toLowerCase()) && !r.test_description.toLowerCase().includes(search.toLowerCase())) return false
    if (statusFilter && r.status !== statusFilter) return false
    return true
  })

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post('/v1/test-records', form)
      setShowModal(false)
      setForm({ test_id: '', requirement_id: '', test_type: 'unit_test', test_description: '', expected_results: '', test_environment: '' })
      loadData()
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedRecord) return
    setSaving(true)
    try {
      await api.post(`/v1/test-records/${selectedRecord.id}/execute`, {
        passed_count: executeResult.passed,
        failed_count: executeResult.failed,
        blocked_count: executeResult.blocked,
        test_results: executeResult.results,
        new_status: executeResult.new_status,
      })
      setShowExecuteModal(false)
      setExecuteResult({ passed: 0, failed: 0, blocked: 0, results: '', new_status: 'pending' })
      loadData()
      setSelectedRecord(null)
    } catch (e: any) { setError(e.message) }
    finally { setSaving(false) }
  }

  return (
    <div className="test-records-page">
      <div className="page-header">
        <h1>Verification Test Records</h1>
        <p>EN 50128 Table A.3 — Test records linked to requirements</p>
      </div>

      <div className="flex justify-between items-center gap-12 mb-24">
        <div className="flex gap-8" style={{ flex: 1, maxWidth: 500 }}>
          <div className="search-bar" style={{ flex: 1 }}>
            <Search size={16} className="search-icon" />
            <input className="input search-input" placeholder="Search test records…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 130 }}>
            <option value="">All Status</option>
            {['pending', 'passed', 'failed', 'blocked', 'not_applicable'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={16} /> Record Test
        </button>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Test ID</th><th>Type</th><th>Requirement</th><th>Status</th>
                <th>Results</th><th>Executed</th><th>Closed</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="text-muted text-sm">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} className="text-muted text-sm">No test records found.</td></tr>
              ) : filtered.map(rec => (
                <tr key={rec.id} className="clickable-row" onClick={() => setSelectedRecord(rec)}>
                  <td><code style={{ fontSize: 12 }}>{rec.test_id}</code></td>
                  <td><span className="badge badge-purple">{rec.test_type.replace('_', ' ')}</span></td>
                  <td><code style={{ fontSize: 11 }}>{rec.requirement_id.slice(0, 8)}…</code></td>
                  <td><span className={`badge ${STATUS_COLORS[rec.status]}`}>{rec.status}</span></td>
                  <td>
                    <span className="text-sm" style={{ color: 'var(--green)' }}>{rec.passed_count} ✓</span>
                    {rec.failed_count > 0 && <span className="text-sm" style={{ color: 'var(--red)', marginLeft: 4 }}>{rec.failed_count} ✗</span>}
                    {rec.blocked_count > 0 && <span className="text-sm" style={{ color: 'var(--amber)', marginLeft: 4 }}>{rec.blocked_count} ⊗</span>}
                    {rec.passed_count === 0 && rec.failed_count === 0 && rec.blocked_count === 0 && <span className="text-muted text-sm">—</span>}
                  </td>
                  <td className="text-muted text-sm">
                    {rec.executed_at ? new Date(rec.executed_at).toLocaleDateString() : '—'}
                  </td>
                  <td>
                    {rec.is_closed
                      ? <CheckCircle size={14} style={{ color: 'var(--green)' }} />
                      : <Clock size={14} style={{ color: 'var(--text-muted)' }} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedRecord && (
        <div className="modal-overlay" onClick={() => setSelectedRecord(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{selectedRecord.test_id}</h3>
                <code style={{ fontSize: 11, color: 'var(--text-muted)' }}>{selectedRecord.test_type.replace('_', ' ')}</code>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelectedRecord(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Status</label><span className={`badge ${STATUS_COLORS[selectedRecord.status]}`}>{selectedRecord.status}</span></div>
                <div><label>Requirement</label><code>{selectedRecord.requirement_id}</code></div>
                <div><label>Passed</label><span style={{ color: 'var(--green)' }}>{selectedRecord.passed_count}</span></div>
                <div><label>Failed</label><span style={{ color: 'var(--red)' }}>{selectedRecord.failed_count}</span></div>
                <div><label>Blocked</label><span style={{ color: 'var(--amber)' }}>{selectedRecord.blocked_count}</span></div>
                <div><label>Executed</label><span>{selectedRecord.executed_at ? new Date(selectedRecord.executed_at).toLocaleString() : 'Not executed'}</span></div>
                <div><label>Environment</label><span>{selectedRecord.test_environment || '—'}</span></div>
                <div><label>Closed</label><span>{selectedRecord.is_closed ? 'Yes' : 'No'}</span></div>
              </div>
              <div style={{ marginTop: 16 }}>
                <label>Test Description</label>
                <p className="text-sm" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{selectedRecord.test_description}</p>
              </div>
              {selectedRecord.expected_results && (
                <div style={{ marginTop: 12 }}>
                  <label>Expected Results</label>
                  <p className="text-sm" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{selectedRecord.expected_results}</p>
                </div>
              )}
              {selectedRecord.test_results && (
                <div style={{ marginTop: 12 }}>
                  <label>Test Results</label>
                  <p className="text-sm" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{selectedRecord.test_results}</p>
                </div>
              )}
            </div>
            <div className="modal-footer">
              {selectedRecord.status === 'pending' && (
                <button className="btn btn-primary" onClick={() => setShowExecuteModal(true)}>
                  <Play size={14} /> Record Execution
                </button>
              )}
              <button className="btn btn-ghost" onClick={() => setSelectedRecord(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {showExecuteModal && selectedRecord && (
        <div className="modal-overlay" onClick={() => setShowExecuteModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Record Test Execution: {selectedRecord.test_id}</h3><button className="btn btn-ghost" onClick={() => setShowExecuteModal(false)}>✕</button></div>
            <form onSubmit={handleExecute}>
              <div className="modal-body">
                <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
                  <div className="form-group">
                    <label>Passed Count</label>
                    <input className="input" type="number" min="0" value={executeResult.passed} onChange={e => setExecuteResult({ ...executeResult, passed: parseInt(e.target.value) || 0 })} />
                  </div>
                  <div className="form-group">
                    <label>Failed Count</label>
                    <input className="input" type="number" min="0" value={executeResult.failed} onChange={e => setExecuteResult({ ...executeResult, failed: parseInt(e.target.value) || 0 })} />
                  </div>
                  <div className="form-group">
                    <label>Blocked Count</label>
                    <input className="input" type="number" min="0" value={executeResult.blocked} onChange={e => setExecuteResult({ ...executeResult, blocked: parseInt(e.target.value) || 0 })} />
                  </div>
                </div>
                <div className="form-group" style={{ marginTop: 12 }}>
                  <label>Overall Status</label>
                  <select className="input" value={executeResult.new_status} onChange={e => setExecuteResult({ ...executeResult, new_status: e.target.value })}>
                    {['pending', 'passed', 'failed', 'blocked', 'not_applicable'].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="form-group" style={{ marginTop: 12 }}>
                  <label>Test Results / Notes</label>
                  <textarea className="input" rows={4} placeholder="Actual output, observations, deviations…" value={executeResult.results} onChange={e => setExecuteResult({ ...executeResult, results: e.target.value })} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowExecuteModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Recording…' : 'Record Results'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>Record Verification Test</h3><button className="btn btn-ghost" onClick={() => setShowModal(false)}>✕</button></div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                {error && <div className="alert-error mb-16">{error}</div>}
                <div className="form-grid">
                  <div className="form-group"><label>Test ID *</label><input className="input" placeholder="e.g., TEST-SIG-001-01" value={form.test_id} onChange={e => setForm({ ...form, test_id: e.target.value })} required /></div>
                  <div className="form-group">
                    <label>Test Type *</label>
                    <select className="input" value={form.test_type} onChange={e => setForm({ ...form, test_type: e.target.value })}>
                      {TEST_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
                    </select>
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label>Linked Requirement *</label>
                    <select className="input" value={form.requirement_id} onChange={e => setForm({ ...form, requirement_id: e.target.value })} required>
                      <option value="">Select requirement…</option>
                      {requirements.map(r => <option key={r.id} value={r.id}>{r.requirement_id}: {r.title}</option>)}
                    </select>
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label>Test Description *</label>
                    <textarea className="input" rows={3} placeholder="What does this test verify?" value={form.test_description} onChange={e => setForm({ ...form, test_description: e.target.value })} required />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label>Expected Results</label>
                    <textarea className="input" rows={2} placeholder="What is the expected outcome?" value={form.expected_results} onChange={e => setForm({ ...form, expected_results: e.target.value })} />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label>Test Environment</label>
                    <input className="input" placeholder="Platform, configuration, versions" value={form.test_environment} onChange={e => setForm({ ...form, test_environment: e.target.value })} />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Creating…' : 'Create Test Record'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
