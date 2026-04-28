import { useState, useEffect } from 'react'
import { Plus, Search } from 'lucide-react'
import { api } from '../utils/api'
import './AssetsPage.css'

interface RailwayAsset {
  id: string
  asset_id: string
  asset_type: string
  name: string
  description?: string
  location?: string
  safety_class: string
  sil_level: string
  is_active: boolean
  parent_asset_id?: string
  created_at: string
}

const ASSET_TYPES = [
  'rolling_stock', 'track', 'signal', 'switch', 'bridge', 'tunnel',
  'station', 'overhead_line', 'power_supply', 'control_center',
  'communication', 'depot', 'other',
]

const SAFETY_CLASSES = ['class_a', 'class_b', 'class_c']
const SIL_LEVELS = ['sil0', 'sil1', 'sil2', 'sil3', 'sil4']

export default function AssetsPage() {
  const [assets, setAssets] = useState<RailwayAsset[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [selectedAsset, setSelectedAsset] = useState<RailwayAsset | null>(null)
  const [form, setForm] = useState({
    asset_id: '', asset_type: 'rolling_stock', name: '', description: '',
    location: '', safety_class: 'class_b', sil_level: 'sil2', parent_asset_id: '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadAssets()
  }, [])

  const loadAssets = async () => {
    setLoading(true)
    try {
      const data = await api.get('/v1/assets')
      setAssets(Array.isArray(data) ? data : (data.assets ?? []))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const filtered = assets.filter(a =>
    !search || a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.asset_id.toLowerCase().includes(search.toLowerCase())
  )

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload: any = { ...form }
      if (!payload.parent_asset_id) delete payload.parent_asset_id
      await api.post('/v1/assets', payload)
      setShowModal(false)
      setForm({ asset_id: '', asset_type: 'rolling_stock', name: '', description: '', location: '', safety_class: 'class_b', sil_level: 'sil2', parent_asset_id: '' })
      loadAssets()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Soft-delete this asset? It will be retained for EN 50128 compliance.')) return
    try {
      await api.del(`/v1/assets/${id}`)
      loadAssets()
      setSelectedAsset(null)
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="assets-page">
      <div className="page-header">
        <h1>Railway Assets</h1>
        <p>EN 50128 asset hierarchy and safety classification</p>
      </div>

      <div className="flex justify-between items-center gap-12 mb-24">
        <div className="search-bar" style={{ flex: 1, maxWidth: 400 }}>
          <Search size={16} className="search-icon" />
          <input
            className="input search-input"
            placeholder="Search by name or asset ID…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={16} /> Register Asset
        </button>
      </div>

      {error && <div className="alert-error mb-16">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Asset ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Safety Class</th>
                <th>SIL Level</th>
                <th>Location</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="text-muted text-sm">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} className="text-muted text-sm">No assets found. Register your first asset.</td></tr>
              ) : filtered.map(asset => (
                <tr key={asset.id} className="clickable-row" onClick={() => setSelectedAsset(asset)}>
                  <td><code style={{ fontSize: 12 }}>{asset.asset_id}</code></td>
                  <td>{asset.name}</td>
                  <td><span className="badge badge-purple">{asset.asset_type.replace('_', ' ')}</span></td>
                  <td><span className="badge badge-purple">{asset.safety_class}</span></td>
                  <td><span className={`badge ${asset.sil_level === 'sil3' || asset.sil_level === 'sil4' ? 'badge-red' : asset.sil_level === 'sil2' ? 'badge-amber' : 'badge-green'}`}>{asset.sil_level.toUpperCase()}</span></td>
                  <td className="text-muted text-sm">{asset.location || '—'}</td>
                  <td><span className={`badge ${asset.is_active ? 'badge-green' : 'badge-red'}`}>{asset.is_active ? 'active' : 'inactive'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedAsset && (
        <div className="modal-overlay" onClick={() => setSelectedAsset(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{selectedAsset.name}</h3>
              <button className="btn btn-ghost" onClick={() => setSelectedAsset(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><label>Asset ID</label><span><code>{selectedAsset.asset_id}</code></span></div>
                <div><label>Type</label><span>{selectedAsset.asset_type}</span></div>
                <div><label>Safety Class</label><span>{selectedAsset.safety_class}</span></div>
                <div><label>SIL Level</label><span>{selectedAsset.sil_level.toUpperCase()}</span></div>
                <div><label>Location</label><span>{selectedAsset.location || '—'}</span></div>
                <div><label>Status</label><span>{selectedAsset.is_active ? 'active' : 'inactive'}</span></div>
                <div><label>Created</label><span>{new Date(selectedAsset.created_at).toLocaleString()}</span></div>
              </div>
              {selectedAsset.description && (
                <div style={{ marginTop: 16 }}>
                  <label>Description</label>
                  <p className="text-sm" style={{ marginTop: 4 }}>{selectedAsset.description}</p>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-danger" onClick={() => handleDelete(selectedAsset.id)}>
                Soft-Delete Asset
              </button>
            </div>
          </div>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Register Railway Asset</h3>
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                {error && <div className="alert-error mb-16">{error}</div>}
                <div className="form-grid">
                  <div className="form-group">
                    <label>Asset ID *</label>
                    <input className="input" placeholder="e.g., SIG-001" value={form.asset_id} onChange={e => setForm({ ...form, asset_id: e.target.value })} required />
                  </div>
                  <div className="form-group">
                    <label>Asset Type *</label>
                    <select className="input" value={form.asset_type} onChange={e => setForm({ ...form, asset_type: e.target.value })}>
                      {ASSET_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Name *</label>
                    <input className="input" placeholder="Descriptive name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
                  </div>
                  <div className="form-group">
                    <label>Location</label>
                    <input className="input" placeholder="GPS or line/station" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
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
                  <div className="form-group" style={{ gridColumn: '1/-1' }}>
                    <label>Description</label>
                    <textarea className="input" rows={3} placeholder="Asset description and operational context" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Registering…' : 'Register Asset'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
