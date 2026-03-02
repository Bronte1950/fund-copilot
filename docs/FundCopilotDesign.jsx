import { useState, useEffect, useRef } from "react";

// ─── Mock Data ──────────────────────────────────────────────
const MOCK_SOURCES = [
  {
    id: "src_001",
    provider: "VANGUARD",
    fund: "LifeStrategy 60% Equity Fund",
    docType: "Factsheet",
    pages: "1–2",
    score: 0.94,
    snippet:
      "The Ongoing Charges Figure (OCF) for the Accumulation share class is 0.22% per annum. This figure covers the fund management fee and additional expenses.",
    isin: "GB00B3TYHH97",
  },
  {
    id: "src_002",
    provider: "VANGUARD",
    fund: "LifeStrategy 60% Equity Fund",
    docType: "KID",
    pages: "2",
    score: 0.87,
    snippet:
      "Costs over time: If you invest £10,000, the total costs you would pay over 1 year would be £22. This includes ongoing costs of 0.22% of the value of your investment per year.",
    isin: "GB00B3TYHH97",
  },
  {
    id: "src_003",
    provider: "ISHARES",
    fund: "Core MSCI World UCITS ETF",
    docType: "Factsheet",
    pages: "1",
    score: 0.41,
    snippet:
      "Total Expense Ratio (TER): 0.20%. The fund seeks to track the performance of the MSCI World Index. Domicile: Ireland.",
    isin: "IE00B4L5Y983",
  },
];

const MOCK_ANSWER = `The Ongoing Charges Figure (OCF) for the Vanguard LifeStrategy 60% Equity Fund is **0.22% per annum** for the Accumulation share class [Source: LifeStrategy 60% Equity Fund Factsheet, p.1–2].

This is confirmed by the fund's Key Information Document, which states that for a £10,000 investment, total costs over one year would be £22 — consistent with the 0.22% ongoing charge [Source: LifeStrategy 60% Equity Fund KID, p.2].

For comparison, the iShares Core MSCI World UCITS ETF has a TER of 0.20%, though this is a different fund tracking a global index rather than a multi-asset allocation [Source: Core MSCI World Factsheet, p.1].`;

const MOCK_DOCUMENTS = [
  { provider: "Vanguard", fund: "LifeStrategy 60% Equity", type: "Factsheet", pages: 4, chunks: 12, date: "Jan 2026" },
  { provider: "Vanguard", fund: "LifeStrategy 60% Equity", type: "KID", pages: 3, chunks: 8, date: "Dec 2025" },
  { provider: "Vanguard", fund: "LifeStrategy 80% Equity", type: "Factsheet", pages: 4, chunks: 11, date: "Jan 2026" },
  { provider: "Vanguard", fund: "FTSE Global All Cap Index", type: "Factsheet", pages: 4, chunks: 14, date: "Jan 2026" },
  { provider: "iShares", fund: "Core MSCI World UCITS ETF", type: "Factsheet", pages: 2, chunks: 8, date: "Feb 2026" },
  { provider: "iShares", fund: "Core S&P 500 UCITS ETF", type: "KID", pages: 3, chunks: 9, date: "Jan 2026" },
  { provider: "iShares", fund: "Physical Gold ETC", type: "Factsheet", pages: 2, chunks: 6, date: "Feb 2026" },
  { provider: "HSBC", fund: "FTSE All-World Index Fund", type: "Factsheet", pages: 4, chunks: 13, date: "Dec 2025" },
  { provider: "L&G", fund: "Global Technology Index", type: "KID", pages: 3, chunks: 7, date: "Jan 2026" },
  { provider: "Fidelity", fund: "Index World Fund", type: "Factsheet", pages: 4, chunks: 10, date: "Feb 2026" },
  { provider: "Invesco", fund: "Physical Gold ETC", type: "Factsheet", pages: 2, chunks: 5, date: "Jan 2026" },
  { provider: "WisdomTree", fund: "Physical Gold", type: "KID", pages: 3, chunks: 7, date: "Dec 2025" },
];

const PROVIDERS = ["All Providers", "Vanguard", "iShares", "HSBC", "L&G", "Fidelity", "Invesco", "WisdomTree"];
const DOC_TYPES = ["All Types", "Factsheet", "KID", "Prospectus", "Annual Report"];

// ─── Helpers ────────────────────────────────────────────────
function formatMarkdown(text) {
  return text.split("\n\n").map((para, i) => {
    const formatted = para
      .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#1E3A5F;font-weight:700">$1</strong>')
      .replace(
        /\[Source: (.*?)\]/g,
        '<span style="background:#F0EDE4;color:#6B5B3E;padding:1px 6px;border-radius:3px;font-family:\'IBM Plex Mono\',monospace;font-size:11.5px;white-space:nowrap;border:1px solid #E5DFD1">$1</span>'
      );
    return `<p key="${i}" style="margin-bottom:16px;line-height:1.75">${formatted}</p>`;
  });
}

// ─── Main App ───────────────────────────────────────────────
export default function FundCopilot() {
  const [activeTab, setActiveTab] = useState("ask");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [hasResult, setHasResult] = useState(false);
  const [displayedAnswer, setDisplayedAnswer] = useState("");
  const [expandedSource, setExpandedSource] = useState(null);
  const [providerFilter, setProviderFilter] = useState("All Providers");
  const [typeFilter, setTypeFilter] = useState("All Types");
  const [docSearch, setDocSearch] = useState("");
  const textareaRef = useRef(null);

  // Simulated streaming
  useEffect(() => {
    if (!isLoading) return;
    let idx = 0;
    const interval = setInterval(() => {
      idx += 3;
      if (idx >= MOCK_ANSWER.length) {
        setDisplayedAnswer(MOCK_ANSWER);
        setIsLoading(false);
        setHasResult(true);
        clearInterval(interval);
      } else {
        setDisplayedAnswer(MOCK_ANSWER.slice(0, idx));
      }
    }, 12);
    return () => clearInterval(interval);
  }, [isLoading]);

  function handleSubmit() {
    if (!query.trim()) return;
    setIsLoading(true);
    setHasResult(false);
    setDisplayedAnswer("");
    setExpandedSource(null);
  }

  function handleKeyDown(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  }

  const filteredDocs = MOCK_DOCUMENTS.filter((d) => {
    if (providerFilter !== "All Providers" && d.provider !== providerFilter) return false;
    if (typeFilter !== "All Types" && d.type !== typeFilter) return false;
    if (docSearch && !`${d.provider} ${d.fund} ${d.type}`.toLowerCase().includes(docSearch.toLowerCase())) return false;
    return true;
  });

  return (
    <div style={styles.page}>
      {/* Subtle paper texture overlay */}
      <div style={styles.textureOverlay} />

      {/* ─── Header ─── */}
      <header style={styles.header}>
        <div style={styles.headerInner}>
          <div style={styles.logoGroup}>
            <div style={styles.logoMark}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1E3A5F" strokeWidth="1.8">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
              </svg>
            </div>
            <div>
              <h1 style={styles.logoText}>Fund Copilot</h1>
              <p style={styles.logoSub}>Research Assistant · 100 documents indexed</p>
            </div>
          </div>
          <nav style={styles.nav}>
            {[
              { id: "ask", label: "Ask" },
              { id: "documents", label: "Documents" },
              { id: "evaluation", label: "Evaluation" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  ...styles.navItem,
                  ...(activeTab === tab.id ? styles.navItemActive : {}),
                }}
              >
                {tab.label}
                {activeTab === tab.id && <div style={styles.navIndicator} />}
              </button>
            ))}
          </nav>
        </div>
        <div style={styles.headerRule} />
      </header>

      {/* ─── Ask Tab ─── */}
      {activeTab === "ask" && (
        <main style={styles.mainGrid}>
          {/* Left Column — Query + Answer */}
          <div style={styles.leftCol}>
            {/* Query Input */}
            <div style={styles.queryCard}>
              <label style={styles.queryLabel}>Research Query</label>
              <textarea
                ref={textareaRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="What is the OCF for Vanguard LifeStrategy 60%?"
                style={styles.queryInput}
                rows={3}
              />
              <div style={styles.queryFooter}>
                <div style={styles.filterRow}>
                  <select style={styles.filterSelect} value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)}>
                    {PROVIDERS.map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                  <select style={styles.filterSelect} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                    {DOC_TYPES.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <button onClick={handleSubmit} disabled={isLoading || !query.trim()} style={{ ...styles.submitBtn, ...(isLoading || !query.trim() ? styles.submitBtnDisabled : {}) }}>
                  {isLoading ? (
                    <span style={styles.loadingDots}>
                      <span style={{ ...styles.dot, animationDelay: "0ms" }}>·</span>
                      <span style={{ ...styles.dot, animationDelay: "150ms" }}>·</span>
                      <span style={{ ...styles.dot, animationDelay: "300ms" }}>·</span>
                    </span>
                  ) : (
                    <>
                      Search
                      <span style={styles.shortcut}>⌘↵</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Answer */}
            {(isLoading || hasResult) && (
              <div style={{ ...styles.answerCard, animation: "fadeSlideIn 0.4s ease-out" }}>
                <div style={styles.answerHeader}>
                  <span style={styles.answerTitle}>Analysis</span>
                  <div style={styles.answerMeta}>
                    {hasResult && (
                      <>
                        <span style={styles.confidenceBadge}>
                          <span style={styles.confidenceDot} />
                          High confidence
                        </span>
                        <span style={styles.timingBadge}>1.2s retrieval · 18.4s generation</span>
                      </>
                    )}
                  </div>
                </div>
                <div style={styles.answerDivider} />
                <div style={styles.answerBody} dangerouslySetInnerHTML={{ __html: formatMarkdown(displayedAnswer).join("") }} />
                {isLoading && (
                  <div style={styles.cursor}>
                    <div style={styles.cursorBlink} />
                  </div>
                )}
              </div>
            )}

            {/* Empty State */}
            {!isLoading && !hasResult && (
              <div style={styles.emptyState}>
                <div style={styles.emptyIcon}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#C9A84C" strokeWidth="1" opacity="0.6">
                    <circle cx="11" cy="11" r="8" />
                    <path d="M21 21l-4.35-4.35" />
                  </svg>
                </div>
                <p style={styles.emptyTitle}>Ask a research question</p>
                <p style={styles.emptySubtitle}>
                  Query across 100 indexed fund documents with citations from factsheets, KIDs, prospectuses, and annual reports.
                </p>
                <div style={styles.exampleQueries}>
                  {[
                    "What is the OCF for Vanguard LifeStrategy 60%?",
                    "Compare risk ratings of iShares Physical Gold vs WisdomTree Physical Gold",
                    "What is the investment objective of the HSBC FTSE All-World fund?",
                    "Which funds have exposure to emerging markets?",
                  ].map((q, i) => (
                    <button
                      key={i}
                      style={styles.exampleQuery}
                      onClick={() => {
                        setQuery(q);
                        textareaRef.current?.focus();
                      }}
                    >
                      <span style={styles.exampleArrow}>→</span>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column — Sources */}
          <div style={styles.rightCol}>
            <div style={styles.sourcesHeader}>
              <span style={styles.sourcesTitle}>Sources</span>
              {hasResult && <span style={styles.sourcesCount}>{MOCK_SOURCES.length} chunks retrieved</span>}
            </div>

            {hasResult ? (
              <div style={styles.sourcesList}>
                {MOCK_SOURCES.map((src, i) => (
                  <div
                    key={src.id}
                    style={{
                      ...styles.sourceCard,
                      animation: `fadeSlideIn ${0.3 + i * 0.12}s ease-out`,
                      borderLeftColor: src.score > 0.8 ? "#1E3A5F" : src.score > 0.6 ? "#6B7280" : "#D1D5DB",
                    }}
                    onClick={() => setExpandedSource(expandedSource === src.id ? null : src.id)}
                  >
                    <div style={styles.sourceTop}>
                      <span style={styles.sourceProvider}>{src.provider}</span>
                      <span style={styles.sourceScore}>{(src.score * 100).toFixed(0)}%</span>
                    </div>
                    <h4 style={styles.sourceFund}>{src.fund}</h4>
                    <div style={styles.sourceTagRow}>
                      <span style={styles.sourceTag}>{src.docType}</span>
                      <span style={styles.sourceTag}>p. {src.pages}</span>
                      <span style={{ ...styles.sourceTag, ...styles.sourceTagIsin }}>{src.isin}</span>
                    </div>
                    {/* Relevance bar */}
                    <div style={styles.relevanceTrack}>
                      <div style={{ ...styles.relevanceBar, width: `${src.score * 100}%` }} />
                    </div>
                    {/* Expanded snippet */}
                    {expandedSource === src.id && (
                      <div style={styles.snippetExpanded}>
                        <div style={styles.snippetDivider} />
                        <p style={styles.snippetText}>"{src.snippet}"</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div style={styles.sourcesEmpty}>
                <p style={styles.sourcesEmptyText}>Sources will appear here when you run a query</p>
              </div>
            )}
          </div>
        </main>
      )}

      {/* ─── Documents Tab ─── */}
      {activeTab === "documents" && (
        <main style={styles.docsMain}>
          <div style={styles.docsHeader}>
            <h2 style={styles.docsTitle}>Indexed Documents</h2>
            <p style={styles.docsSubtitle}>
              {MOCK_DOCUMENTS.length} documents · {MOCK_DOCUMENTS.reduce((a, d) => a + d.chunks, 0)} chunks indexed
            </p>
          </div>
          <div style={styles.docsToolbar}>
            <input
              style={styles.docsSearch}
              placeholder="Search documents..."
              value={docSearch}
              onChange={(e) => setDocSearch(e.target.value)}
            />
            <select style={styles.filterSelect} value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)}>
              {PROVIDERS.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
            <select style={styles.filterSelect} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              {DOC_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div style={styles.docsTable}>
            <div style={styles.docsTableHead}>
              <span style={{ ...styles.docsCell, flex: 1.5 }}>Provider</span>
              <span style={{ ...styles.docsCell, flex: 3 }}>Fund Name</span>
              <span style={{ ...styles.docsCell, flex: 1 }}>Type</span>
              <span style={{ ...styles.docsCell, flex: 0.6, textAlign: "right" }}>Pages</span>
              <span style={{ ...styles.docsCell, flex: 0.6, textAlign: "right" }}>Chunks</span>
              <span style={{ ...styles.docsCell, flex: 1, textAlign: "right" }}>As of</span>
            </div>
            {filteredDocs.map((doc, i) => (
              <div key={i} style={{ ...styles.docsRow, animation: `fadeSlideIn ${0.15 + i * 0.04}s ease-out` }}>
                <span style={{ ...styles.docsCell, ...styles.docsCellProvider, flex: 1.5 }}>{doc.provider}</span>
                <span style={{ ...styles.docsCell, ...styles.docsCellFund, flex: 3 }}>{doc.fund}</span>
                <span style={{ ...styles.docsCell, flex: 1 }}>
                  <span style={styles.docTypePill}>{doc.type}</span>
                </span>
                <span style={{ ...styles.docsCell, flex: 0.6, textAlign: "right", fontFamily: "'IBM Plex Mono', monospace", fontSize: 13 }}>
                  {doc.pages}
                </span>
                <span style={{ ...styles.docsCell, flex: 0.6, textAlign: "right", fontFamily: "'IBM Plex Mono', monospace", fontSize: 13 }}>
                  {doc.chunks}
                </span>
                <span style={{ ...styles.docsCell, flex: 1, textAlign: "right", color: "#6B7280", fontSize: 13 }}>{doc.date}</span>
              </div>
            ))}
          </div>
        </main>
      )}

      {/* ─── Evaluation Tab (placeholder) ─── */}
      {activeTab === "evaluation" && (
        <main style={styles.docsMain}>
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#C9A84C" strokeWidth="1" opacity="0.6">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
            <p style={styles.emptyTitle}>Evaluation Dashboard</p>
            <p style={styles.emptySubtitle}>
              Phase 5 — metrics, failure diagnosis, and tuning experiments will appear here.
              <br />
              Recall@k · Precision@k · Grounding accuracy · Model comparison
            </p>
          </div>
        </main>
      )}

      {/* ─── Keyframe animations ─── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Source+Sans+3:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }

        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }

        @keyframes dotPulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }

        ::selection {
          background: #1E3A5F;
          color: #FFFFFF;
        }

        textarea::placeholder {
          color: #9CA3AF;
          font-style: italic;
        }

        * { box-sizing: border-box; }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #9CA3AF; }
      `}</style>
    </div>
  );
}

// ─── Styles ─────────────────────────────────────────────────
const styles = {
  page: {
    minHeight: "100vh",
    background: "#FAFAF8",
    fontFamily: "'Source Sans 3', 'Helvetica Neue', sans-serif",
    color: "#1A1A2E",
    position: "relative",
  },
  textureOverlay: {
    position: "fixed",
    inset: 0,
    pointerEvents: "none",
    opacity: 0.025,
    backgroundImage: `url("data:image/svg+xml,%3Csvg width='100' height='100' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100' height='100' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
    zIndex: 0,
  },

  // Header
  header: {
    position: "sticky",
    top: 0,
    zIndex: 100,
    background: "rgba(250, 250, 248, 0.92)",
    backdropFilter: "blur(12px)",
  },
  headerInner: {
    maxWidth: 1320,
    margin: "0 auto",
    padding: "16px 40px 0",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
  },
  headerRule: {
    height: 1,
    background: "linear-gradient(to right, transparent, #D1CBC0, #D1CBC0, transparent)",
    marginTop: 0,
  },
  logoGroup: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    paddingBottom: 14,
  },
  logoMark: {
    width: 40,
    height: 40,
    borderRadius: 8,
    background: "#F0EDE4",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    border: "1px solid #E5DFD1",
  },
  logoText: {
    fontFamily: "'Playfair Display', Georgia, serif",
    fontSize: 21,
    fontWeight: 600,
    color: "#1A1A2E",
    margin: 0,
    letterSpacing: "-0.3px",
  },
  logoSub: {
    fontSize: 12.5,
    color: "#8B8578",
    margin: 0,
    fontWeight: 400,
    letterSpacing: "0.2px",
  },
  nav: {
    display: "flex",
    gap: 0,
    paddingBottom: 0,
  },
  navItem: {
    background: "none",
    border: "none",
    padding: "10px 22px 14px",
    fontSize: 14,
    fontWeight: 500,
    color: "#8B8578",
    cursor: "pointer",
    position: "relative",
    fontFamily: "'Source Sans 3', sans-serif",
    transition: "color 0.2s",
    letterSpacing: "0.3px",
  },
  navItemActive: {
    color: "#1E3A5F",
    fontWeight: 600,
  },
  navIndicator: {
    position: "absolute",
    bottom: 0,
    left: 22,
    right: 22,
    height: 2,
    background: "#1E3A5F",
    borderRadius: "2px 2px 0 0",
  },

  // Main Grid
  mainGrid: {
    maxWidth: 1320,
    margin: "0 auto",
    padding: "32px 40px",
    display: "grid",
    gridTemplateColumns: "1fr 380px",
    gap: 36,
    alignItems: "start",
    position: "relative",
    zIndex: 1,
  },
  leftCol: {
    display: "flex",
    flexDirection: "column",
    gap: 24,
  },
  rightCol: {
    position: "sticky",
    top: 90,
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },

  // Query Card
  queryCard: {
    background: "#FFFFFF",
    border: "1px solid #E5E0D6",
    borderRadius: 10,
    padding: "22px 24px 18px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.03), 0 4px 12px rgba(0,0,0,0.02)",
  },
  queryLabel: {
    display: "block",
    fontSize: 11.5,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "1.2px",
    color: "#8B8578",
    marginBottom: 10,
  },
  queryInput: {
    width: "100%",
    border: "1px solid #E5E0D6",
    borderRadius: 6,
    padding: "14px 16px",
    fontSize: 15,
    fontFamily: "'Source Sans 3', sans-serif",
    color: "#1A1A2E",
    background: "#FAFAF8",
    resize: "none",
    outline: "none",
    lineHeight: 1.5,
    transition: "border-color 0.2s, box-shadow 0.2s",
  },
  queryFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 14,
    gap: 12,
  },
  filterRow: {
    display: "flex",
    gap: 8,
  },
  filterSelect: {
    padding: "6px 10px",
    fontSize: 13,
    border: "1px solid #E5E0D6",
    borderRadius: 5,
    background: "#FAFAF8",
    color: "#6B7280",
    fontFamily: "'Source Sans 3', sans-serif",
    outline: "none",
    cursor: "pointer",
  },
  submitBtn: {
    padding: "9px 22px",
    fontSize: 14,
    fontWeight: 600,
    fontFamily: "'Source Sans 3', sans-serif",
    background: "#1E3A5F",
    color: "#FFFFFF",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: 8,
    transition: "background 0.2s, transform 0.1s",
    letterSpacing: "0.3px",
  },
  submitBtnDisabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  shortcut: {
    fontSize: 11,
    opacity: 0.6,
    fontFamily: "'IBM Plex Mono', monospace",
    fontWeight: 400,
  },
  loadingDots: {
    display: "flex",
    gap: 2,
    fontSize: 20,
    lineHeight: 1,
  },
  dot: {
    animation: "dotPulse 1s infinite",
    fontWeight: 700,
  },

  // Answer Card
  answerCard: {
    background: "#FFFFFF",
    border: "1px solid #E5E0D6",
    borderRadius: 10,
    padding: "22px 28px 28px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.03), 0 4px 12px rgba(0,0,0,0.02)",
    borderLeft: "3px solid #166534",
  },
  answerHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  answerTitle: {
    fontFamily: "'Playfair Display', Georgia, serif",
    fontSize: 17,
    fontWeight: 600,
    color: "#1A1A2E",
  },
  answerMeta: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  confidenceBadge: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 600,
    color: "#166534",
    background: "#F0FDF4",
    padding: "3px 10px",
    borderRadius: 20,
    border: "1px solid #BBF7D0",
  },
  confidenceDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#166534",
  },
  timingBadge: {
    fontSize: 11.5,
    color: "#9CA3AF",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  answerDivider: {
    height: 1,
    background: "#F0EDE4",
    marginBottom: 18,
  },
  answerBody: {
    fontSize: 15,
    lineHeight: 1.75,
    color: "#374151",
    fontFamily: "'Source Sans 3', sans-serif",
  },
  cursor: {
    display: "inline-block",
    marginLeft: 2,
  },
  cursorBlink: {
    width: 2,
    height: 18,
    background: "#1E3A5F",
    animation: "blink 1s infinite",
    display: "inline-block",
    verticalAlign: "text-bottom",
  },

  // Empty State
  emptyState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "64px 40px",
    textAlign: "center",
  },
  emptyIcon: {
    marginBottom: 20,
  },
  emptyTitle: {
    fontFamily: "'Playfair Display', Georgia, serif",
    fontSize: 20,
    fontWeight: 600,
    color: "#1A1A2E",
    margin: "0 0 8px",
  },
  emptySubtitle: {
    fontSize: 14.5,
    color: "#8B8578",
    margin: "0 0 28px",
    lineHeight: 1.6,
    maxWidth: 460,
  },
  exampleQueries: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    width: "100%",
    maxWidth: 520,
  },
  exampleQuery: {
    background: "#FFFFFF",
    border: "1px solid #E5E0D6",
    borderRadius: 8,
    padding: "12px 16px",
    fontSize: 13.5,
    color: "#4B5563",
    cursor: "pointer",
    textAlign: "left",
    fontFamily: "'Source Sans 3', sans-serif",
    transition: "border-color 0.2s, background 0.2s, transform 0.1s",
    display: "flex",
    alignItems: "center",
    gap: 10,
    lineHeight: 1.4,
  },
  exampleArrow: {
    color: "#C9A84C",
    fontWeight: 600,
    fontSize: 15,
    flexShrink: 0,
  },

  // Sources Panel
  sourcesHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "baseline",
  },
  sourcesTitle: {
    fontFamily: "'Playfair Display', Georgia, serif",
    fontSize: 17,
    fontWeight: 600,
    color: "#1A1A2E",
  },
  sourcesCount: {
    fontSize: 12,
    color: "#8B8578",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  sourcesList: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  sourceCard: {
    background: "#FFFFFF",
    border: "1px solid #E5E0D6",
    borderRadius: 8,
    padding: "16px 18px",
    boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
    cursor: "pointer",
    transition: "box-shadow 0.2s, border-color 0.2s",
    borderLeft: "3px solid #1E3A5F",
  },
  sourceTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  sourceProvider: {
    fontSize: 10.5,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "1.5px",
    color: "#8B8578",
  },
  sourceScore: {
    fontSize: 12,
    fontWeight: 600,
    fontFamily: "'IBM Plex Mono', monospace",
    color: "#1E3A5F",
    background: "#EDF2F7",
    padding: "1px 7px",
    borderRadius: 4,
  },
  sourceFund: {
    fontFamily: "'Playfair Display', Georgia, serif",
    fontSize: 15,
    fontWeight: 600,
    color: "#1A1A2E",
    margin: "2px 0 8px",
    lineHeight: 1.3,
  },
  sourceTagRow: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap",
    marginBottom: 10,
  },
  sourceTag: {
    fontSize: 11,
    color: "#6B7280",
    background: "#F5F3EF",
    padding: "2px 8px",
    borderRadius: 3,
    fontFamily: "'IBM Plex Mono', monospace",
    border: "1px solid #E5E0D6",
  },
  sourceTagIsin: {
    color: "#1E3A5F",
    fontWeight: 500,
  },
  relevanceTrack: {
    height: 3,
    background: "#F0EDE4",
    borderRadius: 2,
    overflow: "hidden",
  },
  relevanceBar: {
    height: "100%",
    background: "linear-gradient(to right, #1E3A5F, #C9A84C)",
    borderRadius: 2,
    transition: "width 0.6s ease-out",
  },
  snippetExpanded: {
    animation: "fadeSlideIn 0.3s ease-out",
  },
  snippetDivider: {
    height: 1,
    background: "#F0EDE4",
    margin: "12px 0",
  },
  snippetText: {
    fontSize: 13,
    color: "#6B7280",
    lineHeight: 1.65,
    fontStyle: "italic",
    margin: 0,
  },
  sourcesEmpty: {
    padding: "48px 20px",
    textAlign: "center",
  },
  sourcesEmptyText: {
    fontSize: 13.5,
    color: "#9CA3AF",
    fontStyle: "italic",
  },

  // Documents Tab
  docsMain: {
    maxWidth: 1320,
    margin: "0 auto",
    padding: "32px 40px",
    position: "relative",
    zIndex: 1,
  },
  docsHeader: {
    marginBottom: 20,
  },
  docsTitle: {
    fontFamily: "'Playfair Display', Georgia, serif",
    fontSize: 24,
    fontWeight: 600,
    color: "#1A1A2E",
    margin: "0 0 4px",
  },
  docsSubtitle: {
    fontSize: 14,
    color: "#8B8578",
    margin: 0,
  },
  docsToolbar: {
    display: "flex",
    gap: 10,
    marginBottom: 16,
  },
  docsSearch: {
    flex: 1,
    padding: "8px 14px",
    fontSize: 14,
    border: "1px solid #E5E0D6",
    borderRadius: 6,
    background: "#FFFFFF",
    fontFamily: "'Source Sans 3', sans-serif",
    outline: "none",
    color: "#1A1A2E",
  },
  docsTable: {
    background: "#FFFFFF",
    border: "1px solid #E5E0D6",
    borderRadius: 10,
    overflow: "hidden",
    boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
  },
  docsTableHead: {
    display: "flex",
    padding: "12px 20px",
    background: "#F5F3EF",
    borderBottom: "1px solid #E5E0D6",
    fontSize: 11,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "1.2px",
    color: "#8B8578",
  },
  docsRow: {
    display: "flex",
    padding: "14px 20px",
    borderBottom: "1px solid #F5F3EF",
    transition: "background 0.15s",
    cursor: "pointer",
    alignItems: "center",
  },
  docsCell: {
    fontSize: 14,
    color: "#4B5563",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  docsCellProvider: {
    fontWeight: 600,
    color: "#1E3A5F",
    fontSize: 13,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  docsCellFund: {
    fontFamily: "'Playfair Display', Georgia, serif",
    fontWeight: 500,
    color: "#1A1A2E",
  },
  docTypePill: {
    fontSize: 11.5,
    background: "#F0EDE4",
    color: "#6B5B3E",
    padding: "2px 9px",
    borderRadius: 4,
    fontWeight: 500,
    border: "1px solid #E5DFD1",
  },
};
