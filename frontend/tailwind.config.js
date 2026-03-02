/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      // Research Analyst colour palette (see CLAUDE.md)
      colors: {
        bg: '#FAFAF8',
        surface: '#FFFFFF',
        'text-primary': '#1A1A2E',
        'text-secondary': '#6B7280',
        navy: '#1E3A5F',
        gold: '#C9A84C',
        border: '#E5E7EB',
        'confidence-high': '#166534',
        'confidence-medium': '#92400E',
        'confidence-refused': '#991B1B',
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        sans: ['"Source Sans 3"', 'ui-sans-serif', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        base: ['14px', { lineHeight: '1.6' }],
      },
    },
  },
  plugins: [],
}
