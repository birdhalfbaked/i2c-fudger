const DEFAULT_BASE_URL = ''

export function resolveBaseUrl() {
  // Same-origin by default. Override with VITE_API_BASE_URL for dev.
  return import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL
}

export async function apiGet(path) {
  const res = await fetch(`${resolveBaseUrl()}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return await res.json()
}

export async function apiPut(path, body) {
  const res = await fetch(`${resolveBaseUrl()}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`)
  return await res.json()
}

export async function apiPost(path, body = undefined) {
  const res = await fetch(`${resolveBaseUrl()}${path}`, {
    method: 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return await res.json()
}

export function makeWsUrl(path) {
  const base = resolveBaseUrl()
  const url = new URL(base || window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = path
  url.search = ''
  url.hash = ''
  return url.toString()
}

