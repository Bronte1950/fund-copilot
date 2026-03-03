// "Documents" tab — searchable table of all indexed documents.

import { useState } from 'react'
import { useDocuments } from '../hooks/useDocuments'
import Badge from './shared/Badge'
import LoadingDots from './shared/LoadingDots'

const STATUS_VARIANT = {
  extracted: 'high',
  needs_ocr: 'medium',
  pending:   'low',
  failed:    'refused',
}

const DOC_TYPES  = ['', 'factsheet', 'kid', 'prospectus', 'annual_report', 'other']
const PROVIDERS  = ['', 'Vanguard', 'iShares', 'LGIM', 'Fidelity', 'Invesco', 'Amundi', 'HSBC', 'Xtrackers', 'SPDR']

const selectCls =
  'text-xs border border-border rounded px-2 py-1.5 text-text-secondary bg-surface ' +
  'focus:outline-none focus:border-navy focus:ring-1 focus:ring-navy/20 cursor-pointer'

export default function DocumentBrowser() {
  const [provider, setProvider] = useState('')
  const [docType, setDocType]   = useState('')
  const [search, setSearch]     = useState('')

  const { documents, loading, error, refetch } = useDocuments(
    provider || null,
    docType  || null,
  )

  const filtered = search.trim()
    ? documents.filter((d) =>
        d.file_name.toLowerCase().includes(search.toLowerCase()) ||
        (d.fund_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
        (d.isin ?? '').toLowerCase().includes(search.toLowerCase()),
      )
    : documents

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Search name, fund, ISIN…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={`${selectCls} w-52 font-sans`}
        />
        <select value={provider} onChange={(e) => setProvider(e.target.value)} className={selectCls}>
          <option value="">All providers</option>
          {PROVIDERS.slice(1).map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={docType} onChange={(e) => setDocType(e.target.value)} className={selectCls}>
          <option value="">All types</option>
          {DOC_TYPES.slice(1).map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
        </select>
        <button
          onClick={refetch}
          className="text-xs text-text-secondary hover:text-navy transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* State messages */}
      {loading && (
        <div className="flex items-center gap-2 text-sm text-text-secondary py-8 justify-center">
          <LoadingDots /> Loading documents…
        </div>
      )}
      {error && (
        <p className="text-sm text-confidence-refused">Failed to load documents: {error}</p>
      )}

      {/* Table */}
      {!loading && !error && (
        <>
          <p className="text-xs text-text-secondary">{filtered.length} document{filtered.length !== 1 ? 's' : ''}</p>
          <div className="bg-surface border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-gray-50">
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-secondary">File</th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-secondary">Provider</th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-secondary">Type</th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-secondary">ISIN</th>
                  <th className="text-right px-4 py-2.5 text-xs font-semibold text-text-secondary">Pages</th>
                  <th className="text-right px-4 py-2.5 text-xs font-semibold text-text-secondary">Chunks</th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-secondary">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-text-secondary text-xs">
                      No documents found.
                    </td>
                  </tr>
                ) : (
                  filtered.map((doc) => (
                    <tr key={doc.doc_id} className="border-b border-border last:border-0 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-2.5">
                        <div className="font-mono text-xs text-text-primary truncate max-w-[220px]" title={doc.file_name}>
                          {doc.file_name}
                        </div>
                        {doc.fund_name && (
                          <div className="text-xs text-text-secondary truncate max-w-[220px]">{doc.fund_name}</div>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        {doc.provider
                          ? <Badge label={doc.provider} variant="navy" />
                          : <span className="text-text-secondary text-xs">—</span>}
                      </td>
                      <td className="px-4 py-2.5">
                        {doc.doc_type
                          ? <Badge label={doc.doc_type.replace('_', ' ')} variant="default" />
                          : <span className="text-text-secondary text-xs">—</span>}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-text-secondary">
                        {doc.isin ?? '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right text-xs font-mono text-text-secondary">
                        {doc.page_count ?? '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right text-xs font-mono text-text-secondary">
                        {doc.chunk_count ?? '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge
                          label={doc.extraction_status ?? 'unknown'}
                          variant={STATUS_VARIANT[doc.extraction_status] ?? 'default'}
                        />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
