// Renders the LLM answer with streaming text, confidence badge, and citation superscripts.
// While streaming: shows accumulated text + blinking cursor.
// When done: transforms [SOURCE: chunk_id] → [n] superscripts and shows confidence.

import Panel from './shared/Panel'
import Badge from './shared/Badge'
import LoadingDots from './shared/LoadingDots'

const CONFIDENCE_META = {
  high:    { label: 'High confidence',   variant: 'high' },
  medium:  { label: 'Medium confidence', variant: 'medium' },
  low:     { label: 'Low confidence',    variant: 'low' },
  refused: { label: 'Refused',           variant: 'refused' },
}

/**
 * Parses the answer text, replacing [SOURCE: chunk_id] with [n] superscript React elements.
 * Returns an array of strings and {type:'cite', n} objects.
 */
function parseAnswerText(text, chunksCited = []) {
  const chunkIndex = {}
  chunksCited.forEach((id, i) => { chunkIndex[id] = i + 1 })

  const parts = []
  let last = 0
  const re = /\[SOURCE:\s*([^\]]+?)\]/gi
  let m

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    const chunkId = m[1].trim()
    const n = chunkIndex[chunkId] ?? '?'
    parts.push({ type: 'cite', n })
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

function AnswerText({ text, chunksCited }) {
  const parts = parseAnswerText(text, chunksCited)
  return (
    <p className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) =>
        typeof part === 'string'
          ? part
          : (
            <sup
              key={i}
              className="text-navy font-mono font-semibold text-[10px] ml-0.5 cursor-default"
              title={`Source ${part.n}`}
            >
              [{part.n}]
            </sup>
          )
      )}
    </p>
  )
}

export default function AnswerCard({ status, streamingText, response }) {
  const isIdle = status === 'idle'
  const isLoading = status === 'loading'
  const isStreaming = status === 'streaming'
  const isDone = status === 'done'
  const isError = status === 'error'

  if (isIdle) return null

  const confidence = response?.confidence
  const meta = confidence ? CONFIDENCE_META[confidence] : null

  return (
    <Panel className="p-5">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-serif text-base font-semibold text-text-primary">Answer</h2>
        {meta && (
          <Badge label={meta.label} variant={meta.variant} />
        )}
        {isStreaming && (
          <span className="text-xs text-text-secondary flex items-center gap-1.5">
            <LoadingDots size="sm" /> Generating
          </span>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-border mb-4" />

      {/* Body */}
      {isLoading && (
        <div className="flex items-center gap-2 text-text-secondary text-sm">
          <LoadingDots /> Searching documents…
        </div>
      )}

      {(isStreaming || isDone) && (
        <>
          <AnswerText
            text={isDone ? (response.answer ?? streamingText) : streamingText}
            chunksCited={response?.chunks_cited ?? []}
          />
          {isStreaming && (
            <span className="inline-block w-0.5 h-4 bg-navy animate-pulse ml-0.5 align-middle" />
          )}
        </>
      )}

      {isDone && confidence === 'refused' && response.refusal_reason && (
        <p className="mt-3 text-xs text-text-secondary border-l-2 border-confidence-refused pl-3">
          {response.refusal_reason}
        </p>
      )}

      {isError && (
        <p className="text-sm text-confidence-refused">
          Something went wrong. Please try again.
        </p>
      )}

      {/* Timing footer */}
      {isDone && response && (
        <div className="mt-4 pt-3 border-t border-border flex gap-4 text-[11px] text-text-secondary font-mono">
          <span>retrieval {Math.round(response.retrieval_time_ms)} ms</span>
          <span>generation {Math.round(response.generation_time_ms)} ms</span>
          <span>{response.model}</span>
        </div>
      )}
    </Panel>
  )
}
