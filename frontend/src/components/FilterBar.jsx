// Provider, doc_type, and ISIN filter controls — used inside QueryBar.

const PROVIDERS = ['Vanguard', 'iShares', 'LGIM', 'Fidelity', 'Invesco', 'Amundi', 'HSBC', 'Xtrackers', 'SPDR']
const DOC_TYPES  = ['factsheet', 'kid', 'prospectus', 'annual_report', 'other']

const selectCls =
  'text-xs border border-border rounded px-2 py-1.5 text-text-secondary bg-surface ' +
  'focus:outline-none focus:border-navy focus:ring-1 focus:ring-navy/20 cursor-pointer'

export default function FilterBar({ filters, onChange }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-text-secondary font-medium">Filter:</span>

      <select
        value={filters.provider ?? ''}
        onChange={(e) => onChange({ ...filters, provider: e.target.value || null })}
        className={selectCls}
      >
        <option value="">All providers</option>
        {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>

      <select
        value={filters.doc_type ?? ''}
        onChange={(e) => onChange({ ...filters, doc_type: e.target.value || null })}
        className={selectCls}
      >
        <option value="">All types</option>
        {DOC_TYPES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
      </select>

      <input
        type="text"
        placeholder="ISIN"
        value={filters.isin ?? ''}
        onChange={(e) => onChange({ ...filters, isin: e.target.value || null })}
        className={`${selectCls} w-36 font-mono placeholder:font-sans placeholder:text-text-secondary/60`}
        spellCheck={false}
      />

      {(filters.provider || filters.doc_type || filters.isin) && (
        <button
          onClick={() => onChange({})}
          className="text-xs text-text-secondary hover:text-confidence-refused transition-colors"
        >
          Clear
        </button>
      )}
    </div>
  )
}
