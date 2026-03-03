// Query textarea + filter bar + submit button.
// Submits on Enter (Shift+Enter for newline). Calls onSubmit(query, filters).

import { useState, useRef } from 'react'
import FilterBar from './FilterBar'
import LoadingDots from './shared/LoadingDots'

export default function QueryBar({ onSubmit, loading = false }) {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState({})
  const textareaRef = useRef(null)

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  function handleSubmit() {
    const q = query.trim()
    if (!q || loading) return
    onSubmit(q, filters)
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
          placeholder="Ask about a fund — e.g. What is the ongoing charge for the Vanguard FTSE All-World ETF?"
          className={
            'w-full border rounded-lg px-4 py-3 pr-24 text-sm text-text-primary bg-surface resize-none ' +
            'focus:outline-none focus:ring-1 transition-colors placeholder:text-text-secondary/70 ' +
            (loading
              ? 'border-navy/40 focus:border-navy focus:ring-navy/20'
              : 'border-border focus:border-navy focus:ring-navy/20')
          }
          disabled={loading}
        />
        <button
          onClick={handleSubmit}
          disabled={!query.trim() || loading}
          className={
            'absolute bottom-3 right-3 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ' +
            'disabled:opacity-40 disabled:cursor-not-allowed ' +
            'bg-navy text-white hover:bg-navy/90'
          }
        >
          {loading ? <LoadingDots size="sm" /> : 'Ask'}
        </button>
      </div>

      <FilterBar filters={filters} onChange={setFilters} />
    </div>
  )
}
