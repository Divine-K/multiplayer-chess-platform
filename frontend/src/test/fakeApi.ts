import { vi } from 'vitest'

export interface RecordedRequest {
  method: string
  path: string
  body: unknown
  token: string | null
}

type Reply = { status?: number; body?: unknown }
type Handler = (request: RecordedRequest) => Reply | Promise<Reply>

/**
 * Stands in for the backend at the `fetch` boundary, so the real API client, error handling and
 * auth headers all run. Routes are keyed "METHOD /path"; later definitions win.
 */
export function fakeApi(routes: Record<string, Handler | Reply> = {}) {
  const table = new Map<string, Handler | Reply>(Object.entries(routes))
  const requests: RecordedRequest[] = []

  vi.stubGlobal('fetch', async (input: string, init: RequestInit = {}) => {
    const url = new URL(input)
    const headers = (init.headers ?? {}) as Record<string, string>
    const request: RecordedRequest = {
      method: init.method ?? 'GET',
      path: url.pathname + url.search,
      body: init.body ? JSON.parse(String(init.body)) : undefined,
      token: headers.Authorization?.replace('Bearer ', '') ?? null,
    }
    requests.push(request)
    const route = table.get(`${request.method} ${request.path}`) ?? table.get(`${request.method} ${url.pathname}`)
    if (!route) throw new Error(`No fake route for ${request.method} ${request.path}`)
    const reply = typeof route === 'function' ? await route(request) : route
    const status = reply.status ?? 200
    return new Response(status === 204 ? null : JSON.stringify(reply.body ?? null), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })

  return {
    requests,
    on(key: string, route: Handler | Reply) {
      table.set(key, route)
    },
    calls: (key: string) => requests.filter((r) => `${r.method} ${r.path.split('?')[0]}` === key),
  }
}
