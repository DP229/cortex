import { useState, useEffect } from 'react'
import { Play, Shield, FileText } from 'lucide-react'
import { api } from '../utils/api'
import './QualificationPage.css'

interface EvidencePackage {
  evidence_id: string; generated_at: string; tool_class: string
  sil_target: string; qualification_status: string; total_checks: number
  passed_checks: number; failed_checks: number; signature?: string
}

export default function QualificationPage() {
  const [status, setStatus] = useState<any>(null)
  const [tor, setTor] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [evidence, setEvidence] = useState<EvidencePackage | null>(null)
  const [showTor, setShowTor] = useState(false)

  useEffect(() => { loadStatus() }, [])

  const loadStatus = async () => {
    setLoading(true)
    try {
      const [stat, torRes] = await Promise.allSettled([
        api.get('/v2/qualification/status'),
        api.get('/v2/qualification/tor'),
      ])
      if (stat.status === 'fulfilled') setStatus(stat.value)
      if (torRes.status === 'fulfilled') setTor(torRes.value?.tor || torRes.value?.content || JSON.stringify(torRes.value))
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const runQualification = async () => {
    setRunning(true)
    setError('')
    try {
      await api.post('/v2/qualification/run?sil_target=SIL2', {})
      await loadStatus()
      // Fetch evidence
      const ev = await api.get('/v2/qualification/evidence')
      setEvidence(ev)
    } catch (e: any) { setError(e.message) }
    finally { setRunning(false) }
  }

  const loadEvidence = async () => {
    try {
      const ev = await api.get('/v2/qualification/evidence')
      setEvidence(ev)
    } catch (e: any) { setError(e.message) }
  }

  return (
    <div className="qualification-page">
      <div className="page-header">
        <h1>T2 Qualification Dashboard</h1>
        <p>EN 50128 / EN 50716 Class T2 self-qualifying tool evidence</p>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="flex gap-16 mb-24" style={{ maxWidth: 600 }}>
        <button className="btn btn-primary" onClick={runQualification} disabled={running}>
          <Play size={14} /> {running ? 'Running Qualification…' : 'Run Qualification'}
        </button>
        <button className="btn btn-ghost" onClick={loadEvidence}><Shield size={14} /> Load Evidence</button>
        <button className="btn btn-ghost" onClick={() => setShowTor(!showTor)}><FileText size={14} /> {showTor ? 'Hide TOR' : 'View TOR'}</button>
      </div>

      {loading ? (
        <p className="text-muted text-sm">Loading qualification status…</p>
      ) : (
        <>
          {status && (
            <div className="card mb-16">
              <h3>Current Status</h3>
              <div className="detail-grid mt-12">
                <div><label>Tool Class</label><span className="badge badge-green">{status.tool_class || status.qualification_status}</span></div>
                {status.last_run && <div><label>Last Run</label><span>{new Date(status.last_run).toLocaleString()}</span></div>}
                {status.sil_target && <div><label>SIL Target</label><span>{status.sil_target}</span></div>}
                {status.qualification_status && <div><label>Status</label><span className={`badge ${status.qualification_status === 'passed' ? 'badge-green' : 'badge-amber'}`}>{status.qualification_status}</span></div>}
              </div>
            </div>
          )}

          {evidence && (
            <div className="card mb-16">
              <h3>Evidence Package</h3>
              <div className="detail-grid mt-12">
                <div><label>Evidence ID</label><code style={{ fontSize: 11 }}>{evidence.evidence_id?.slice(0, 20)}…</code></div>
                <div><label>Tool Class</label><span>{evidence.tool_class}</span></div>
                <div><label>SIL Target</label><span>{evidence.sil_target}</span></div>
                <div><label>Generated</label><span>{evidence.generated_at ? new Date(evidence.generated_at).toLocaleString() : '—'}</span></div>
                <div><label>Passed</label><span style={{ color: 'var(--green)' }}>{evidence.passed_checks} / {evidence.total_checks}</span></div>
                {evidence.failed_checks > 0 && <div><label>Failed</label><span style={{ color: 'var(--red)' }}>{evidence.failed_checks}</span></div>}
              </div>
              {evidence.signature && (
                <div style={{ marginTop: 12 }}>
                  <label>HMAC Signature</label>
                  <code style={{ fontSize: 10, wordBreak: 'break-all' }}>{evidence.signature.slice(0, 64)}…</code>
                </div>
              )}
            </div>
          )}

          {showTor && tor && (
            <div className="card">
              <h3>Test Objective Report (TOR)</h3>
              <pre className="tor-content">{typeof tor === 'string' ? tor : JSON.stringify(tor, null, 2)}</pre>
            </div>
          )}
        </>
      )}
    </div>
  )
}
