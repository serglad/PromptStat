const TOKEN_KEY = 'promptstat_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
  }
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const resp = await fetch(path, { ...options, headers })
  let body = null
  try { body = await resp.json() } catch { /* empty */ }
  if (!resp.ok) {
    const code = body?.error_code || 'UNKNOWN'
    const message = body?.message || `Ошибка ${resp.status}`
    if (resp.status === 401) setToken(null)
    throw new ApiError(code, message)
  }
  return body
}

export const api = {
  register: (email, password) =>
    request('/api/v1/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email, password) =>
    request('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  listConnections: () => request('/api/v1/connections'),
  createConnection: (data) =>
    request('/api/v1/connections', { method: 'POST', body: JSON.stringify(data) }),
  deleteConnection: (id) =>
    request(`/api/v1/connections/${id}`, { method: 'DELETE' }),
  getSchema: (id, refresh = false) =>
    request(`/api/v1/connections/${id}/schema?refresh=${refresh}`),
  query: (connectionId, prompt, conversationId) =>
    request('/api/v1/query', {
      method: 'POST',
      body: JSON.stringify({
        connection_id: connectionId,
        prompt,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      }),
    }),
  history: (connectionId) =>
    request(`/api/v1/history${connectionId ? `?connection_id=${connectionId}` : ''}`),
}
