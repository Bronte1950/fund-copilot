// Phase 4: chat hook — submits query, streams response via SSE, tracks state
import { useState } from 'react'

// TODO Phase 4: implement useChat() returning { submit, answer, citations, status }
export function useChat() {
  const [status, setStatus] = useState('idle')
  return { status }
}
