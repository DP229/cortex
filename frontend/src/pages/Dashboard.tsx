import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import './Dashboard.css'

interface Stats {
  queries_today: number
  total_entries: number
  avg_latency: number
  uptime: string
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({ queries_today: 0, total_entries: 0, avg_latency: 0, uptime: '--' })
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetch('/api/memory/stats')
      .then(r => r.json())
      .then(data => {
        setStats(s => ({
          ...s,
          total_entries: data.total_memories ?? 0,
          uptime: 'running',
        }))
        setLoading(false)
      })
      .catch(() => {
        setStats(s => ({ ...s, uptime: 'checking…' }))
        setLoading(false)
      })

    fetch('/api/health')
      .then(r => r.json())
      .then(data => {
        if (data.status === 'healthy') {
          setStats(s => ({ ...s, uptime: 'operational' }))
        }
      })
      .catch(() => {})
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (search.trim()) {
      window.location.href = `/knowledge?q=${encodeURIComponent(search)}`
    }
  }

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Welcome to Cortex — your compliance-ready AI knowledge base.</p>
      </div>

      {/* Quick search */}
      <form onSubmit={handleSearch} className="search-bar">
        <Search size={16} className="search-icon" />
        <input
          className="input search-input"
          placeholder="Search knowledge base…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button type="submit" className="btn btn-primary">Search</button>
      </form>

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-card__label">Queries Today</div>
          <div className="stat-card__value">{loading ? '…' : stats.queries_today}</div>
          <div className="stat-card__sub">session interactions</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Knowledge Entries</div>
          <div className="stat-card__value">{loading ? '…' : stats.total_entries}</div>
          <div className="stat-card__sub">indexed documents</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Avg Latency</div>
          <div className="stat-card__value">{loading ? '…' : stats.avg_latency ? `${stats.avg_latency}ms` : '--'}</div>
          <div className="stat-card__sub">per query</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">System Status</div>
          <div className="stat-card__value" style={{ fontSize: 18, color: 'var(--green)' }}>
            ● {loading ? '…' : stats.uptime}
          </div>
          <div className="stat-card__sub">health check</div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card">
        <div className="card-header">
          <h2>Recent Activity</h2>
        </div>
        {loading ? (
          <p className="text-muted text-sm">Connecting to Cortex API…</p>
        ) : (
          <p className="text-muted text-sm">No recent activity. Start by querying the agent or adding a knowledge entry.</p>
        )}
      </div>
    </div>
  )
}