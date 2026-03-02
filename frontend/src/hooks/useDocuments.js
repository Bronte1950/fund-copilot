// Phase 4: documents hook — fetches indexed document list with pagination/filters
import { useState, useEffect } from 'react'

// TODO Phase 4: implement useDocuments() returning { documents, loading, error }
export function useDocuments() {
  const [documents, setDocuments] = useState([])
  return { documents, loading: false, error: null }
}
