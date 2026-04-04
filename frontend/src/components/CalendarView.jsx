import { useState, useMemo } from "react";

// Chrome styling (matches HistoryPage.jsx)
const chrome = {
  border: "#4a3828",
  mutedText: "#a08878",
  brightText: "#e8d8cc"
};

// Status color mapping
const STATUS_COLORS = {
  draft: "#9a8070",    // gray/muted
  sent: "#4a94b4",     // blue
  paid: "#5a8a5a",     // green
  overdue: "#d4601a"   // red/alert
};

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

/**
 * Extract client initials from client name or ID
 * Examples: "Sunrise Home Health" -> "SH", "John Doe" -> "JD", "Client" -> "CL"
 */
function getClientInitials(clientName) {
  if (!clientName) return "??";

  const words = clientName.trim().split(/\s+/);
  if (words.length >= 2) {
    // Two or more words: take first letter of first and last word
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  }
  // Single word: take first two letters
  return clientName.slice(0, 2).toUpperCase();
}

/**
 * Determine invoice status (including overdue calculation)
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
 * CalendarView - Month grid calendar showing color-coded invoice pills by status
 *
 * Features:
 * - Month grid displays with day cells
 * - Invoice pills color-coded: gray=draft, blue=sent, green=paid, red=overdue
 * - Pill shows client initials, hours, amount
 * - Month navigation (‹ ›) loads adjacent months
 * - Tap pill opens invoice detail panel
 * - Today highlighted in grid
 */
export default function CalendarView({ invoices, config, onInvoiceClick }) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // State for current displayed month
  const [currentDate, setCurrentDate] = useState(new Date());

  // Navigate to previous month
  const handlePrevMonth = () => {
    setCurrentDate(prevDate => {
      const newDate = new Date(prevDate);
      newDate.setMonth(newDate.getMonth() - 1);
      return newDate;
    });
  };

  // Navigate to next month
  const handleNextMonth = () => {
    setCurrentDate(prevDate => {
      const newDate = new Date(prevDate);
      newDate.setMonth(newDate.getMonth() + 1);
      return newDate;
    });
  };

  // Generate calendar grid data
  const calendarGrid = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    // First day of the month (0 = Sunday, 6 = Saturday)
    const firstDay = new Date(year, month, 1);
    const firstDayOfWeek = firstDay.getDay();

    // Number of days in the month
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    // Number of days in previous month (for leading cells)
    const daysInPrevMonth = new Date(year, month, 0).getDate();

    // Generate 6 weeks (42 cells) to accommodate any month layout
    const cells = [];
    let cellDate = new Date(year, month, 1);
    cellDate.setDate(1 - firstDayOfWeek); // Start from previous month if needed

    for (let i = 0; i < 42; i++) {
      const cellYear = cellDate.getFullYear();
      const cellMonth = cellDate.getMonth();
      const cellDay = cellDate.getDate();

      cells.push({
        date: new Date(cellDate),
        day: cellDay,
        isCurrentMonth: cellMonth === month,
        isToday: cellDate.getTime() === today.getTime(),
        dateKey: `${cellYear}-${String(cellMonth + 1).padStart(2, '0')}-${String(cellDay).padStart(2, '0')}`
      });

      cellDate.setDate(cellDate.getDate() + 1);
    }

    return cells;
  }, [currentDate, today]);

  // Group invoices by date (using weekStart as the display date)
  const invoicesByDate = useMemo(() => {
    const grouped = {};

    invoices.forEach(invoice => {
      // Use weekStart as the date key
      if (invoice.weekStart) {
        const dateKey = invoice.weekStart; // Already in YYYY-MM-DD format
        if (!grouped[dateKey]) {
          grouped[dateKey] = [];
        }
        grouped[dateKey].push(invoice);
      }
    });

    return grouped;
  }, [invoices]);

  const acc = config.accent;

  return (
    <div style={{
      width: "100%",
      maxWidth: 900,
      margin: "0 auto"
    }}>
      {/* Month Navigation Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 20,
        padding: "0 8px"
      }}>
        <button
          onClick={handlePrevMonth}
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: chrome.mutedText,
            background: "white",
            border: `1.5px solid ${chrome.border}`,
            borderRadius: 8,
            padding: "8px 16px",
            cursor: "pointer",
            transition: "all 0.15s"
          }}
          onMouseEnter={(e) => {
            e.target.style.background = "#f9f3ee";
            e.target.style.color = acc;
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "white";
            e.target.style.color = chrome.mutedText;
          }}
        >
          ‹
        </button>

        <div style={{
          fontSize: 18,
          fontWeight: 700,
          color: "#6a4a40",
          textAlign: "center"
        }}>
          {MONTH_NAMES[currentDate.getMonth()]} {currentDate.getFullYear()}
        </div>

        <button
          onClick={handleNextMonth}
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: chrome.mutedText,
            background: "white",
            border: `1.5px solid ${chrome.border}`,
            borderRadius: 8,
            padding: "8px 16px",
            cursor: "pointer",
            transition: "all 0.15s"
          }}
          onMouseEnter={(e) => {
            e.target.style.background = "#f9f3ee";
            e.target.style.color = acc;
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "white";
            e.target.style.color = chrome.mutedText;
          }}
        >
          ›
        </button>
      </div>

      {/* Calendar Grid */}
      <div style={{
        background: "white",
        borderRadius: 12,
        border: `1px solid ${chrome.border}`,
        overflow: "hidden"
      }}>
        {/* Weekday Headers */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
          background: "#f9f3ee",
          borderBottom: `1px solid ${chrome.border}`
        }}>
          {WEEKDAY_LABELS.map((day) => (
            <div
              key={day}
              style={{
                padding: "12px 8px",
                fontSize: 11,
                fontWeight: 700,
                textAlign: "center",
                color: chrome.mutedText,
                textTransform: "uppercase",
                letterSpacing: 0.5
              }}
            >
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Grid Cells */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
          gridTemplateRows: "repeat(6, 1fr)",
          minHeight: 480
        }}>
          {calendarGrid.map((cell, index) => {
            const cellInvoices = invoicesByDate[cell.dateKey] || [];

            return (
              <div
                key={index}
                style={{
                  borderRight: (index % 7 !== 6) ? `1px solid ${chrome.border}` : "none",
                  borderBottom: (index < 35) ? `1px solid ${chrome.border}` : "none",
                  padding: "8px 6px",
                  minHeight: 80,
                  background: cell.isToday ? "#fdf2f4" : "white",
                  opacity: cell.isCurrentMonth ? 1 : 0.4,
                  position: "relative"
                }}
              >
                {/* Day Number */}
                <div style={{
                  fontSize: 13,
                  fontWeight: cell.isToday ? 700 : 600,
                  color: cell.isToday ? acc : (cell.isCurrentMonth ? "#6a4a40" : chrome.mutedText),
                  marginBottom: 6,
                  textAlign: "right"
                }}>
                  {cell.day}
                </div>

                {/* Today Indicator */}
                {cell.isToday && (
                  <div style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: 3,
                    background: acc,
                    borderRadius: "12px 12px 0 0"
                  }} />
                )}

                {/* Invoice Pills */}
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4
                }}>
                  {cellInvoices.map((invoice) => {
                    const status = getInvoiceStatus(invoice);
                    const statusColor = STATUS_COLORS[status];
                    const initials = getClientInitials(invoice.clientId || "Client");

                    return (
                      <button
                        key={invoice.invoiceId}
                        onClick={() => onInvoiceClick && onInvoiceClick(invoice)}
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          padding: "4px 6px",
                          borderRadius: 4,
                          border: "none",
                          background: statusColor,
                          color: "white",
                          cursor: "pointer",
                          textAlign: "left",
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                          transition: "all 0.15s",
                          width: "100%"
                        }}
                        onMouseEnter={(e) => {
                          e.target.style.opacity = "0.85";
                          e.target.style.transform = "scale(1.02)";
                        }}
                        onMouseLeave={(e) => {
                          e.target.style.opacity = "1";
                          e.target.style.transform = "scale(1)";
                        }}
                      >
                        {/* Status indicator */}
                        <span style={{ fontSize: 8 }}>
                          {status === "paid" ? "✓" : status === "overdue" ? "!" : "●"}
                        </span>

                        {/* Content */}
                        <span style={{
                          flex: 1,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap"
                        }}>
                          {initials} • {invoice.totalHours || 0}h • ${(invoice.totalPay || 0).toFixed(0)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div style={{
        marginTop: 16,
        padding: "12px 16px",
        background: "white",
        borderRadius: 8,
        border: `1px solid ${chrome.border}`,
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
  );
}
