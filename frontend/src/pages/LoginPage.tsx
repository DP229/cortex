import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import './LoginPage.css'

export default function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) return
    setLoading(true)
    setError('')
    try {
      await login(email, password)
      window.location.href = '/'
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-bg">
      <div className="login-card">
        <div className="login-logo">🚄 Cortex</div>
        <p className="login-subtitle">Railway Safety Compliance Platform</p>
        <p className="login-subtitle" style={{ fontSize: 12, marginTop: 4 }}>
          EN 50128 Class B · IEC 62443
        </p>
        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="login-error">{error}</div>}
          <input
            className="input"
            type="email"
            placeholder="Email address"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
          <input
            className="input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
          />
          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
        <p className="login-note">
          Roles: <strong>admin</strong> · <strong>safety_engineer</strong> · <strong>auditor</strong> · <strong>viewer</strong>
        </p>
      </div>
    </div>
  )
}
