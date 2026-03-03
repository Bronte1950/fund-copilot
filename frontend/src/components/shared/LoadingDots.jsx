// Animated three-dot loading indicator — used in QueryBar button and AnswerCard.

export default function LoadingDots({ size = 'md' }) {
  const dot = size === 'sm'
    ? 'w-1 h-1'
    : 'w-1.5 h-1.5'

  return (
    <span className="inline-flex items-center gap-1" aria-label="Loading">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`${dot} rounded-full bg-current animate-pulse`}
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
    </span>
  )
}
