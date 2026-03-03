// Query history panel — list of past queries with expandable answers.
// Shows when idle. Each entry can be expanded or re-asked.

import { useState } from 'react'
import Badge from './shared/Badge'
import SourceCard from './SourceCard'

const CONFIDENCE_VARIANT = {
  high:    'high',
  medium:  'medium',
  low:     'low',
  refused: 'refused',
}

function formatTime(iso) {
  const d = new Date(iso)
  const today = new Date()
  const isToday =
    d.getDate() === today.getDate() &&
    d.getMonth() === today.getMonth() &&
    d.getFullYear() === today.getFullYear()

  if (isToday) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
    ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function HistoryEntry({ entry, onReask }) {
  const [expanded, setExpanded] = useState(false)
  const { query, response, timestamp } = entry
  const confidence = response?.confidence

  return (
    <div className="border border-border rounded-lg bg-surface overflow-hidden">
      {/* Header row — always visible */}
      <button
        className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Expand chevron */}
        <span className="text-text-secondary mt-0.5 flex-shrink-0 text-xs">
          {expanded ? '▾' : '▸'}
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-sm text-text-primary font-medium truncate">{query}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[11px] font-mono text-text-secondary">{formatTime(timestamp)}</span>
            {confidence && (
              <Badge
                label={confidence}
                variant={CONFIDENCE_VARIANT[confidence] ?? 'default'}
              />
            )}
            {response && (
              <span className="text-[11px] text-text-secondary">
                {Math.round(response.retrieval_time_ms + response.generation_time_ms)}ms
              </span>
            )}
          </div>
        </div>

        <button
          onClick={(e) => { e.stopPropagation(); onReask(entry.query, entry.filters) }}
          className="flex-shrink-0 text-[11px] text-navy border border-navy/30 rounded px-2 py-0.5 hover:bg-navy/10 transition-colors font-medium"
        >
          Re-ask
        </button>
      </button>

      {/* Expanded body */}
      {expanded && response && (
        <div className="border-t border-border px-4 py-4 space-y-4 bg-gray-50/50">
          {/* Answer text */}
          <p className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
            {response.answer}
          </p>

          {/* Refusal reason */}
          {confidence === 'refused' && response.refusal_reason && (
            <p className="text-xs text-text-secondary border-l-2 border-confidence-refused pl-3">
              {response.refusal_reason}
            </p>
          )}

          {/* Citations */}
          {response.citations?.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
                Sources ({response.citations.length})
              </p>
              {response.citations.map((c, i) => (
                <SourceCard key={c.doc_id + i} citation={c} index={i + 1} />
              ))}
            </div>
          )}

          {/* Timing */}
          <div className="flex gap-4 text-[11px] text-text-secondary font-mono pt-1">
            <span>retrieval {Math.round(response.retrieval_time_ms)} ms</span>
            <span>generation {Math.round(response.generation_time_ms)} ms</span>
            <span>{response.model}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default function QueryHistory({ history, onClear, onReask }) {
  if (!history.length) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-base font-semibold text-text-primary">
          History
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-text-secondary bg-gray-100 rounded-full px-2 py-0.5">
            {history.length}
          </span>
          <button
            onClick={onClear}
            className="text-xs text-text-secondary hover:text-confidence-refused transition-colors"
          >
            Clear all
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {history.map((entry) => (
          <HistoryEntry key={entry.id} entry={entry} onReask={onReask} />
        ))}
      </div>
    </div>
  )
}
