// REST + SSE client for the Fund Copilot API.
// All API calls go through hooks (useChat, useDocuments) — never call these directly from components.

const BASE = import.meta.env.VITE_API_BASE ?? ''

// ── Health ────────────────────────────────────────────────────────────────────

export async function fetchHealth() {
  const resp = await fetch(`${BASE}/health`)
  if (!resp.ok) throw new Error(`Health check failed: ${resp.status}`)
  return resp.json()
}

// ── Documents ─────────────────────────────────────────────────────────────────

export async function listDocs(filters = {}) {
  const params = new URLSearchParams()
  if (filters.provider) params.set('provider', filters.provider)
  if (filters.doc_type) params.set('doc_type', filters.doc_type)
  const qs = params.toString()
  const resp = await fetch(`${BASE}/docs${qs ? `?${qs}` : ''}`)
  if (!resp.ok) throw new Error(`Failed to fetch documents: ${resp.status}`)
  return resp.json()
}

// ── Chat — SSE streaming ──────────────────────────────────────────────────────

/**
 * Async generator that streams SSE events from POST /chat/stream.
 *
 * Yields objects with shape:
 *   { type: 'token', data: { text: string } }
 *   { type: 'done',  data: ChatResponse }
 *   { type: 'error', data: { error: string } }
 */
export async function* chatStream(query, filters = {}) {
  const body = JSON.stringify({
    query,
    top_k: 10,
    provider: filters.provider ?? null,
    doc_type: filters.doc_type ?? null,
    isin: filters.isin ?? null,
  })

  const resp = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })

  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`Chat request failed (${resp.status}): ${text}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by double newline
    const parts = buffer.split('\n\n')
    buffer = parts.pop() // last element may be incomplete

    for (const part of parts) {
      let eventType = 'message'
      let dataLine = ''

      for (const line of part.split('\n')) {
        if (line.startsWith('event: ')) eventType = line.slice(7).trim()
        else if (line.startsWith('data: ')) dataLine = line.slice(6).trim()
      }

      if (!dataLine) continue
      try {
        yield { type: eventType, data: JSON.parse(dataLine) }
      } catch {
        // skip malformed lines
      }
    }
  }
}
