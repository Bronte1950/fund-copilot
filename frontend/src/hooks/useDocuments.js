// Documents hook — fetches the indexed document list with optional filters.
// Refetches automatically when provider or doc_type changes.

import { useState, useEffect } from 'react'
import { listDocs } from '../api/client'

/**
 * @param {string|null} provider
 * @param {string|null} docType
 * @returns {{ documents: object[], loading: boolean, error: string|null, refetch: () => void }}
 */
export function useDocuments(provider = null, docType = null) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tick, setTick] = useState(0)

  const refetch = () => setTick((t) => t + 1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    listDocs({ provider, doc_type: docType })
      .then((docs) => { if (!cancelled) setDocuments(docs) })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [provider, docType, tick])

  return { documents, loading, error, refetch }
}
