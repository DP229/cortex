import { useState } from 'react'
import { Search, Plus, Tag } from 'lucide-react'
import './KnowledgeBase.css'

interface Entry {
  id: string
  content: string
  category: string
  tags: string[]
  citations: number
}

const MOCK_ENTRIES: Entry[] = [
  { id: '1', content: 'IEC 62304:2009 — Medical device software life cycle processes require risk management at each stage.', category: 'standard', tags: ['IEC 62304', 'medical'], citations: 4 },
  { id: '2', content: 'HIPAA Security Rule requires encryption of PHI at rest and in transit using AES-256 or equivalent.', category: 'regulation', tags: ['HIPAA', 'encryption', 'PHI'], citations: 7 },
  { id: '3', content: 'FDA 21 CFR Part 11 defines requirements for electronic records and signatures in regulated systems.', category: 'regulation', tags: ['FDA', '21CFR', 'e-signatures'], citations: 3 },
  { id: '4', content: 'EN 50128 SIL 0–4 classification defines software safety integrity levels for railway systems.', category: 'standard', tags: ['EN 50128', 'SIL', 'railway'], citations: 2 },
  { id: '5', content: 'ISO 14971:2019 risk management framework for medical devices — hazard identification, risk assessment, risk control.', category: 'standard', tags: ['ISO 14971', 'risk', 'medical'], citations: 5 },
]

export default function KnowledgeBase() {
  const [query, setQuery] = useState('')
  const [entries] = useState(MOCK_ENTRIES)
  const [selectedCat, setSelectedCat] = useState<string | null>(null)

  const filtered = entries.filter(e =>
    (e.content.toLowerCase().includes(query.toLowerCase()) || e.tags.some(t => t.toLowerCase().includes(query.toLowerCase())))
    && (!selectedCat || e.category === selectedCat)
  )

  const categories = Array.from(new Set(entries.map(e => e.category)))

  return (
    <div className="kb">
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Knowledge Base</h1>
          <p>{entries.length} entries indexed. Citations are cryptographically verifiable.</p>
        </div>
        <button className="btn btn-primary"><Plus size={14} /> Add Entry</button>
      </div>

      {/* Search + filters */}
      <div className="kb-toolbar">
        <div className="search-bar" style={{ flex: 1 }}>
          <Search size={16} className="search-icon" />
          <input className="input search-input" placeholder="Search entries or tags…" value={query} onChange={e => setQuery(e.target.value)} />
        </div>
        <div className="kb-filters">
          <button className={`badge ${selectedCat === null ? 'badge-purple' : 'badge-ghost'}`} onClick={() => setSelectedCat(null)}>All</button>
          {categories.map(c => (
            <button key={c} className={`badge ${selectedCat === c ? 'badge-purple' : 'badge-ghost'}`} onClick={() => setSelectedCat(c === selectedCat ? null : c)}>
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="kb-list">
        {filtered.length === 0 ? (
          <div className="card"><p className="text-muted text-sm">No entries match your search.</p></div>
        ) : filtered.map(e => (
          <div key={e.id} className="card kb-entry">
            <p className="kb-entry__text">{e.content}</p>
            <div className="kb-entry__footer">
              <span className="badge badge-amber">{e.category}</span>
              <div className="kb-tags">
                {e.tags.map(t => <span key={t} className="kb-tag"><Tag size={10} /> {t}</span>)}
              </div>
              <span className="text-muted text-sm" style={{ marginLeft: 'auto' }}>⬗ {e.citations} citations</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}