// useEval — manage eval run lifecycle, live progress, results, and history

import { useState, useRef, useCallback, useEffect } from 'react'

const API = 'http://localhost:8010'

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export function useEval() {
  const [status, setStatus] = useState('idle')   // idle | loading | running | done | error
  const [summary, setSummary] = useState(null)
  const [results, setResults] = useState([])
  const [error, setError] = useState(null)
  const [progress, setProgress] = useState(null) // live run state from /eval/progress
  const [history, setHistory] = useState([])     // all past run summaries

  const pollRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const data = await apiFetch('/eval/results')
      setHistory(data.runs)
    } catch {
      // non-fatal — history panel stays empty
    }
  }, [])

  // Auto-load history on mount
  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const fetchLatest = useCallback(async () => {
    const data = await apiFetch('/eval/results/latest')
    setSummary(data.summary)
    setResults(data.results)
  }, [])

  const startRun = useCallback(async (topK = 10) => {
    setStatus('running')
    setError(null)
    setProgress(null)

    try {
      await apiFetch(`/eval/run?top_k=${topK}`, { method: 'POST' })
    } catch (err) {
      setStatus('error')
      setError(err.message)
      return
    }

    // Poll /eval/progress every 2s for live per-question updates
    pollRef.current = setInterval(async () => {
      try {
        const prog = await apiFetch('/eval/progress')
        setProgress(prog)

        if (prog.status === 'done') {
          stopPolling()
          setStatus('done')
          setSummary(null) // will be loaded below
          await fetchLatest()
          await loadHistory()  // refresh history after run completes
        } else if (prog.status === 'error') {
          stopPolling()
          setStatus('error')
          setError(prog.error || 'Unknown error')
        }
      } catch (err) {
        stopPolling()
        setStatus('error')
        setError(err.message)
      }
    }, 2000)
  }, [fetchLatest, loadHistory, stopPolling])

  const loadLatest = useCallback(async () => {
    setStatus('loading')
    setError(null)
    try {
      await fetchLatest()
      setStatus('done')
    } catch (err) {
      setStatus('error')
      setError(err.message)
    }
  }, [fetchLatest])

  return { status, summary, results, error, progress, history, startRun, loadLatest }
}
