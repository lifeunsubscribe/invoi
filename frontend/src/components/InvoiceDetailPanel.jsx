import { useState, useEffect, useRef } from "react";
import { getAuthToken } from "../auth.jsx";
import { getInvoiceStatus } from "../utils/invoiceStatus.js";

// API configuration
const API_BASE = import.meta.env.VITE_API_URL || '';

// Validate required environment variables for API calls
if (!API_BASE && import.meta.env.DEV) {
  console.warn(
    'VITE_API_URL is not defined. PDF download will fail.\n' +
    'Run `npx sst dev` to start the development environment with the API.'
  );
}

// Chrome styling (matches HistoryPage.jsx)
const chrome = {
  titleBar: "#2e2218",
  toolbar: "#241a12",
  border: "#4a3828",
  mutedText: "#a08878",
  brightText: "#e8d8cc"
};

// Status color mapping (consistent with ListView and CalendarView)
const STATUS_COLORS = {
  draft: "#9a8070",
  sent: "#4a94b4",
  paid: "#5a8a5a",
  overdue: "#d4601a"
};

/**
 * Find the monthly report that contains this invoice
 *
 * Monthly reports aggregate all weekly invoices for a given month.
 * This function searches for a monthly report with type="monthly"
 * that covers the same month as the given invoice.
 *
 * @param {Object} invoice - The invoice to find a report for
 * @param {Array} allInvoices - Complete list of all invoices (weekly + monthly)
 * @returns {Object|null} The monthly report containing this invoice, or null if none exists
 */
function findMonthlyReport(invoice, allInvoices) {
  if (!invoice.weekStart) return null;

  const invoiceDate = new Date(invoice.weekStart);
  const year = invoiceDate.getFullYear();
  const month = invoiceDate.getMonth(); // 0-indexed (0 = January)

  // Search for a monthly report covering the same month as this invoice
  const monthlyReport = allInvoices.find(inv => {
    if (inv.type !== "monthly") return false;

    // Monthly reports have invoiceId like "RPT-2026-03"
    // Compare year and month from the report's weekStart date
    if (inv.weekStart) {
      const reportDate = new Date(inv.weekStart);
      return reportDate.getFullYear() === year && reportDate.getMonth() === month;
    }
    return false;
  });

  return monthlyReport;
}

/**
 * InvoiceDetailPanel - Slide-out panel showing full invoice details
 *
 * Features:
 * - Slides in from right with smooth animation
 * - Full invoice metadata display
 * - PDF preview/download link
 * - Associated service logs (if any)
 * - Link to monthly report containing this invoice (if exists)
 * - Sequential navigation: ← prev / next →
 * - "Mark as paid" toggle with micro-animation
 * - Close button returns to view
 *
 * Accessibility:
 * - Focus trapping: Tab/Shift+Tab cycles within modal
 * - Auto-focus on close button when modal opens
 * - Focus restoration to trigger element when modal closes
 * - ARIA attributes: role="dialog", aria-modal="true"
 * - Escape key to close
 */
export default function InvoiceDetailPanel({
  invoice,
  invoices = [],
  config,
  onClose,
  onNavigate,
  onMarkPaid
}) {
  const [isAnimating, setIsAnimating] = useState(false);
  const [showPaidAnimation, setShowPaidAnimation] = useState(false);

  // Refs for focus management and trapping
  const panelRef = useRef(null);
  const previouslyFocusedElement = useRef(null);

  // Trigger slide-in animation on mount
  // The panel starts off-screen (translateX(100%)) and slides in after mount
  useEffect(() => {
    // Small delay allows React to render the initial state before starting the CSS transition
    const timer = setTimeout(() => setIsAnimating(true), 10);
    return () => clearTimeout(timer);
  }, []);

  // Focus management: Store previously focused element and set initial focus
  useEffect(() => {
    // Store the element that had focus before the modal opened
    previouslyFocusedElement.current = document.activeElement;

    // Set focus to the panel container after the slide-in animation
    const focusTimer = setTimeout(() => {
      if (panelRef.current) {
        // Find the close button (first focusable button in the header)
        const closeButton = panelRef.current.querySelector('button');
        if (closeButton) {
          closeButton.focus();
        }
      }
    }, 350); // Wait for animation (300ms) + small buffer

    return () => clearTimeout(focusTimer);
  }, []);

  // Focus trap: Prevent Tab from leaving the modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Close panel on Escape key
      if (e.key === "Escape") {
        handleClose();
        return;
      }

      // Focus trap: Handle Tab and Shift+Tab
      if (e.key === "Tab" && panelRef.current) {
        const focusableSelector = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])';
        const focusableElements = panelRef.current.querySelectorAll(focusableSelector);
        const focusableArray = Array.from(focusableElements);

        if (focusableArray.length === 0) return;

        const firstFocusable = focusableArray[0];
        const lastFocusable = focusableArray[focusableArray.length - 1];

        // Shift+Tab on first element: cycle to last
        if (e.shiftKey && document.activeElement === firstFocusable) {
          e.preventDefault();
          lastFocusable.focus();
        }
        // Tab on last element: cycle to first
        else if (!e.shiftKey && document.activeElement === lastFocusable) {
          e.preventDefault();
          firstFocusable.focus();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Handle close with slide-out animation
  // Reverses the slide-in animation before unmounting
  const handleClose = () => {
    setIsAnimating(false);
    // Wait for the 300ms CSS transition to complete before removing the component
    setTimeout(() => {
      onClose && onClose();
      // Restore focus to the element that was focused before the modal opened
      // Check that the element still exists in the DOM before focusing
      if (
        previouslyFocusedElement.current &&
        typeof previouslyFocusedElement.current.focus === 'function' &&
        document.contains(previouslyFocusedElement.current)
      ) {
        previouslyFocusedElement.current.focus();
      }
    }, 300);
  };

  // Find current invoice index in the list
  const currentIndex = invoices.findIndex(inv => inv.invoiceId === invoice.invoiceId);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < invoices.length - 1;

  // Navigation handlers
  const handlePrev = () => {
    if (hasPrev && onNavigate) {
      const prevInvoice = invoices[currentIndex - 1];
      if (prevInvoice) {
        onNavigate(prevInvoice);
      }
    }
  };

  const handleNext = () => {
    if (hasNext && onNavigate) {
      const nextInvoice = invoices[currentIndex + 1];
      if (nextInvoice) {
        onNavigate(nextInvoice);
      }
    }
  };

  // Mark as paid handler with micro-animation
  // Shows a celebratory pulse animation when marking an invoice as paid
  const handleTogglePaid = () => {
    const isPaid = invoice.status === "paid";

    if (!isPaid) {
      // Trigger 1-second celebratory pulse animation for the positive action of getting paid
      setShowPaidAnimation(true);
      setTimeout(() => setShowPaidAnimation(false), 1000);
    }

    // Toggle the paid status (UI-only for now, backend integration pending)
    if (onMarkPaid) {
      onMarkPaid(invoice, !isPaid);
    }
  };

  // Download PDF handler
  // Fetches a signed URL from the backend and opens it in a new tab
  // Supports both invoice PDFs (pdfType='invoice') and service log PDFs (pdfType='log')
  const handleDownloadPdf = async (pdfType = 'invoice') => {
    // Validate API configuration before making the request
    if (!API_BASE) {
      console.error('Cannot download PDF: VITE_API_URL is not configured');
      alert('PDF download is not available. Please ensure the API is configured.');
      return;
    }

    // Check if the requested PDF type exists for this invoice
    if (pdfType === 'log' && !invoice.logPdfKey) {
      console.error('Cannot download service log PDF: No service log PDF available for this invoice');
      alert('No service log PDF available for this invoice');
      return;
    }

    if (pdfType === 'invoice' && !invoice.pdfKey) {
      console.error('Cannot download invoice PDF: No invoice PDF available');
      alert('No invoice PDF available for this invoice');
      return;
    }

    try {
      // Get authentication token
      const token = await getAuthToken();
      if (!token) {
        console.error('Cannot download PDF: Not authenticated');
        alert('Please sign in to download PDFs');
        return;
      }

      // Request signed URL from backend API with PDF type parameter
      // The backend validates ownership and generates a time-limited signed S3 URL
      const url = `${API_BASE}/api/pdf/${invoice.invoiceId}${pdfType === 'log' ? '?type=log' : ''}`;
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to get PDF URL (${response.status})`);
      }

      const data = await response.json();

      // Open the signed URL in a new tab for preview/download
      if (data.pdfUrl) {
        window.open(data.pdfUrl, '_blank');
      } else {
        throw new Error('No PDF URL returned from server');
      }
    } catch (error) {
      console.error('Error downloading PDF:', error);
      alert(`Failed to download PDF: ${error.message}`);
    }
  };

  const status = getInvoiceStatus(invoice);
  const statusColor = STATUS_COLORS[status];
  const isPaid = invoice.status === "paid";
  const acc = config.accent;

  // Find associated monthly report
  const monthlyReport = findMonthlyReport(invoice, invoices);

  return (
    <>
      {/* Backdrop */}
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.5)",
          zIndex: 999,
          opacity: isAnimating ? 1 : 0,
          transition: "opacity 300ms ease-out"
        }}
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="invoice-detail-title"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(600px, 100vw)",
          background: "white",
          zIndex: 1000,
          display: "flex",
          flexDirection: "column",
          boxShadow: "-4px 0 24px rgba(0,0,0,0.2)",
          transform: isAnimating ? "translateX(0)" : "translateX(100%)",
          transition: "transform 300ms cubic-bezier(0.4, 0, 0.2, 1)"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          background: chrome.toolbar,
          borderBottom: `2px solid ${chrome.border}`,
          padding: "20px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0
        }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 12
          }}>
            <h2
              id="invoice-detail-title"
              style={{
                margin: 0,
                fontSize: 18,
                fontWeight: 700,
                color: chrome.brightText
              }}
            >
              Invoice Details
            </h2>

            {/* Status Badge */}
            <div style={{
              fontSize: 11,
              fontWeight: 700,
              padding: "5px 10px",
              borderRadius: 6,
              background: statusColor,
              color: "white",
              textTransform: "uppercase",
              letterSpacing: 0.5
            }}>
              {status}
            </div>
          </div>

          <button
            onClick={handleClose}
            aria-label="Close invoice details"
            style={{
              background: "none",
              border: "none",
              fontSize: 28,
              color: chrome.mutedText,
              cursor: "pointer",
              padding: "0 8px",
              lineHeight: 1,
              transition: "color 0.15s"
            }}
            onMouseEnter={(e) => e.target.style.color = chrome.brightText}
            onMouseLeave={(e) => e.target.style.color = chrome.mutedText}
          >
            ×
          </button>
        </div>

        {/* Content - Scrollable */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px",
          background: "#f9f3ee"
        }}>
          {/* Invoice Metadata Section */}
          <div style={{
            background: "white",
            borderRadius: 12,
            border: `1px solid ${chrome.border}`,
            padding: "20px",
            marginBottom: 20
          }}>
            <h3 style={{
              margin: "0 0 16px 0",
              fontSize: 14,
              fontWeight: 700,
              color: chrome.mutedText,
              textTransform: "uppercase",
              letterSpacing: 0.5
            }}>
              Invoice Information
            </h3>

            <div style={{
              display: "flex",
              flexDirection: "column",
              gap: 14
            }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: chrome.mutedText, marginBottom: 4 }}>
                  INVOICE NUMBER
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#6a4a40" }}>
                  {invoice.invoiceNumber || invoice.invoiceId}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: chrome.mutedText, marginBottom: 4 }}>
                  CLIENT
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, color: "#6a4a40" }}>
                  {invoice.clientId || "Unknown Client"}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: chrome.mutedText, marginBottom: 4 }}>
                  PERIOD
                </div>
                <div style={{ fontSize: 14, color: "#6a4a40" }}>
                  {invoice.weekStart} to {invoice.weekEnd}
                </div>
              </div>

              <div style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 14
              }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: chrome.mutedText, marginBottom: 4 }}>
                    TOTAL HOURS
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "#6a4a40" }}>
                    {invoice.totalHours || 0} hrs
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: chrome.mutedText, marginBottom: 4 }}>
                    HOURLY RATE
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "#6a4a40" }}>
                    ${(invoice.rate || 0).toFixed(2)}
                  </div>
                </div>
              </div>

              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: chrome.mutedText, marginBottom: 4 }}>
                  TOTAL AMOUNT
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: acc }}>
                  ${(invoice.totalPay || 0).toFixed(2)}
                </div>
              </div>

              {invoice.sentAt && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: chrome.mutedText, marginBottom: 4 }}>
                    SENT ON
                  </div>
                  <div style={{ fontSize: 14, color: "#6a4a40" }}>
                    {new Date(invoice.sentAt).toLocaleDateString("en-US", {
                      month: "long",
                      day: "numeric",
                      year: "numeric"
                    })}
                  </div>
                </div>
              )}

              {invoice.dueDate && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: chrome.mutedText, marginBottom: 4 }}>
                    DUE DATE
                  </div>
                  <div style={{ fontSize: 14, color: "#6a4a40" }}>
                    {new Date(invoice.dueDate).toLocaleDateString("en-US", {
                      month: "long",
                      day: "numeric",
                      year: "numeric"
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Mark as Paid Toggle */}
          <div style={{
            background: "white",
            borderRadius: 12,
            border: `1px solid ${chrome.border}`,
            padding: "16px 20px",
            marginBottom: 20,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            position: "relative",
            overflow: "hidden"
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#6a4a40", marginBottom: 3 }}>
                Payment Status
              </div>
              <div style={{ fontSize: 12, color: chrome.mutedText }}>
                {isPaid ? "This invoice has been marked as paid" : "Mark this invoice when payment is received"}
              </div>
            </div>

            <button
              onClick={handleTogglePaid}
              style={{
                fontSize: 13,
                fontWeight: 700,
                padding: "10px 20px",
                borderRadius: 8,
                border: isPaid ? `2px solid ${STATUS_COLORS.paid}` : `2px solid ${chrome.border}`,
                background: isPaid ? STATUS_COLORS.paid : "white",
                color: isPaid ? "white" : "#6a4a40",
                cursor: "pointer",
                transition: "all 0.2s",
                display: "flex",
                alignItems: "center",
                gap: 6,
                position: "relative",
                zIndex: 1
              }}
              onMouseEnter={(e) => {
                if (!isPaid) {
                  e.target.style.background = "#f9f3ee";
                }
              }}
              onMouseLeave={(e) => {
                if (!isPaid) {
                  e.target.style.background = "white";
                }
              }}
            >
              {isPaid ? "✓ Paid" : "Mark as Paid"}
            </button>

            {/* Celebratory animation overlay */}
            {showPaidAnimation && (
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: `linear-gradient(135deg, ${STATUS_COLORS.paid}22, ${STATUS_COLORS.paid}44)`,
                  animation: "pulse 1s ease-out",
                  pointerEvents: "none"
                }}
              />
            )}
          </div>

          {/* PDF Preview/Download Section */}
          <div style={{
            background: "white",
            borderRadius: 12,
            border: `1px solid ${chrome.border}`,
            padding: "20px",
            marginBottom: 20
          }}>
            <h3 style={{
              margin: "0 0 16px 0",
              fontSize: 14,
              fontWeight: 700,
              color: chrome.mutedText,
              textTransform: "uppercase",
              letterSpacing: 0.5
            }}>
              Documents
            </h3>

            {/* Invoice PDF */}
            <div style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "12px 16px",
              background: "#f9f3ee",
              borderRadius: 8,
              marginBottom: invoice.logPdfKey ? 10 : 0
            }}>
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 10
              }}>
                <span style={{ fontSize: 24 }}>📄</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#6a4a40" }}>
                    Invoice PDF
                  </div>
                  <div style={{ fontSize: 11, color: chrome.mutedText }}>
                    {invoice.invoiceNumber || invoice.invoiceId}
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleDownloadPdf('invoice')}
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: `1.5px solid ${acc}`,
                  background: "white",
                  color: acc,
                  cursor: "pointer",
                  transition: "all 0.15s"
                }}
                onMouseEnter={(e) => {
                  e.target.style.background = acc;
                  e.target.style.color = "white";
                }}
                onMouseLeave={(e) => {
                  e.target.style.background = "white";
                  e.target.style.color = acc;
                }}
              >
                Download
              </button>
            </div>

            {/* Service Log PDF (if exists) */}
            {invoice.logPdfKey && (
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 16px",
                background: "#f9f3ee",
                borderRadius: 8
              }}>
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10
                }}>
                  <span style={{ fontSize: 24 }}>📋</span>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#6a4a40" }}>
                      Service Log
                    </div>
                    <div style={{ fontSize: 11, color: chrome.mutedText }}>
                      Associated activity log
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => handleDownloadPdf('log')}
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    padding: "8px 16px",
                    borderRadius: 6,
                    border: `1.5px solid ${acc}`,
                    background: "white",
                    color: acc,
                    cursor: "pointer",
                    transition: "all 0.15s"
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.background = acc;
                    e.target.style.color = "white";
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.background = "white";
                    e.target.style.color = acc;
                  }}
                >
                  Download
                </button>
              </div>
            )}
          </div>

          {/* Monthly Report Link (if exists) */}
          {monthlyReport && (
            <div style={{
              background: "white",
              borderRadius: 12,
              border: `1px solid ${chrome.border}`,
              padding: "20px",
              marginBottom: 20
            }}>
              <h3 style={{
                margin: "0 0 12px 0",
                fontSize: 14,
                fontWeight: 700,
                color: chrome.mutedText,
                textTransform: "uppercase",
                letterSpacing: 0.5
              }}>
                Monthly Report
              </h3>

              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 16px",
                background: "#f9f3ee",
                borderRadius: 8,
                border: `1px solid ${chrome.border}`
              }}>
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10
                }}>
                  <span style={{ fontSize: 24 }}>📊</span>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#6a4a40" }}>
                      {monthlyReport.invoiceNumber || monthlyReport.invoiceId}
                    </div>
                    <div style={{ fontSize: 11, color: chrome.mutedText }}>
                      This invoice is included in this monthly report
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => onNavigate && onNavigate(monthlyReport)}
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    padding: "8px 16px",
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
                  View Report
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer - Sequential Navigation */}
        <div style={{
          background: chrome.toolbar,
          borderTop: `2px solid ${chrome.border}`,
          padding: "16px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0
        }}>
          <button
            onClick={handlePrev}
            disabled={!hasPrev}
            style={{
              fontSize: 13,
              fontWeight: 600,
              padding: "10px 20px",
              borderRadius: 8,
              border: `1.5px solid ${chrome.border}`,
              background: hasPrev ? "white" : chrome.toolbar,
              color: hasPrev ? "#6a4a40" : chrome.mutedText,
              cursor: hasPrev ? "pointer" : "not-allowed",
              transition: "all 0.15s",
              opacity: hasPrev ? 1 : 0.5
            }}
            onMouseEnter={(e) => {
              if (hasPrev) {
                e.target.style.background = "#f9f3ee";
              }
            }}
            onMouseLeave={(e) => {
              if (hasPrev) {
                e.target.style.background = "white";
              }
            }}
          >
            ← Previous
          </button>

          <div style={{
            fontSize: 12,
            color: chrome.brightText,
            fontWeight: 600
          }}>
            {currentIndex + 1} of {invoices.length}
          </div>

          <button
            onClick={handleNext}
            disabled={!hasNext}
            style={{
              fontSize: 13,
              fontWeight: 600,
              padding: "10px 20px",
              borderRadius: 8,
              border: `1.5px solid ${chrome.border}`,
              background: hasNext ? "white" : chrome.toolbar,
              color: hasNext ? "#6a4a40" : chrome.mutedText,
              cursor: hasNext ? "pointer" : "not-allowed",
              transition: "all 0.15s",
              opacity: hasNext ? 1 : 0.5
            }}
            onMouseEnter={(e) => {
              if (hasNext) {
                e.target.style.background = "#f9f3ee";
              }
            }}
            onMouseLeave={(e) => {
              if (hasNext) {
                e.target.style.background = "white";
              }
            }}
          >
            Next →
          </button>
        </div>
      </div>

      {/* CSS Animation for paid toggle */}
      <style>{`
        @keyframes pulse {
          0% {
            opacity: 0;
            transform: scale(0.95);
          }
          50% {
            opacity: 1;
            transform: scale(1.02);
          }
          100% {
            opacity: 0;
            transform: scale(1);
          }
        }
      `}</style>
    </>
  );
}
