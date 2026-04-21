import { useState, useEffect } from 'react'
import { api } from '../utils/api'
import './Patients.css'

interface Patient {
  id: string
  mrn: string
  full_name_encrypted: string
  date_of_birth: string
  gender: string
  created_at: string
}

export default function Patients() {
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')

  useEffect(() => { loadPatients() }, [])

  const loadPatients = () => {
    setLoading(true)
    api.get('/patients')
      .then(d => setPatients(d.patients ?? d))
      .catch(() => setPatients([]))
      .finally(() => setLoading(false))
  }

  const filtered = patients.filter(p =>
    p.mrn.includes(query) || p.full_name_encrypted.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div className="patients">
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Patients</h1>
          <p>PHI records — access logged to audit trail.</p>
        </div>
      </div>

      <div className="search-bar" style={{ marginBottom: 16 }}>
        <input className="input" placeholder="Search MRN or name…" value={query} onChange={e => setQuery(e.target.value)} />
      </div>

      <div className="card">
        <div className="card-header"><h2>Patient List</h2></div>
        {loading ? <p className="text-muted text-sm">Loading…</p>
         : filtered.length === 0 ? <p className="text-muted text-sm">No patients found.</p>
         : (
           <div className="table-wrap">
             <table>
               <thead>
                 <tr><th>MRN</th><th>Encrypted Name</th><th>DOB</th><th>Gender</th></tr>
               </thead>
               <tbody>
                 {filtered.map(p => (
                   <tr key={p.id}>
                     <td className="text-accent">{p.mrn}</td>
                     <td className="text-muted text-sm" style={{ fontFamily: 'monospace', fontSize: 11 }}>
                       {p.full_name_encrypted.slice(0, 24)}…
                     </td>
                     <td>{p.date_of_birth ?? '—'}</td>
                     <td className="text-muted text-sm">{p.gender ?? '—'}</td>
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
