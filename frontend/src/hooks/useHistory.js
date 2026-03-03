// Query history — persists the last 50 queries + responses in localStorage.

import { useState, useCallback } from 'react'

const STORAGE_KEY = 'fund_copilot_history'
const MAX_ENTRIES = 50

function load() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
  } catch {
    return []
  }
}

function save(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // localStorage full — ignore
  }
}

/**
 * @returns {{
 *   history: Array<{id, timestamp, query, filters, response}>,
 *   addEntry: (query, filters, response) => void,
 *   clearHistory: () => void,
 * }}
 */
export function useHistory() {
  const [history, setHistory] = useState(load)

  const addEntry = useCallback((query, filters, response) => {
    setHistory((prev) => {
      const entry = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        query,
        filters,
        response,
      }
      const next = [entry, ...prev].slice(0, MAX_ENTRIES)
      save(next)
      return next
    })
  }, [])

  const clearHistory = useCallback(() => {
    setHistory([])
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  return { history, addEntry, clearHistory }
}
