import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

interface User {
  id: string
  email: string
  full_name: string
  role: string
}

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Validate existing session by calling /api/auth/me
    // The access_token cookie is sent automatically by the browser
    fetch('/api/auth/me', {
      credentials: 'include',  // Required for httpOnly cookie to be sent
    })
      .then(res => {
        if (res.ok) return res.json()
        return null
      })
      .then(data => {
        if (data) {
          setUser({
            id: data.id ?? data.user_id,
            email: data.email,
            full_name: data.full_name ?? '',
            role: data.role,
          })
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'include',  // Receive httpOnly cookie
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }))
      throw new Error(err.detail || 'Login failed')
    }
    const data = await res.json()
    // Backend sets httpOnly cookie; fetch /me to get user details
    const meRes = await fetch('/api/auth/me', { credentials: 'include' })
    if (meRes.ok) {
      const meData = await meRes.json()
      setUser({
        id: meData.id ?? meData.user_id,
        email: meData.email,
        full_name: meData.full_name ?? '',
        role: meData.role,
      })
    } else {
      // Fallback: populate from login response
      setUser({ id: data.user_id, email, full_name: '', role: data.role })
    }
  }

  const logout = async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',  // Send + clear httpOnly cookie
      })
    } catch {}
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}
