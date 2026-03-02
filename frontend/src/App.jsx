// Phase 4: full implementation of the Research Analyst UI
// For now: minimal shell with nav tabs

import React, { useState } from 'react'

const TABS = ['Ask', 'Documents', 'Evaluation']

export default function App() {
  const [activeTab, setActiveTab] = useState('Ask')

  return (
    <div className="min-h-screen bg-bg">
      {/* Top nav */}
      <header className="border-b border-border bg-white px-8 py-4 flex items-center gap-8">
        <h1 className="font-serif text-xl font-bold text-navy">Fund Copilot</h1>
        <nav className="flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`text-sm font-medium pb-1 border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-navy text-navy'
                  : 'border-transparent text-text-secondary hover:text-text-primary'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </header>

      {/* Main content — Phase 4 */}
      <main className="p-8 text-text-secondary text-sm">
        <p>
          <span className="font-mono text-xs bg-gray-100 px-1 py-0.5 rounded">
            Phase 4
          </span>{' '}
          UI implementation coming soon.
        </p>
      </main>
    </div>
  )
}
