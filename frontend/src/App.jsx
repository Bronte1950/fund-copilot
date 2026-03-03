// Fund Copilot — Research Analyst UI
// Two-column layout: 60% query + answer (left), 40% sources (right).
// Nav tabs: Ask | Documents | Evaluation.

import { useState, useEffect, Fragment } from 'react'
import { useChat } from './hooks/useChat'
import { useHistory } from './hooks/useHistory'
import { useEval } from './hooks/useEval'
import QueryBar from './components/QueryBar'
import AnswerCard from './components/AnswerCard'
import SourcesPanel from './components/SourcesPanel'
import QueryHistory from './components/QueryHistory'
import DocumentBrowser from './components/DocumentBrowser'
import Badge from './components/shared/Badge'
import LoadingDots from './components/shared/LoadingDots'

const TABS = ['Ask', 'Documents', 'Evaluation']

// ── Nav ───────────────────────────────────────────────────────────────────────

function NavTab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={
        'text-sm font-medium pb-1 border-b-2 transition-colors ' +
        (active
          ? 'border-navy text-navy'
          : 'border-transparent text-text-secondary hover:text-text-primary')
      }
    >
      {label}
    </button>
  )
}

// ── Ask tab ───────────────────────────────────────────────────────────────────

function AskTab() {
  const { submit, reset, status, streamingText, response, error } = useChat()
  const { history, addEntry, clearHistory } = useHistory()
  const isActive = status !== 'idle'
  const isLoading = status === 'loading' || status === 'streaming'

  const [lastQuery, setLastQuery] = useState(null)

  // Save to history when a query completes
  useEffect(() => {
    if (status === 'done' && response && lastQuery) {
      addEntry(lastQuery.query, lastQuery.filters, response)
    }
  }, [status]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmitWithHistory(query, filters) {
    setLastQuery({ query, filters })
    reset()
    submit(query, filters)
  }

  function handleReask(query, filters) {
    setLastQuery({ query, filters })
    reset()
    submit(query, filters)
  }

  return (
    <div className="flex gap-6 h-full">
      {/* Left column — 60% */}
      <div className="flex-[3] min-w-0 space-y-4">
        <QueryBar onSubmit={handleSubmitWithHistory} loading={isLoading} />

        {isActive && (
          <AnswerCard
            status={status}
            streamingText={streamingText}
            response={response}
            error={error}
          />
        )}

        {!isActive && (
          <QueryHistory
            history={history}
            onClear={clearHistory}
            onReask={handleReask}
          />
        )}
      </div>

      {/* Right column — 40% */}
      <div className="flex-[2] min-w-0">
        {response?.citations?.length > 0 && (
          <SourcesPanel
            citations={response.citations}
            confidence={response.confidence}
          />
        )}
      </div>
    </div>
  )
}

// ── Evaluation tab ────────────────────────────────────────────────────────────

function MetricBox({ label, value, variant }) {
  const formatted =
    value === null || value === undefined
      ? '—'
      : typeof value === 'number' && value <= 1
      ? `${(value * 100).toFixed(1)}%`
      : value

  return (
    <div className="bg-surface border border-border rounded-lg p-4 text-center space-y-1">
      <p className="text-xs text-text-secondary uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-mono font-semibold ${variant === 'navy' ? 'text-navy' : 'text-text-primary'}`}>
        {formatted}
      </p>
    </div>
  )
}

function CategoryRow({ cat, data }) {
  const hitBg = data.hit_at_k >= 0.8
    ? 'text-green-700'
    : data.hit_at_k >= 0.5
    ? 'text-amber-700'
    : 'text-red-700'

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 px-3 font-mono text-xs text-text-secondary">{cat}</td>
      <td className="py-2 px-3 text-center text-sm">{data.n}</td>
      <td className={`py-2 px-3 text-center text-sm font-mono ${hitBg}`}>
        {data.hit_at_k !== null ? `${(data.hit_at_k * 100).toFixed(0)}%` : '—'}
      </td>
      <td className="py-2 px-3 text-center text-sm font-mono">
        {`${(data.grounding_rate * 100).toFixed(0)}%`}
      </td>
      <td className="py-2 px-3 text-center text-sm font-mono">
        {`${(data.refusal_accuracy * 100).toFixed(0)}%`}
      </td>
    </tr>
  )
}

function ResultRow({ r, i }) {
  const hitColor =
    r.hit_at_k === 1.0 ? 'text-green-600' :
    r.hit_at_k === 0.0 ? 'text-red-600' : 'text-text-secondary'

  const confidenceBadge =
    r.confidence === 'high' ? 'high' :
    r.confidence === 'medium' ? 'medium' :
    r.confidence === 'refused' ? 'refused' : 'default'

  return (
    <tr className="border-b border-border last:border-0 hover:bg-gray-50 align-top text-xs">
      <td className="py-2 px-3 font-mono text-text-secondary whitespace-nowrap">{r.question_id}</td>
      <td className="py-2 px-3 max-w-xs">
        <p className="truncate text-text-primary" title={r.query}>{r.query}</p>
        <p className="text-[10px] text-text-secondary font-mono mt-0.5">{r.category}</p>
      </td>
      <td className={`py-2 px-3 text-center font-mono font-semibold ${hitColor}`}>
        {r.hit_at_k === null ? '—' : r.hit_at_k === 1.0 ? '✓' : '✗'}
      </td>
      <td className="py-2 px-3 text-center">
        <Badge variant={confidenceBadge}>{r.confidence}</Badge>
      </td>
      <td className="py-2 px-3 text-center">
        {r.grounding_ok
          ? <span className="text-green-600 font-mono">✓</span>
          : <span className="text-red-600 font-mono">✗</span>}
      </td>
      <td className="py-2 px-3 text-center">
        {r.refusal_correct
          ? <span className="text-green-600 font-mono">✓</span>
          : <span className="text-red-600 font-mono">✗</span>}
      </td>
      <td className="py-2 px-3 font-mono text-text-secondary whitespace-nowrap">
        {r.error
          ? <span className="text-red-500 text-[10px]">error</span>
          : `${Math.round(r.retrieval_ms + r.generation_ms)}ms`}
      </td>
    </tr>
  )
}

// ── Run history ───────────────────────────────────────────────────────────────

function formatTs(ts) {
  // "20250101T120000" → local datetime string
  const s = ts.replace(/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/, '$1-$2-$3T$4:$5:$6Z')
  return new Date(s).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function pct(v) {
  return v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`
}

function DeltaBadge({ current, prev }) {
  if (prev === null || prev === undefined || current === null || current === undefined) return null
  const diff = current - prev
  if (Math.abs(diff) < 0.001) return null
  const up = diff > 0
  return (
    <span className={`ml-1 text-[10px] font-mono ${up ? 'text-green-600' : 'text-red-500'}`}>
      {up ? '▲' : '▼'}{(Math.abs(diff) * 100).toFixed(1)}
    </span>
  )
}

const API = 'http://localhost:8010'

function RunHistory({ history }) {
  const [expandedTs, setExpandedTs] = useState(null)
  const [expandedResults, setExpandedResults] = useState([])
  const [expandLoading, setExpandLoading] = useState(false)

  async function toggleExpand(ts) {
    if (expandedTs === ts) {
      setExpandedTs(null)
      setExpandedResults([])
      return
    }
    setExpandedTs(ts)
    setExpandedResults([])
    setExpandLoading(true)
    try {
      const res = await fetch(`${API}/eval/results/${ts}`)
      const data = await res.json()
      setExpandedResults(data.results ?? [])
    } catch {
      setExpandedResults([])
    } finally {
      setExpandLoading(false)
    }
  }

  if (history.length === 0) return null

  const COL_COUNT = 10  // run ID + summary cols + expand chevron

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <p className="px-4 py-2.5 text-xs font-medium text-text-secondary border-b border-border uppercase tracking-wide">
        Run History ({history.length})
      </p>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-gray-50 text-xs text-text-secondary uppercase tracking-wide">
              <th className="py-2 px-3 text-left">Run</th>
              <th className="py-2 px-3 text-left">Timestamp</th>
              <th className="py-2 px-3 text-center">top_k</th>
              <th className="py-2 px-3 text-center">Questions</th>
              <th className="py-2 px-3 text-center">Hit@k</th>
              <th className="py-2 px-3 text-center">Grounding</th>
              <th className="py-2 px-3 text-center">Refusal acc.</th>
              <th className="py-2 px-3 text-center">Errors</th>
              <th className="py-2 px-3 text-center">Avg gen.</th>
              <th className="py-2 px-3 w-8" />
            </tr>
          </thead>
          <tbody>
            {history.map((run, i) => {
              const runId = `R${history.length - i}`
              const prev = history[i + 1]
              const isLatest = i === 0
              const isOpen = expandedTs === run.timestamp
              const rowBg = isOpen
                ? 'bg-navy/5'
                : isLatest
                ? 'bg-blue-50/40 hover:bg-blue-50/60'
                : 'hover:bg-gray-50'

              return (
                <Fragment key={run.timestamp}>
                  <tr
                    onClick={() => toggleExpand(run.timestamp)}
                    className={`border-b border-border text-xs cursor-pointer select-none ${rowBg}`}
                  >
                    <td className="py-2 px-3 whitespace-nowrap">
                      <span className="font-mono font-semibold text-navy">{runId}</span>
                    </td>
                    <td className="py-2 px-3 font-mono text-text-secondary whitespace-nowrap">
                      {formatTs(run.timestamp)}
                      {isLatest && (
                        <span className="ml-2 text-[10px] bg-navy text-white rounded px-1 py-0.5 font-sans">latest</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-center font-mono">{run.top_k}</td>
                    <td className="py-2 px-3 text-center font-mono">{run.n_questions}</td>
                    <td className="py-2 px-3 text-center font-mono">
                      <span className={run.hit_at_k >= 0.8 ? 'text-green-700' : run.hit_at_k >= 0.5 ? 'text-amber-700' : 'text-red-700'}>
                        {pct(run.hit_at_k)}
                      </span>
                      <DeltaBadge current={run.hit_at_k} prev={prev?.hit_at_k} />
                    </td>
                    <td className="py-2 px-3 text-center font-mono">
                      {pct(run.grounding_rate)}
                      <DeltaBadge current={run.grounding_rate} prev={prev?.grounding_rate} />
                    </td>
                    <td className="py-2 px-3 text-center font-mono">
                      {pct(run.refusal_accuracy)}
                      <DeltaBadge current={run.refusal_accuracy} prev={prev?.refusal_accuracy} />
                    </td>
                    <td className={`py-2 px-3 text-center font-mono ${run.n_errors > 0 ? 'text-red-500' : 'text-text-secondary'}`}>
                      {run.n_errors ?? 0}
                    </td>
                    <td className="py-2 px-3 text-center font-mono text-text-secondary">
                      {run.avg_generation_ms != null ? `${Math.round(run.avg_generation_ms / 1000)}s` : '—'}
                    </td>
                    <td className="py-2 px-3 text-center text-text-secondary text-[10px]">
                      {isOpen ? '▲' : '▼'}
                    </td>
                  </tr>

                  {/* Expanded per-question results */}
                  {isOpen && (
                    <tr className="border-b border-border">
                      <td colSpan={COL_COUNT} className="p-0 bg-gray-50/60">
                        {expandLoading ? (
                          <div className="px-6 py-4 text-xs text-text-secondary">Loading…</div>
                        ) : expandedResults.length === 0 ? (
                          <div className="px-6 py-4 text-xs text-text-secondary">No results found.</div>
                        ) : (
                          <div className="overflow-x-auto">
                            <table className="w-full">
                              <thead>
                                <tr className="border-b border-border text-xs text-text-secondary uppercase tracking-wide bg-gray-100">
                                  <th className="py-2 px-3 text-left">ID</th>
                                  <th className="py-2 px-3 text-left">Query</th>
                                  <th className="py-2 px-3 text-center">Hit</th>
                                  <th className="py-2 px-3 text-center">Confidence</th>
                                  <th className="py-2 px-3 text-center">Grounded</th>
                                  <th className="py-2 px-3 text-center">Refusal</th>
                                  <th className="py-2 px-3 text-center">Time</th>
                                </tr>
                              </thead>
                              <tbody>
                                {expandedResults.map((r) => (
                                  <ResultRow key={r.question_id} r={r} i={0} />
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function EvaluationTab() {
  const { status, summary, results, error, progress, history, startRun, loadLatest } = useEval()
  const [topK, setTopK] = useState(10)
  const [elapsed, setElapsed] = useState(0)

  const isRunning = status === 'running'

  // Tick elapsed-seconds counter for the current question
  useEffect(() => {
    if (!isRunning || !progress?.current_started_at) {
      setElapsed(0)
      return
    }
    const tick = () =>
      setElapsed(Math.round((Date.now() - new Date(progress.current_started_at)) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [isRunning, progress?.current_started_at])

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-serif text-xl text-text-primary">Evaluation Dashboard</h2>
          <p className="text-xs text-text-secondary mt-0.5">
            Recall@k · grounding accuracy · refusal accuracy
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-text-secondary">
            top_k
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              disabled={isRunning}
              className="border border-border rounded px-1.5 py-0.5 text-xs font-mono bg-surface focus:outline-none focus:ring-1 focus:ring-navy/30"
            >
              {[5, 10, 20].map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          </label>
          <button
            onClick={() => startRun(topK)}
            disabled={isRunning}
            className="px-4 py-1.5 bg-navy text-white text-xs rounded font-medium hover:bg-navy/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning ? 'Running…' : 'Run Eval'}
          </button>
          {!summary && status !== 'running' && (
            <button
              onClick={loadLatest}
              className="px-3 py-1.5 border border-border text-xs rounded text-text-secondary hover:bg-gray-50 transition-colors"
            >
              Load Latest
            </button>
          )}
        </div>
      </div>

      {/* Live progress panel */}
      {isRunning && (
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          {/* Progress bar header */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
            <LoadingDots size="sm" />
            <span className="text-sm text-text-secondary">Evaluating questions…</span>
            {progress?.n_questions > 0 && (
              <span className="font-mono text-xs text-navy ml-auto">
                {progress.n_complete ?? 0} / {progress.n_questions}
              </span>
            )}
          </div>

          {/* Current question */}
          {progress?.current_qid && (
            <div className="flex items-center gap-3 px-4 py-2.5 bg-blue-50/60 border-b border-border">
              <span className="font-mono text-xs text-navy w-10 shrink-0">{progress.current_qid}</span>
              <span className="text-xs text-text-secondary flex-1">Generating…</span>
              <span className="font-mono text-xs text-navy tabular-nums">{elapsed}s</span>
            </div>
          )}

          {/* Completed questions so far — newest first */}
          {progress?.partial_results?.length > 0 && (
            <div className="overflow-x-auto max-h-60 overflow-y-auto">
              <table className="w-full">
                <thead className="sticky top-0 bg-gray-50 z-10">
                  <tr className="border-b border-border text-xs text-text-secondary uppercase tracking-wide">
                    <th className="py-2 px-3 text-left">ID</th>
                    <th className="py-2 px-3 text-left">Query</th>
                    <th className="py-2 px-3 text-center">Hit</th>
                    <th className="py-2 px-3 text-center">Confidence</th>
                    <th className="py-2 px-3 text-center">Grounded</th>
                    <th className="py-2 px-3 text-center">Refusal</th>
                    <th className="py-2 px-3 text-center">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {[...progress.partial_results].reverse().map((r) => (
                    <ResultRow key={r.question_id} r={r} i={0} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {status === 'error' && error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg px-4 py-3 font-mono">
          {error}
        </div>
      )}

      {/* Summary metrics */}
      {summary && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricBox label="Hit@k" value={summary.hit_at_k} variant="navy" />
            <MetricBox label="Grounding" value={summary.grounding_rate} />
            <MetricBox label="Refusal acc." value={summary.refusal_accuracy} />
            <MetricBox label="Answ. grounding" value={summary.answerable_grounding} />
            <MetricBox label="Correct refusals" value={summary.correct_refusals} />
            <MetricBox label="Questions" value={summary.n_questions} />
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs text-text-secondary">
            <p>
              Avg retrieval:{' '}
              <span className="font-mono text-text-primary">{summary.avg_retrieval_ms}ms</span>
            </p>
            <p>
              Avg generation:{' '}
              <span className="font-mono text-text-primary">{summary.avg_generation_ms}ms</span>
              {summary.n_errors > 0 && (
                <span className="ml-3 text-red-500">{summary.n_errors} error(s)</span>
              )}
            </p>
          </div>

          {/* By category */}
          {summary.by_category && Object.keys(summary.by_category).length > 0 && (
            <div className="bg-surface border border-border rounded-lg overflow-hidden">
              <p className="px-4 py-2.5 text-xs font-medium text-text-secondary border-b border-border uppercase tracking-wide">
                By Category
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-gray-50 text-xs text-text-secondary uppercase tracking-wide">
                    <th className="py-2 px-3 text-left">Category</th>
                    <th className="py-2 px-3 text-center">n</th>
                    <th className="py-2 px-3 text-center">Hit@k</th>
                    <th className="py-2 px-3 text-center">Grounding</th>
                    <th className="py-2 px-3 text-center">Refusal</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(summary.by_category).map(([cat, data]) => (
                    <CategoryRow key={cat} cat={cat} data={data} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Per-question results */}
          {results.length > 0 && (
            <div className="bg-surface border border-border rounded-lg overflow-hidden">
              <p className="px-4 py-2.5 text-xs font-medium text-text-secondary border-b border-border uppercase tracking-wide">
                Per-Question Results
              </p>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border bg-gray-50 text-xs text-text-secondary uppercase tracking-wide">
                      <th className="py-2 px-3 text-left">ID</th>
                      <th className="py-2 px-3 text-left">Query</th>
                      <th className="py-2 px-3 text-center">Hit</th>
                      <th className="py-2 px-3 text-center">Confidence</th>
                      <th className="py-2 px-3 text-center">Grounded</th>
                      <th className="py-2 px-3 text-center">Refusal</th>
                      <th className="py-2 px-3 text-center">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r, i) => <ResultRow key={r.question_id} r={r} i={i} />)}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {status === 'idle' && !summary && (
        <div className="flex items-center justify-center py-16 text-text-secondary text-sm">
          <div className="text-center space-y-3">
            <p className="font-serif text-lg text-text-primary">No results yet</p>
            <p className="text-xs">Click <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">Run Eval</span> to evaluate the question set against the live pipeline.</p>
            <p className="text-xs">Or click <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">Load Latest</span> to view the most recent saved results.</p>
          </div>
        </div>
      )}

      {/* Run history — always shown when there are past results */}
      <RunHistory history={history} />
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [activeTab, setActiveTab] = useState('Ask')

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-surface px-8 py-3.5 flex items-center gap-8 flex-shrink-0">
        <div className="flex items-center gap-2">
          <h1 className="font-serif text-lg font-bold text-navy tracking-tight">Fund Copilot</h1>
          <span className="text-[10px] font-mono text-gold border border-gold/40 rounded px-1.5 py-0.5 leading-none">
            beta
          </span>
        </div>

        <nav className="flex gap-6">
          {TABS.map((tab) => (
            <NavTab
              key={tab}
              label={tab}
              active={activeTab === tab}
              onClick={() => setActiveTab(tab)}
            />
          ))}
        </nav>

        <div className="ml-auto text-[11px] text-text-secondary font-mono hidden sm:block">
          local-first · cite or refuse
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 p-6 lg:p-8 overflow-auto">
        {activeTab === 'Ask'        && <AskTab />}
        {activeTab === 'Documents'  && <DocumentBrowser />}
        {activeTab === 'Evaluation' && <EvaluationTab />}
      </main>
    </div>
  )
}
