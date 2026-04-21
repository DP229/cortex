import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import './Consent.css'

interface Consent {
  id: string
  patient_id: string
  consent_type: string
  status: string
  granted_at: string | null
  expires_at: string | null
}

export default function Consent() {
  const [records, setRecords] = useState<Consent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadRecords() }, [])

  const loadRecords = () => {
    setLoading(true)
    api.get('/consent')
      .then(d => setRecords(d.consents ?? d))
      .catch(() => setRecords([]))
      .finally(() => setLoading(false))
  }

  const revoke = async (id: string) => {
    if (!confirm('Revoke this consent record?')) return
    try {
      await api.post(`/consent/${id}/revoke`, {})
      loadRecords()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const statusColour = (s: string) =>
    s === 'granted' ? 'var(--green)' : s === 'denied' ? 'var(--red)' : 'var(--amber)'

  return (
    <div className="consent">
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Consent Management</h1>
          <p>HIPAA consent tracking — all actions logged.</p>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h2>Consent Records</h2></div>
        {loading ? <p className="text-muted text-sm">Loading…</p>
         : records.length === 0 ? <p className="text-muted text-sm">No consent records found.</p>
         : (
           <div className="table-wrap">
             <table>
               <thead>
                 <tr><th>Patient ID</th><th>Type</th><th>Status</th><th>Granted</th><th>Expires</th><th>Action</th></tr>
               </thead>
               <tbody>
                 {records.map(r => (
                   <tr key={r.id}>
                     <td className="text-accent">{r.patient_id?.slice(0, 8)}…</td>
                     <td className="text-muted text-sm">{r.consent_type}</td>
                     <td>
                       <span className="badge badge-purple" style={{ color: statusColour(r.status), borderColor: statusColour(r.status) }}>
                         {r.status}
                       </span>
                     </td>
                     <td className="text-sm">{r.granted_at ? new Date(r.granted_at).toLocaleDateString() : '—'}</td>
                     <td className="text-sm">{r.expires_at ? new Date(r.expires_at).toLocaleDateString() : '—'}</td>
                     <td>
                       {r.status === 'granted' && (
                         <button className="btn btn-ghost btn-sm" onClick={() => revoke(r.id)}>Revoke</button>
                       )}
                     </td>
                   </tr>
                 ))}
               </tbody>
             </table>
           </div>
         )
        }
      </div>
    </div>
  )
}
