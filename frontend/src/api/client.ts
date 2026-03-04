const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'
const ADMIN_TOKEN_KEY = 'admin_token'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

function normalizePath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`
}

async function parseError(response: Response): Promise<never> {
  const body = await response.text()
  throw new Error(body || `请求失败: ${response.status}`)
}

async function request<T>(method: HttpMethod, path: string, body?: unknown): Promise<T> {
  const normalizedPath = normalizePath(path)
  const url = `${API_BASE_URL}${normalizedPath}`
  const parsedUrl = new URL(url, window.location.origin)
  const token = window.localStorage.getItem(ADMIN_TOKEN_KEY) ?? ''
  const shouldAttachAdminToken = parsedUrl.pathname.startsWith('/api/') && !parsedUrl.pathname.startsWith('/v1/')

  const response = await fetch(url, {
    method,
    headers: {
      Accept: 'application/json',
      ...(shouldAttachAdminToken && token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {})
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {})
  })

  if (!response.ok) {
    await parseError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>('GET', path)
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>('POST', path, body)
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>('PUT', path, body)
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>('PATCH', path, body)
}

export async function apiDelete(path: string): Promise<void> {
  await request<void>('DELETE', path)
}
