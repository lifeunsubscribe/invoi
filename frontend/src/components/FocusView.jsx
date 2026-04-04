import { useMemo } from "react";

// Chrome styling (matches HistoryPage.jsx and other views)
const chrome = {
  border: "#4a3828",
  mutedText: "#a08878",
  brightText: "#e8d8cc"
};

// Status color mapping (from CalendarView.jsx)
const STATUS_COLORS = {
  draft: "#9a8070",    // gray/muted
  sent: "#4a94b4",     // blue
  paid: "#5a8a5a",     // green
  overdue: "#d4601a"   // red/alert
};

const STATUS_LABELS = {
  draft: "Draft",
  sent: "Sent",
  paid: "Paid",
  overdue: "Overdue"
};

const STATUS_ICONS = {
  draft: "●",
  sent: "→",
  paid: "✓",
  overdue: "!"
};

/**
 * Determine invoice status (including overdue calculation)
 * Shared logic from CalendarView.jsx
 */
function getInvoiceStatus(invoice) {
  if (invoice.status === "paid") return "paid";
  if (invoice.status === "sent") {
    // Check if overdue
    if (invoice.dueDate) {
      const dueDate = new Date(invoice.dueDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (dueDate < today) {
        return "overdue";
      }
    }
    return "sent";
  }
  return "draft";
}

/**
 * Format date for display (e.g., "Mon, Mar 24")
 */
function formatDateShort(dateString) {
  if (!dateString) return "";
  const date = new Date(dateString);
  const weekday = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][date.getDay()];
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][date.getMonth()];
  const day = date.getDate();
  return `${weekday}, ${month} ${day}`;
}

/**
 * Break down daily hours into a compact string (e.g., "M8 T8 W8 Th8 F8" or "40h total")
 */
function formatHoursBreakdown(invoice) {
  if (!invoice.dailyHours) {
    return `${invoice.totalHours || 0}h total`;
  }

  const dayAbbrev = { Mon: "M", Tue: "T", Wed: "W", Thu: "Th", Fri: "F", Sat: "Sa", Sun: "Su" };
  const entries = Object.entries(invoice.dailyHours)
    .filter(([_, hours]) => hours > 0)
    .map(([day, hours]) => `${dayAbbrev[day] || day}${hours}`);

  if (entries.length === 0) {
    return `${invoice.totalHours || 0}h total`;
  }

  if (entries.length > 5) {
    // Too many days to display compactly, just show total
    return `${invoice.totalHours || 0}h total`;
  }

  return entries.join(" ");
}

/**
 * FocusView - Collapsed calendar showing only invoice days as floating cards
 *
 * Features:
 * - Horizontal scroll layout with CSS scroll-snap for snap-to-card behavior
 * - Only days with invoices displayed (no empty days)
 * - Floating cards with shadows and breathing room between them
 * - Same color coding as calendar (draft/sent/paid/overdue)
 * - More detail per card: client name, hours breakdown, amount, status badge
 * - Tap card opens invoice detail panel
 */
export default function FocusView({ invoices, config, onInvoiceClick }) {
  // Filter and sort invoices: only show invoices with data, sorted by date (newest first for Focus view)
  const sortedInvoices = useMemo(() => {
    return [...invoices]
      .filter(invoice => invoice.weekStart) // Only invoices with valid dates
      .sort((a, b) => {
        // Sort by weekStart date descending (newest first)
        const dateA = new Date(a.weekStart);
        const dateB = new Date(b.weekStart);
        return dateB.getTime() - dateA.getTime();
      });
  }, [invoices]);

  const acc = config.accent;

  // Empty state when no invoices
  if (sortedInvoices.length === 0) {
    return (
      <div style={{
        width: "100%",
        maxWidth: 800,
        margin: "0 auto"
      }}>
        <div style={{
          background: "white",
          borderRadius: 12,
          border: `1px solid ${chrome.border}`,
          padding: "48px 32px",
          textAlign: "center"
        }}>
          <div style={{
            fontSize: 48,
            marginBottom: 16
          }}>🎯</div>
          <div style={{
            fontSize: 16,
            fontWeight: 700,
            color: "#6a4a40",
            marginBottom: 8
          }}>
            No invoices to focus on
          </div>
          <div style={{
            fontSize: 13,
            color: "#9a8070",
            lineHeight: 1.5
          }}>
            Create your first invoice to see it appear here in the Focus view
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      width: "100%"
    }}>
      {/* Header */}
      <div style={{
        maxWidth: 800,
        margin: "0 auto 20px",
        padding: "0 16px"
      }}>
        <div style={{
          fontSize: 14,
          fontWeight: 600,
          color: chrome.mutedText,
          marginBottom: 8
        }}>
          Showing {sortedInvoices.length} invoice{sortedInvoices.length !== 1 ? "s" : ""}
        </div>
        <div style={{
          fontSize: 12,
          color: "#9a8070",
          lineHeight: 1.4
        }}>
          Scroll horizontally to browse your invoices. Tap a card for details.
        </div>
      </div>

      {/* Horizontal Scroll Container with Snap Behavior */}
      <div
        style={{
          overflowX: "auto",
          overflowY: "hidden",
          // CSS scroll-snap for smooth snap-to-card behavior
          scrollSnapType: "x mandatory",
          WebkitOverflowScrolling: "touch", // Smooth scrolling on iOS
          // Hide scrollbar on some browsers for cleaner appearance
          scrollbarWidth: "thin",
          paddingBottom: 16,
          paddingTop: 8
        }}
      >
        {/* Card Container */}
        <div style={{
          display: "flex",
          gap: 20, // Breathing room between cards
          padding: "0 max(16px, calc(50vw - 140px))", // Center first/last card on scroll
          minHeight: 280
        }}>
          {sortedInvoices.map((invoice) => {
            const status = getInvoiceStatus(invoice);
            const statusColor = STATUS_COLORS[status];
            const statusLabel = STATUS_LABELS[status];
            const statusIcon = STATUS_ICONS[status];
            const dateLabel = formatDateShort(invoice.weekStart);
            const hoursBreakdown = formatHoursBreakdown(invoice);

            return (
              <button
                key={invoice.invoiceId}
                onClick={() => onInvoiceClick && onInvoiceClick(invoice)}
                style={{
                  // Fixed width for consistent snap points
                  width: 280,
                  minWidth: 280,
                  flexShrink: 0,

                  // Snap alignment
                  scrollSnapAlign: "center",

                  // Floating card appearance
                  background: "white",
                  borderRadius: 16,
                  border: `2px solid ${chrome.border}`,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)",

                  // Padding and layout
                  padding: 0,
                  display: "flex",
                  flexDirection: "column",
                  textAlign: "left",
                  cursor: "pointer",
                  transition: "all 0.2s ease",

                  // Reset button styles
                  fontFamily: "inherit",
                  fontSize: "inherit"
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-4px)";
                  e.currentTarget.style.boxShadow = "0 8px 20px rgba(0,0,0,0.12), 0 4px 8px rgba(0,0,0,0.06)";
                  e.currentTarget.style.borderColor = acc;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)";
                  e.currentTarget.style.borderColor = chrome.border;
                }}
              >
                {/* Status Header Bar */}
                <div style={{
                  background: statusColor,
                  padding: "12px 16px",
                  borderRadius: "14px 14px 0 0",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8
                }}>
                  <div style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "white",
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                    display: "flex",
                    alignItems: "center",
                    gap: 6
                  }}>
                    <span style={{ fontSize: 10 }}>{statusIcon}</span>
                    {statusLabel}
                  </div>

                  {/* Invoice Number */}
                  <div style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "rgba(255,255,255,0.9)"
                  }}>
                    {invoice.invoiceNumber || invoice.invoiceId}
                  </div>
                </div>

                {/* Card Body */}
                <div style={{
                  padding: "20px 16px",
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: 16
                }}>
                  {/* Date */}
                  <div>
                    <div style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: chrome.mutedText,
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      marginBottom: 4
                    }}>
                      Week Starting
                    </div>
                    <div style={{
                      fontSize: 15,
                      fontWeight: 700,
                      color: "#6a4a40"
                    }}>
                      {dateLabel}
                    </div>
                    <div style={{
                      fontSize: 11,
                      color: "#9a8070",
                      marginTop: 2
                    }}>
                      {invoice.weekStart} to {invoice.weekEnd}
                    </div>
                  </div>

                  {/* Client */}
                  <div>
                    <div style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: chrome.mutedText,
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      marginBottom: 4
                    }}>
                      Client
                    </div>
                    <div style={{
                      fontSize: 14,
                      fontWeight: 700,
                      color: "#6a4a40",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap"
                    }}>
                      {invoice.clientId || "Unknown Client"}
                    </div>
                  </div>

                  {/* Hours Breakdown */}
                  <div>
                    <div style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: chrome.mutedText,
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      marginBottom: 4
                    }}>
                      Hours
                    </div>
                    <div style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: "#6a4a40",
                      fontFamily: "monospace"
                    }}>
                      {hoursBreakdown}
                    </div>
                    <div style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: chrome.mutedText,
                      marginTop: 4
                    }}>
                      Total: {invoice.totalHours || 0} hours
                    </div>
                  </div>

                  {/* Amount */}
                  <div style={{
                    marginTop: "auto",
                    paddingTop: 12,
                    borderTop: `1px solid #f0e8e0`
                  }}>
                    <div style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: chrome.mutedText,
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      marginBottom: 4
                    }}>
                      Total Amount
                    </div>
                    <div style={{
                      fontSize: 24,
                      fontWeight: 700,
                      color: acc
                    }}>
                      ${(invoice.totalPay || 0).toFixed(2)}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div style={{
        maxWidth: 800,
        margin: "20px auto 0",
        padding: "0 16px"
      }}>
        <div style={{
          background: "white",
          borderRadius: 8,
          border: `1px solid ${chrome.border}`,
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 20,
          flexWrap: "wrap"
        }}>
          {[
            { status: "draft", label: "Draft" },
            { status: "sent", label: "Sent" },
            { status: "paid", label: "Paid" },
            { status: "overdue", label: "Overdue" }
          ].map(({ status, label }) => (
            <div
              key={status}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6
              }}
            >
              <div style={{
                width: 12,
                height: 12,
                borderRadius: 2,
                background: STATUS_COLORS[status]
              }} />
              <span style={{
                fontSize: 11,
                fontWeight: 600,
                color: chrome.mutedText
              }}>
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
