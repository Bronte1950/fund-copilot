// Chat hook — submits a query, streams the SSE response, and tracks state.
// Components only see { submit, reset, status, streamingText, response, error }.
// All network calls go through client.js.

import { useState, useCallback, useRef } from 'react'
import { chatStream } from '../api/client'

/**
 * @returns {{
 *   submit: (query: string, filters?: object) => void,
 *   reset:  () => void,
 *   status: 'idle'|'loading'|'streaming'|'done'|'error',
 *   streamingText: string,
 *   response: object|null,
 *   error: string|null,
 * }}
 */
export function useChat() {
  const [status, setStatus] = useState('idle')
  const [streamingText, setStreamingText] = useState('')
  const [response, setResponse] = useState(null)
  const [error, setError] = useState(null)
  const abortedRef = useRef(false)

  const submit = useCallback(async (query, filters = {}) => {
    if (!query.trim()) return

    abortedRef.current = false
    setStatus('loading')
    setStreamingText('')
    setResponse(null)
    setError(null)

    try {
      setStatus('streaming')
      let accumulated = ''

      for await (const event of chatStream(query, filters)) {
        if (abortedRef.current) break

        if (event.type === 'token') {
          accumulated += event.data.text
          setStreamingText(accumulated)
        } else if (event.type === 'done') {
          setResponse(event.data)
          setStatus('done')
        } else if (event.type === 'error') {
          setError(event.data.error ?? 'Unknown error')
          setStatus('error')
        }
      }
    } catch (err) {
      if (!abortedRef.current) {
        setError(err.message)
        setStatus('error')
      }
    }
  }, [])

  const reset = useCallback(() => {
    abortedRef.current = true
    setStatus('idle')
    setStreamingText('')
    setResponse(null)
    setError(null)
  }, [])

  return { submit, reset, status, streamingText, response, error }
}
