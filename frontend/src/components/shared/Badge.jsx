// Reusable pill badge — provider label, doc type, confidence indicator, page range.

const VARIANTS = {
  navy:    'bg-navy/10 text-navy border border-navy/20',
  gold:    'bg-gold/15 text-[#8a6a1a] border border-gold/30',
  high:    'bg-green-50 text-confidence-high border border-green-200',
  medium:  'bg-amber-50 text-confidence-medium border border-amber-200',
  low:     'bg-gray-100 text-text-secondary border border-gray-200',
  refused: 'bg-red-50 text-confidence-refused border border-red-200',
  default: 'bg-gray-100 text-text-secondary border border-gray-200',
}

export default function Badge({ label, variant = 'default' }) {
  const cls = VARIANTS[variant] ?? VARIANTS.default
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium font-mono leading-none ${cls}`}>
      {label}
    </span>
  )
}
