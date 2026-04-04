import { useState, useEffect } from "react";
import { getAuthToken } from "../auth.jsx";

const API_BASE = import.meta.env.VITE_API_URL || '';

// Chrome styling (matches App.jsx)
const chrome = {
  titleBar: "#2e2218",
  toolbar: "#241a12",
  previewBg: "#ccc8c4",
  border: "#4a3828",
  mutedText: "#a08878",
  brightText: "#e8d8cc"
};

/**
 * Helper function to create tinted colors with alpha
 */
function tint(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/**
 * Shell component wrapper for consistent page layout
 * Matches the pattern used in WeeklyPage, MonthlyPage, ProfilePage
 */
function Shell({ config, title, subtitle, onBack, children }) {
  return (
    <div style={{
      height: "100vh",
      display: "flex",
      flexDirection: "column",
      background: chrome.titleBar,
      overflow: "hidden"
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Dancing+Script:wght@400;700&family=Great+Vibes&family=Sacramento&family=Pacifico&family=Satisfy&display=swap');
        * { box-sizing: border-box; }
        .view-btn { transition: all 0.15s; }
        .view-btn:hover { opacity: 0.85; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-thumb { background: #d0c0b8; border-radius: 3px; }
      `}</style>
      <div style={{
        background: chrome.toolbar,
        borderBottom: `1px solid ${chrome.border}`,
        padding: "10px 20px",
        display: "flex",
        alignItems: "center",
        gap: 14,
        flexShrink: 0
      }}>
        <button
          onClick={onBack || undefined}
          style={{
            fontSize: 15,
            color: chrome.mutedText,
            background: "none",
            border: `1px solid ${onBack ? chrome.border : "transparent"}`,
            borderRadius: 6,
            padding: "5px 12px",
            cursor: onBack ? "pointer" : "default",
            visibility: onBack ? "visible" : "hidden"
          }}
        >
          ← Back
        </button>
        <span style={{
          fontSize: 14,
          letterSpacing: 3,
          textTransform: "uppercase",
          color: config.accent,
          display: "flex",
          alignItems: "center",
          gap: 6
        }}>
          <span>♥</span> {title}
        </span>
        {subtitle && (
          <>
            <div style={{ width: 1, height: 14, background: chrome.border }} />
            <span style={{ fontSize: 16, color: chrome.brightText }}>{subtitle}</span>
          </>
        )}
      </div>
      {children}
    </div>
  );
}

/**
 * HistoryPage - Main invoice history page with view switcher
 *
 * Features:
 * - Segmented control to switch between Calendar, List, and Focus views
 * - Persists view preference to localStorage
 * - Loading state while fetching invoices
 * - Empty state when no invoices exist
 *
 * View implementations (Calendar/List/Focus) will be added in separate issues.
 */
export default function HistoryPage({ config, onBack }) {
  // Retrieve view preference from localStorage, default to "list"
  const [activeView, setActiveView] = useState(() => {
    const saved = localStorage.getItem("history-view-preference");
    return saved || "list";
  });

  const [loading, setLoading] = useState(true);
  const [invoices, setInvoices] = useState([]);
  const [error, setError] = useState(null);

  // Fetch invoices from API
  useEffect(() => {
    async function fetchInvoices() {
      try {
        setLoading(true);
        setError(null);

        const token = await getAuthToken();
        if (!token) {
          setError("Not authenticated");
          setLoading(false);
          return;
        }

        const response = await fetch(`${API_BASE}/api/invoices`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) {
          // If endpoint doesn't exist yet (404), treat as empty list
          if (response.status === 404) {
            setInvoices([]);
            setLoading(false);
            return;
          }
          throw new Error(`Failed to fetch invoices: ${response.statusText}`);
        }

        const data = await response.json();
        setInvoices(data.invoices || []);
      } catch (err) {
        console.error("Error fetching invoices:", err);
        // Gracefully handle API not being ready yet
        setError(null);
        setInvoices([]);
      } finally {
        setLoading(false);
      }
    }

    fetchInvoices();
  }, []);

  // Handle view change and persist to localStorage
  const handleViewChange = (view) => {
    setActiveView(view);
    localStorage.setItem("history-view-preference", view);
  };

  const acc = config.accent;

  return (
    <Shell config={config} title="History" onBack={onBack}>
      <div style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        background: "#f9f3ee",
        overflow: "hidden"
      }}>
        {/* Segmented Control for View Switching */}
        <div style={{
          padding: "20px 16px 16px",
          background: "white",
          borderBottom: `1px solid ${chrome.border}`
        }}>
          <div style={{
            display: "flex",
            gap: 8,
            maxWidth: 480,
            margin: "0 auto"
          }}>
            {["calendar", "list", "focus"].map((view) => {
              const isActive = activeView === view;
              const label = view.charAt(0).toUpperCase() + view.slice(1);
              const emoji = view === "calendar" ? "📅" : view === "list" ? "📋" : "🎯";

              return (
                <button
                  key={view}
                  className="view-btn"
                  onClick={() => handleViewChange(view)}
                  style={{
                    flex: 1,
                    fontSize: 13,
                    fontWeight: isActive ? 700 : 600,
                    padding: "10px 0",
                    borderRadius: 8,
                    border: isActive ? "none" : `1.5px solid ${chrome.border}`,
                    background: isActive ? acc : "white",
                    color: isActive ? "white" : chrome.mutedText,
                    cursor: "pointer",
                    boxShadow: isActive ? `0 3px 12px ${tint(acc, 0.3)}` : "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6
                  }}
                >
                  <span>{emoji}</span>
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Content Area */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "28px 16px 32px"
        }}>
          <div style={{
            width: "100%",
            maxWidth: 800,
            margin: "0 auto"
          }}>
            {/* Loading State */}
            {loading && (
              <div style={{
                background: "white",
                borderRadius: 12,
                padding: "40px 20px",
                textAlign: "center",
                border: `1px solid ${chrome.border}`
              }}>
                <div style={{
                  fontSize: 32,
                  marginBottom: 12
                }}>⏳</div>
                <div style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "#6a4a40",
                  marginBottom: 6
                }}>Loading your invoices...</div>
                <div style={{
                  fontSize: 12,
                  color: "#9a8070"
                }}>This should only take a moment</div>
              </div>
            )}

            {/* Error State (if any) */}
            {!loading && error && (
              <div style={{
                background: "#fef3e8",
                border: "1.5px solid #e8c090",
                borderRadius: 12,
                padding: "20px",
                textAlign: "center"
              }}>
                <div style={{
                  fontSize: 28,
                  marginBottom: 12
                }}>⚠️</div>
                <div style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "#8a5010",
                  marginBottom: 6
                }}>Could not load invoices</div>
                <div style={{
                  fontSize: 12,
                  color: "#a87020",
                  lineHeight: 1.4
                }}>{error}</div>
              </div>
            )}

            {/* Empty State */}
            {!loading && !error && invoices.length === 0 && (
              <div style={{
                background: "white",
                borderRadius: 12,
                padding: "48px 32px",
                textAlign: "center",
                border: `1px solid ${chrome.border}`
              }}>
                <div style={{
                  fontSize: 48,
                  marginBottom: 16
                }}>📄</div>
                <div style={{
                  fontSize: 16,
                  fontWeight: 700,
                  color: "#6a4a40",
                  marginBottom: 8
                }}>No invoices yet</div>
                <div style={{
                  fontSize: 13,
                  color: "#9a8070",
                  lineHeight: 1.5,
                  marginBottom: 20,
                  maxWidth: 360,
                  margin: "0 auto 20px"
                }}>
                  Create your first invoice to see it appear here. Your invoice history will be organized by {activeView} view.
                </div>
                <button
                  onClick={onBack}
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    padding: "10px 24px",
                    borderRadius: 8,
                    border: `1.5px solid ${acc}`,
                    background: "white",
                    color: acc,
                    cursor: "pointer"
                  }}
                >
                  ← Back to Menu
                </button>
              </div>
            )}

            {/* Placeholder for View Content (when invoices exist) */}
            {!loading && !error && invoices.length > 0 && (
              <div style={{
                background: "white",
                borderRadius: 12,
                padding: "32px",
                border: `1px solid ${chrome.border}`
              }}>
                <div style={{
                  textAlign: "center",
                  padding: "20px"
                }}>
                  <div style={{
                    fontSize: 36,
                    marginBottom: 12
                  }}>
                    {activeView === "calendar" ? "📅" : activeView === "list" ? "📋" : "🎯"}
                  </div>
                  <div style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "#6a4a40",
                    marginBottom: 6
                  }}>
                    {activeView === "calendar" ? "Calendar View" :
                     activeView === "list" ? "List View" :
                     "Focus View"}
                  </div>
                  <div style={{
                    fontSize: 12,
                    color: "#9a8070",
                    lineHeight: 1.4
                  }}>
                    Found {invoices.length} invoice{invoices.length !== 1 ? "s" : ""}.
                    View implementation coming soon.
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
}
