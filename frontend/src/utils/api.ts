const BASE = '/api'

async function handleRes(res: Response) {
  if (res.status === 401) {
    // Cookie expired or invalid — redirect to login
    window.location.href = '/login'
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
    fetch(`${BASE}${path}`, { credentials: 'include' })
      .then(handleRes),
  post: (path: string, body: object) =>
    fetch(`${BASE}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(handleRes),
  put: (path: string, body?: object) =>
    fetch(`${BASE}${path}`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
      .then(handleRes),
  patch: (path: string, body: object) =>
    fetch(`${BASE}${path}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(handleRes),
  del: (path: string) =>
    fetch(`${BASE}${path}`, {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(handleRes),
}
