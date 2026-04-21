const BASE = '/api'

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('cortex_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function handleRes(res: Response) {
  if (res.status === 401) {
    localStorage.removeItem('cortex_token')
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  get: (path: string) =>
    fetch(`${BASE}${path}`, { headers: { 'Content-Type': 'application/json', ...authHeaders() } })
      .then(handleRes),
  post: (path: string, body: object) =>
    fetch(`${BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify(body) })
      .then(handleRes),
  put: (path: string, body?: object) =>
    fetch(`${BASE}${path}`, { method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() }, ...(body ? { body: JSON.stringify(body) } : {}) })
      .then(handleRes),
  del: (path: string) =>
    fetch(`${BASE}${path}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json', ...authHeaders() } })
      .then(handleRes),
}
