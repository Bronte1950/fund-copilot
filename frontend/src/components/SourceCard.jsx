// Single citation card — renders both PDF document citations and live Yahoo Finance data.

import Badge from './shared/Badge'

export default function SourceCard({ citation, index }) {
  const {
    file_name, provider, fund_name, page_start, page_end,
    section, snippet, url, citation_type
  } = citation

  const isLive = citation_type === 'live_data'

  const pageLabel = isLive
    ? null
    : page_start === page_end
    ? `p. ${page_start}`
    : `pp. ${page_start}–${page_end}`

  return (
    <div className={`border rounded-lg p-4 transition-colors ${
      isLive
        ? 'bg-surface border-green-200 hover:border-green-400'
        : 'bg-surface border-border hover:border-navy/30'
    }`}>
      {/* Top row: index badge + provider + type badge + page */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] font-mono font-semibold text-navy bg-navy/10 rounded-full w-5 h-5 flex items-center justify-center flex-shrink-0">
            {index}
          </span>
          {provider && <Badge label={provider} variant={isLive ? 'high' : 'navy'} />}
          {isLive && <Badge label="live" variant="high" />}
          {!isLive && citation.doc_type && (
            <Badge label={citation.doc_type.replace('_', ' ')} variant="default" />
          )}
        </div>
        {pageLabel && <Badge label={pageLabel} variant="gold" />}
      </div>

      {/* Fund name */}
      {fund_name && (
        <p className="text-xs font-semibold text-text-primary mb-1 leading-snug">{fund_name}</p>
      )}

      {/* File name — clickable link for live data citations */}
      {isLive && url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] font-mono text-navy hover:underline truncate block mb-2"
          title={`Open ${file_name} on Yahoo Finance`}
        >
          {file_name} ↗
        </a>
      ) : (
        <p className="text-[11px] font-mono text-text-secondary mb-2 truncate" title={file_name}>
          {file_name}
        </p>
      )}

      {/* Section heading */}
      {section && (
        <p className="text-[11px] text-gold font-medium mb-1 uppercase tracking-wide">{section}</p>
      )}

      {/* Snippet */}
      {snippet && (
        <p className="text-xs text-text-secondary leading-relaxed line-clamp-4 border-l-2 border-border pl-2">
          {snippet}
        </p>
      )}
    </div>
  )
}
