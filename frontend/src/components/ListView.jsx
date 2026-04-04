import { useState, useMemo } from "react";

// Chrome styling (matches HistoryPage.jsx and CalendarView.jsx)
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
 * Extract unique client names/IDs from invoices for filter dropdown
 */
function getUniqueClients(invoices) {
  const clientSet = new Set();
  invoices.forEach(invoice => {
    if (invoice.clientId) {
      clientSet.add(invoice.clientId);
    }
  });
  return Array.from(clientSet).sort();
}

/**
 * ListView - Filterable, sortable list view with multi-select for bulk actions
 *
 * Features:
 * - Filter dropdowns: status, client, date range
 * - Sort options: date, amount, client
 * - Multi-select checkboxes for bulk actions
 * - Bulk action bar: mark paid, export, resend
 * - Tap row opens invoice detail panel
 */
export default function ListView({ invoices, config, onInvoiceClick }) {
  // Filter state
  const [statusFilter, setStatusFilter] = useState("all");
  const [clientFilter, setClientFilter] = useState("all");
  const [dateRangeFilter, setDateRangeFilter] = useState("all");

  // Sort state
  const [sortBy, setSortBy] = useState("date");
  const [sortOrder, setSortOrder] = useState("desc");

  // Multi-select state
  const [selectedIds, setSelectedIds] = useState(new Set());

  // Get unique clients for filter dropdown
  const uniqueClients = useMemo(() => getUniqueClients(invoices), [invoices]);

  /**
   * Apply filters to invoice list
   * Filters are applied client-side for simplicity (invoices already loaded)
   * Memoized to avoid recalculating on every render
   */
  const filteredInvoices = useMemo(() => {
    return invoices.filter(invoice => {
      const status = getInvoiceStatus(invoice);

      // Status filter
      if (statusFilter !== "all" && status !== statusFilter) {
        return false;
      }

      // Client filter
      if (clientFilter !== "all" && invoice.clientId !== clientFilter) {
        return false;
      }

      // Date range filter - calculates time ranges relative to current date
      if (dateRangeFilter !== "all" && invoice.weekStart) {
        const invoiceDate = new Date(invoice.weekStart);
        const now = new Date();
        const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        const ninetyDaysAgo = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);

        if (dateRangeFilter === "30days" && invoiceDate < thirtyDaysAgo) {
          return false;
        }
        if (dateRangeFilter === "90days" && invoiceDate < ninetyDaysAgo) {
          return false;
        }
        if (dateRangeFilter === "year") {
          const oneYearAgo = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
          if (invoiceDate < oneYearAgo) {
            return false;
          }
        }
      }

      return true;
    });
  }, [invoices, statusFilter, clientFilter, dateRangeFilter]);

  /**
   * Apply sorting to filtered invoices
   * Sorts by date (weekStart), amount (totalPay), or client (clientId)
   * Order can be ascending or descending
   */
  const sortedInvoices = useMemo(() => {
    const sorted = [...filteredInvoices];

    sorted.sort((a, b) => {
      let compareValue = 0;

      if (sortBy === "date") {
        const dateA = new Date(a.weekStart || 0);
        const dateB = new Date(b.weekStart || 0);
        compareValue = dateA.getTime() - dateB.getTime();
      } else if (sortBy === "amount") {
        compareValue = (a.totalPay || 0) - (b.totalPay || 0);
      } else if (sortBy === "client") {
        compareValue = (a.clientId || "").localeCompare(b.clientId || "");
      }

      // Negate for descending order
      return sortOrder === "asc" ? compareValue : -compareValue;
    });

    return sorted;
  }, [filteredInvoices, sortBy, sortOrder]);

  // Toggle individual invoice selection
  const handleToggleSelect = (invoiceId) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(invoiceId)) {
        newSet.delete(invoiceId);
      } else {
        newSet.add(invoiceId);
      }
      return newSet;
    });
  };

  // Toggle select all
  const handleToggleSelectAll = () => {
    if (selectedIds.size === sortedInvoices.length) {
      // Deselect all
      setSelectedIds(new Set());
    } else {
      // Select all filtered/sorted invoices
      setSelectedIds(new Set(sortedInvoices.map(inv => inv.invoiceId)));
    }
  };

  // Bulk action handlers (UI-only per scope boundary)
  const handleBulkMarkPaid = () => {
    console.log("Bulk mark as paid:", Array.from(selectedIds));
    // TODO: Backend integration in separate issue
    alert(`Mark ${selectedIds.size} invoice(s) as paid - Backend integration pending`);
  };

  const handleBulkExport = () => {
    console.log("Bulk export:", Array.from(selectedIds));
    // TODO: Backend integration in separate issue
    alert(`Export ${selectedIds.size} invoice(s) - Backend integration pending`);
  };

  const handleBulkResend = () => {
    console.log("Bulk resend:", Array.from(selectedIds));
    // TODO: Backend integration in separate issue
    alert(`Resend ${selectedIds.size} invoice(s) - Backend integration pending`);
  };

  // Toggle sort order for a given field
  const handleSort = (field) => {
    if (sortBy === field) {
      // Toggle order
      setSortOrder(prev => prev === "asc" ? "desc" : "asc");
    } else {
      // New field, default to descending
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  const acc = config.accent;
  const allSelected = sortedInvoices.length > 0 && selectedIds.size === sortedInvoices.length;

  return (
    <div style={{
      width: "100%",
      maxWidth: 900,
      margin: "0 auto",
      paddingBottom: selectedIds.size > 0 ? 80 : 0
    }}>
      {/* Filter and Sort Controls */}
      <div style={{
        background: "white",
        borderRadius: 12,
        border: `1px solid ${chrome.border}`,
        padding: "20px",
        marginBottom: 16
      }}>
        {/* Filters Row */}
        <div style={{
          display: "flex",
          gap: 12,
          marginBottom: 16,
          flexWrap: "wrap"
        }}>
          {/* Status Filter */}
          <div style={{ flex: "1 1 200px", minWidth: 150 }}>
            <label htmlFor="status-filter" style={{
              display: "block",
              fontSize: 11,
              fontWeight: 600,
              color: chrome.mutedText,
              textTransform: "uppercase",
              letterSpacing: 0.5,
              marginBottom: 6
            }}>
              Status
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: 13,
                fontWeight: 600,
                border: `1.5px solid ${chrome.border}`,
                borderRadius: 6,
                background: "white",
                color: "#6a4a40",
                cursor: "pointer"
              }}
            >
              <option value="all">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="sent">Sent</option>
              <option value="paid">Paid</option>
              <option value="overdue">Overdue</option>
            </select>
          </div>

          {/* Client Filter */}
          <div style={{ flex: "1 1 200px", minWidth: 150 }}>
            <label htmlFor="client-filter" style={{
              display: "block",
              fontSize: 11,
              fontWeight: 600,
              color: chrome.mutedText,
              textTransform: "uppercase",
              letterSpacing: 0.5,
              marginBottom: 6
            }}>
              Client
            </label>
            <select
              id="client-filter"
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: 13,
                fontWeight: 600,
                border: `1.5px solid ${chrome.border}`,
                borderRadius: 6,
                background: "white",
                color: "#6a4a40",
                cursor: "pointer"
              }}
            >
              <option value="all">All Clients</option>
              {uniqueClients.map(client => (
                <option key={client} value={client}>{client}</option>
              ))}
            </select>
          </div>

          {/* Date Range Filter */}
          <div style={{ flex: "1 1 200px", minWidth: 150 }}>
            <label htmlFor="date-range-filter" style={{
              display: "block",
              fontSize: 11,
              fontWeight: 600,
              color: chrome.mutedText,
              textTransform: "uppercase",
              letterSpacing: 0.5,
              marginBottom: 6
            }}>
              Date Range
            </label>
            <select
              id="date-range-filter"
              value={dateRangeFilter}
              onChange={(e) => setDateRangeFilter(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: 13,
                fontWeight: 600,
                border: `1.5px solid ${chrome.border}`,
                borderRadius: 6,
                background: "white",
                color: "#6a4a40",
                cursor: "pointer"
              }}
            >
              <option value="all">All Time</option>
              <option value="30days">Last 30 Days</option>
              <option value="90days">Last 90 Days</option>
              <option value="year">Last Year</option>
            </select>
          </div>
        </div>

        {/* Sort Controls */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap"
        }}>
          <span style={{
            fontSize: 11,
            fontWeight: 600,
            color: chrome.mutedText,
            textTransform: "uppercase",
            letterSpacing: 0.5
          }}>
            Sort by:
          </span>

          {["date", "amount", "client"].map(field => {
            const isActive = sortBy === field;
            const label = field.charAt(0).toUpperCase() + field.slice(1);

            return (
              <button
                key={field}
                onClick={() => handleSort(field)}
                style={{
                  fontSize: 12,
                  fontWeight: isActive ? 700 : 600,
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: isActive ? "none" : `1.5px solid ${chrome.border}`,
                  background: isActive ? acc : "white",
                  color: isActive ? "white" : chrome.mutedText,
                  cursor: "pointer",
                  transition: "all 0.15s",
                  display: "flex",
                  alignItems: "center",
                  gap: 4
                }}
              >
                {label}
                {isActive && (
                  <span style={{ fontSize: 10 }}>
                    {sortOrder === "asc" ? "↑" : "↓"}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Results Summary */}
      <div style={{
        fontSize: 12,
        color: chrome.mutedText,
        marginBottom: 12,
        padding: "0 4px"
      }}>
        Showing {sortedInvoices.length} of {invoices.length} invoice{invoices.length !== 1 ? "s" : ""}
        {selectedIds.size > 0 && (
          <span style={{ fontWeight: 600, color: acc }}>
            {" • "}{selectedIds.size} selected
          </span>
        )}
      </div>

      {/* Invoice List */}
      {sortedInvoices.length === 0 ? (
        <div style={{
          background: "white",
          borderRadius: 12,
          border: `1px solid ${chrome.border}`,
          padding: "40px 20px",
          textAlign: "center"
        }}>
          <div style={{
            fontSize: 32,
            marginBottom: 12
          }}>🔍</div>
          <div style={{
            fontSize: 14,
            fontWeight: 600,
            color: "#6a4a40",
            marginBottom: 6
          }}>
            No invoices found
          </div>
          <div style={{
            fontSize: 12,
            color: "#9a8070",
            lineHeight: 1.4
          }}>
            Try adjusting your filters to see more results
          </div>
        </div>
      ) : (
        <>
          {/* Select All Header */}
          <div style={{
            background: "white",
            borderRadius: "12px 12px 0 0",
            border: `1px solid ${chrome.border}`,
            borderBottom: "none",
            padding: "12px 20px",
            display: "flex",
            alignItems: "center",
            gap: 12
          }}>
            <input
              type="checkbox"
              checked={allSelected}
              onChange={handleToggleSelectAll}
              style={{
                width: 16,
                height: 16,
                cursor: "pointer",
                accentColor: acc
              }}
            />
            <span style={{
              fontSize: 12,
              fontWeight: 600,
              color: chrome.mutedText,
              textTransform: "uppercase",
              letterSpacing: 0.5
            }}>
              Select All
            </span>
          </div>

          {/* Invoice Cards */}
          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: 1
          }}>
            {sortedInvoices.map((invoice, index) => {
              const status = getInvoiceStatus(invoice);
              const statusColor = STATUS_COLORS[status];
              const isSelected = selectedIds.has(invoice.invoiceId);
              const isLast = index === sortedInvoices.length - 1;

              return (
                <div
                  key={invoice.invoiceId}
                  style={{
                    background: "white",
                    border: `1px solid ${chrome.border}`,
                    borderTop: "none",
                    borderRadius: isLast ? "0 0 12px 12px" : 0,
                    padding: "16px 20px",
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    cursor: "pointer",
                    transition: "all 0.15s",
                    ...(isSelected && {
                      background: "#fdf9f6",
                      borderColor: acc
                    })
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = "#f9f3ee";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = "white";
                    }
                  }}
                >
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => {
                      e.stopPropagation();
                      handleToggleSelect(invoice.invoiceId);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      width: 16,
                      height: 16,
                      cursor: "pointer",
                      accentColor: acc,
                      flexShrink: 0
                    }}
                  />

                  {/* Main Content - Clickable */}
                  <div
                    onClick={() => onInvoiceClick && onInvoiceClick(invoice)}
                    style={{
                      flex: 1,
                      display: "flex",
                      alignItems: "center",
                      gap: 20,
                      flexWrap: "wrap"
                    }}
                  >
                    {/* Status Badge */}
                    <div style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: "6px 10px",
                      borderRadius: 6,
                      background: statusColor,
                      color: "white",
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      flexShrink: 0,
                      minWidth: 70,
                      textAlign: "center"
                    }}>
                      {STATUS_LABELS[status]}
                    </div>

                    {/* Invoice Info */}
                    <div style={{ flex: "1 1 200px", minWidth: 150 }}>
                      <div style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: "#6a4a40",
                        marginBottom: 4
                      }}>
                        {invoice.invoiceNumber || invoice.invoiceId}
                      </div>
                      <div style={{
                        fontSize: 12,
                        color: chrome.mutedText
                      }}>
                        {invoice.weekStart} to {invoice.weekEnd}
                      </div>
                    </div>

                    {/* Client */}
                    <div style={{ flex: "1 1 150px", minWidth: 120 }}>
                      <div style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: chrome.mutedText,
                        textTransform: "uppercase",
                        letterSpacing: 0.5,
                        marginBottom: 3
                      }}>
                        Client
                      </div>
                      <div style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "#6a4a40"
                      }}>
                        {invoice.clientId || "Unknown"}
                      </div>
                    </div>

                    {/* Hours */}
                    <div style={{ flex: "0 0 80px", textAlign: "right" }}>
                      <div style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: chrome.mutedText,
                        textTransform: "uppercase",
                        letterSpacing: 0.5,
                        marginBottom: 3
                      }}>
                        Hours
                      </div>
                      <div style={{
                        fontSize: 15,
                        fontWeight: 700,
                        color: "#6a4a40"
                      }}>
                        {invoice.totalHours || 0}
                      </div>
                    </div>

                    {/* Amount */}
                    <div style={{ flex: "0 0 100px", textAlign: "right" }}>
                      <div style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: chrome.mutedText,
                        textTransform: "uppercase",
                        letterSpacing: 0.5,
                        marginBottom: 3
                      }}>
                        Amount
                      </div>
                      <div style={{
                        fontSize: 16,
                        fontWeight: 700,
                        color: acc
                      }}>
                        ${(invoice.totalPay || 0).toFixed(2)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Bulk Action Bar (Fixed at Bottom) */}
      {selectedIds.size > 0 && (
        <div style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          background: "#2e2218",
          borderTop: `2px solid ${acc}`,
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          zIndex: 100,
          boxShadow: "0 -4px 16px rgba(0,0,0,0.1)"
        }}>
          {/* Selection Count */}
          <div style={{
            fontSize: 14,
            fontWeight: 700,
            color: chrome.brightText
          }}>
            {selectedIds.size} invoice{selectedIds.size !== 1 ? "s" : ""} selected
          </div>

          {/* Action Buttons */}
          <div style={{
            display: "flex",
            gap: 10,
            flexWrap: "wrap"
          }}>
            <button
              onClick={handleBulkMarkPaid}
              style={{
                fontSize: 13,
                fontWeight: 600,
                padding: "10px 18px",
                borderRadius: 6,
                border: "none",
                background: "#5a8a5a",
                color: "white",
                cursor: "pointer",
                transition: "all 0.15s"
              }}
              onMouseEnter={(e) => e.target.style.opacity = "0.85"}
              onMouseLeave={(e) => e.target.style.opacity = "1"}
            >
              ✓ Mark Paid
            </button>

            <button
              onClick={handleBulkExport}
              style={{
                fontSize: 13,
                fontWeight: 600,
                padding: "10px 18px",
                borderRadius: 6,
                border: "none",
                background: "#4a94b4",
                color: "white",
                cursor: "pointer",
                transition: "all 0.15s"
              }}
              onMouseEnter={(e) => e.target.style.opacity = "0.85"}
              onMouseLeave={(e) => e.target.style.opacity = "1"}
            >
              📦 Export
            </button>

            <button
              onClick={handleBulkResend}
              style={{
                fontSize: 13,
                fontWeight: 600,
                padding: "10px 18px",
                borderRadius: 6,
                border: "none",
                background: acc,
                color: "white",
                cursor: "pointer",
                transition: "all 0.15s"
              }}
              onMouseEnter={(e) => e.target.style.opacity = "0.85"}
              onMouseLeave={(e) => e.target.style.opacity = "1"}
            >
              ✉ Resend
            </button>

            <button
              onClick={() => setSelectedIds(new Set())}
              style={{
                fontSize: 13,
                fontWeight: 600,
                padding: "10px 18px",
                borderRadius: 6,
                border: `1.5px solid ${chrome.mutedText}`,
                background: "transparent",
                color: chrome.brightText,
                cursor: "pointer",
                transition: "all 0.15s"
              }}
              onMouseEnter={(e) => e.target.style.background = "rgba(255,255,255,0.1)"}
              onMouseLeave={(e) => e.target.style.background = "transparent"}
            >
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
