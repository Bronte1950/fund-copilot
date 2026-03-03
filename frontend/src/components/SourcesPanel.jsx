// Right-column sources panel — list of citation SourceCards.

import SourceCard from './SourceCard'

export default function SourcesPanel({ citations = [], confidence }) {
  if (!citations.length) return null

  const isRefused = confidence === 'refused'

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-base font-semibold text-text-primary">
          Sources
        </h2>
        <span className="text-xs font-mono text-text-secondary bg-gray-100 rounded-full px-2 py-0.5">
          {citations.length}
        </span>
      </div>

      {isRefused ? (
        <p className="text-xs text-text-secondary italic">
          No sources cited — the model could not find sufficient evidence.
        </p>
      ) : (
        <div className="space-y-2">
          {citations.map((citation, i) => (
            <SourceCard key={citation.doc_id + i} citation={citation} index={i + 1} />
          ))}
        </div>
      )}
    </div>
  )
}
