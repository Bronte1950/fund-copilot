// Phase 4: REST + SSE client for the Fund Copilot API
// All component API calls go through hooks (useChat, useDocuments) — never directly.

const BASE = import.meta.env.VITE_API_BASE ?? ''

// TODO Phase 4: implement retrieve(), chat() with SSE, listDocs()
export async function fetchHealth() {
  const resp = await fetch(`${BASE}/health`)
  if (!resp.ok) throw new Error(`Health check failed: ${resp.status}`)
  return resp.json()
}
