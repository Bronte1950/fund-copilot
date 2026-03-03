// White surface card with border and shadow — wraps AnswerCard, SourcesPanel, etc.

export default function Panel({ children, className = '' }) {
  return (
    <div className={`bg-surface border border-border rounded-lg shadow-sm ${className}`}>
      {children}
    </div>
  )
}
