import { useState, useEffect } from 'react'
import { Search, AlertTriangle, CheckCircle, Clock, Box, FileText, Database, CheckSquare } from 'lucide-react'
import './Dashboard.css'

interface Stats {
  total_assets: number
  total_requirements: number
  total_soups: number
  total_test_records: number
  requirements_approved: number
  requirements_pending: number
  soups_approved: number
  soups_candidate: number
  tests_passed: number
  tests_failed: number
  tests_pending: number
  uptime: string
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({
    total_assets: 0, total_requirements: 0, total_soups: 0, total_test_records: 0,
    requirements_approved: 0, requirements_pending: 0,
    soups_approved: 0, soups_candidate: 0,
    tests_passed: 0, tests_failed: 0, tests_pending: 0,
    uptime: '--',
  })
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    Promise.allSettled([
      fetch('/api/v1/assets', { credentials: 'include' }).then(r => r.json()).catch(() => []),
      fetch('/api/v1/requirements', { credentials: 'include' }).then(r => r.json()).catch(() => []),
      fetch('/api/v1/soups', { credentials: 'include' }).then(r => r.json()).catch(() => []),
      fetch('/api/v1/test-records', { credentials: 'include' }).then(r => r.json()).catch(() => []),
      fetch('/api/health', { credentials: 'include' }).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([assetsRes, reqsRes, soupsRes, testsRes, healthRes]) => {
      const assets: any[] = assetsRes.status === 'fulfilled' ? (assetsRes.value ?? []) : []
      const reqs: any[] = reqsRes.status === 'fulfilled' ? (reqsRes.value ?? []) : []
      const soups: any[] = soupsRes.status === 'fulfilled' ? (soupsRes.value ?? []) : []
      const tests: any[] = testsRes.status === 'fulfilled' ? (testsRes.value ?? []) : []
      const healthData = healthRes.status === 'fulfilled' ? healthRes.value : null

      setStats({
        total_assets: assets.length,
        total_requirements: reqs.length,
        total_soups: soups.length,
        total_test_records: tests.length,
        requirements_approved: reqs.filter((r: any) => r.status === 'approved').length,
        requirements_pending: reqs.filter((r: any) => ['draft', 'review'].includes(r.status)).length,
        soups_approved: soups.filter((s: any) => s.status === 'approved').length,
        soups_candidate: soups.filter((s: any) => s.status === 'candidate').length,
        tests_passed: tests.filter((t: any) => t.status === 'passed').length,
        tests_failed: tests.filter((t: any) => ['failed', 'blocked'].includes(t.status)).length,
        tests_pending: tests.filter((t: any) => t.status === 'pending').length,
        uptime: healthData?.status === 'healthy' ? 'operational' : 'degraded',
      })
      setLoading(false)
    })
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (search.trim()) {
      window.location.href = `/requirements?q=${encodeURIComponent(search)}`
    }
  }

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Railway Safety Compliance Platform — EN 50128 Class B · IEC 62443</p>
      </div>

      <form onSubmit={handleSearch} className="search-bar">
        <Search size={16} className="search-icon" />
        <input
          className="input search-input"
          placeholder="Search requirements…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button type="submit" className="btn btn-primary">Search</button>
      </form>

      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-card__label"><Box size={12} style={{ display: 'inline', marginRight: 4 }} />Railway Assets</div>
          <div className="stat-card__value">{loading ? '…' : stats.total_assets}</div>
          <div className="stat-card__sub">registered infrastructure</div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label"><FileText size={12} style={{ display: 'inline', marginRight: 4 }} />Requirements</div>
          <div className="stat-card__value">{loading ? '…' : stats.total_requirements}</div>
          <div className="stat-card__sub">
            {loading ? '' : (
              <span style={{ color: 'var(--green)' }}>{stats.requirements_approved} approved</span>
            )}
            {loading ? '' : (
              <span> · <span style={{ color: 'var(--amber)' }}>{stats.requirements_pending} pending</span></span>
            )}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label"><Database size={12} style={{ display: 'inline', marginRight: 4 }} />SOUPs</div>
          <div className="stat-card__value">{loading ? '…' : stats.total_soups}</div>
          <div className="stat-card__sub">
            {loading ? '' : (
              <span style={{ color: 'var(--green)' }}>{stats.soups_approved} approved</span>
            )}
            {loading ? '' : (
              <span> · <span style={{ color: 'var(--amber)' }}>{stats.soups_candidate} candidate</span></span>
            )}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label"><CheckSquare size={12} style={{ display: 'inline', marginRight: 4 }} />Test Records</div>
          <div className="stat-card__value">{loading ? '…' : stats.total_test_records}</div>
          <div className="stat-card__sub">
            {loading ? '' : (
              <span style={{ color: 'var(--green)' }}>{stats.tests_passed} passed</span>
            )}
            {loading ? '' : (
              <span> · <span style={{ color: 'var(--red)' }}>{stats.tests_failed} failed/blocked</span></span>
            )}
            {loading ? '' : (
              <span> · {stats.tests_pending} pending</span>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>System Status</h2>
          <span className={`badge ${stats.uptime === 'operational' ? 'badge-green' : 'badge-amber'}`}>
            {loading ? 'checking…' : stats.uptime}
          </span>
        </div>
        <div className="flex gap-16 mt-16">
          <div className="flex-col gap-8" style={{ flex: 1 }}>
            <div className="flex items-center gap-8">
              <CheckCircle size={14} style={{ color: 'var(--green)' }} />
              <span className="text-sm">EN 50128 Class B compliance mode</span>
            </div>
            <div className="flex items-center gap-8">
              <CheckCircle size={14} style={{ color: 'var(--green)' }} />
              <span className="text-sm">IEC 62443 P2 cybersecurity framework</span>
            </div>
            <div className="flex items-center gap-8">
              <CheckCircle size={14} style={{ color: 'var(--green)' }} />
              <span className="text-sm">10-year audit retention active</span>
            </div>
          </div>
          <div className="flex-col gap-8" style={{ flex: 1 }}>
            <div className="flex items-center gap-8">
              <Clock size={14} style={{ color: 'var(--text-muted)' }} />
              <span className="text-sm text-muted">All timestamps in UTC</span>
            </div>
            <div className="flex items-center gap-8">
              <AlertTriangle size={14} style={{ color: stats.requirements_pending > 0 ? 'var(--amber)' : 'var(--text-muted)' }} />
              <span className="text-sm text-muted">
                {stats.requirements_pending > 0
                  ? `${stats.requirements_pending} requirements need approval`
                  : 'No pending approvals'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Quick Actions</h2>
        </div>
        <div className="flex gap-12 mt-16">
          <a href="/requirements" className="btn btn-primary">+ New Requirement</a>
          <a href="/assets" className="btn btn-ghost">+ Register Asset</a>
          <a href="/soups" className="btn btn-ghost">+ Register SOUP</a>
          <a href="/tests" className="btn btn-ghost">+ Record Test</a>
        </div>
      </div>
    </div>
  )
}
