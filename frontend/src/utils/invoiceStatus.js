/**
 * Invoice status utility functions.
 *
 * Shared logic for calculating invoice status including overdue detection.
 */

/**
 * Determine invoice status (including overdue calculation).
 *
 * @param {Object} invoice - Invoice object with status and dueDate fields
 * @returns {string} One of: "paid", "overdue", "sent", "draft"
 */
export function getInvoiceStatus(invoice) {
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
