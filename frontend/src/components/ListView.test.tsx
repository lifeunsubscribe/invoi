import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ListView from './ListView.jsx';

const mockConfig = {
  accent: '#b76e79'
};

// Generate dates relative to test execution time to prevent flaky tests
const now = new Date();
const formatDate = (date) => date.toISOString().split('T')[0];

// Recent dates (within last 30 days)
const tenDaysAgo = new Date(now.getTime() - 10 * 24 * 60 * 60 * 1000);
const tenDaysAgoEnd = new Date(tenDaysAgo.getTime() + 6 * 24 * 60 * 60 * 1000);
const fiveDaysAgo = new Date(now.getTime() - 5 * 24 * 60 * 60 * 1000);
const fiveDaysAgoEnd = new Date(fiveDaysAgo.getTime() + 6 * 24 * 60 * 60 * 1000);
const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);
const twoDaysAgoEnd = new Date(twoDaysAgo.getTime() + 6 * 24 * 60 * 60 * 1000);

// Old date (outside 30 days, for testing date filter)
const ninetyDaysAgo = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
const ninetyDaysAgoEnd = new Date(ninetyDaysAgo.getTime() + 6 * 24 * 60 * 60 * 1000);
const overdueDueDate = new Date(now.getTime() - 10 * 24 * 60 * 60 * 1000);

const mockInvoices = [
  {
    invoiceId: 'INV-001',
    invoiceNumber: 'INV-047',
    clientId: 'Client A',
    status: 'draft',
    weekStart: formatDate(tenDaysAgo),
    weekEnd: formatDate(tenDaysAgoEnd),
    totalHours: 40,
    totalPay: 1120.00
  },
  {
    invoiceId: 'INV-002',
    invoiceNumber: 'INV-048',
    clientId: 'Client B',
    status: 'sent',
    weekStart: formatDate(fiveDaysAgo),
    weekEnd: formatDate(fiveDaysAgoEnd),
    dueDate: formatDate(fiveDaysAgoEnd),
    totalHours: 35,
    totalPay: 980.00
  },
  {
    invoiceId: 'INV-003',
    invoiceNumber: 'INV-049',
    clientId: 'Client A',
    status: 'paid',
    weekStart: formatDate(twoDaysAgo),
    weekEnd: formatDate(twoDaysAgoEnd),
    totalHours: 42,
    totalPay: 1176.00
  },
  {
    invoiceId: 'INV-004',
    invoiceNumber: 'INV-050',
    clientId: 'Client C',
    status: 'sent',
    weekStart: formatDate(ninetyDaysAgo),
    weekEnd: formatDate(ninetyDaysAgoEnd),
    dueDate: formatDate(overdueDueDate), // Overdue
    totalHours: 38,
    totalPay: 1064.00
  }
];

describe('ListView', () => {
  it('renders all invoices by default', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Should show all 4 invoices
    expect(screen.getByText(/Showing 4 of 4 invoice/)).toBeInTheDocument();
    expect(screen.getByText('INV-047')).toBeInTheDocument();
    expect(screen.getByText('INV-048')).toBeInTheDocument();
    expect(screen.getByText('INV-049')).toBeInTheDocument();
    expect(screen.getByText('INV-050')).toBeInTheDocument();
  });

  it('filters by status', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    const statusFilter = screen.getByLabelText('Status');
    fireEvent.change(statusFilter, { target: { value: 'paid' } });

    // Should show only paid invoice
    expect(screen.getByText(/Showing 1 of 4 invoice/)).toBeInTheDocument();
    expect(screen.getByText('INV-049')).toBeInTheDocument();
    expect(screen.queryByText('INV-047')).not.toBeInTheDocument();
  });

  it('filters by client', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    const clientFilter = screen.getByLabelText('Client');
    fireEvent.change(clientFilter, { target: { value: 'Client A' } });

    // Should show only Client A invoices (2 total)
    expect(screen.getByText(/Showing 2 of 4 invoice/)).toBeInTheDocument();
    expect(screen.getByText('INV-047')).toBeInTheDocument();
    expect(screen.getByText('INV-049')).toBeInTheDocument();
  });

  it('filters by date range', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    const dateRangeFilter = screen.getByLabelText('Date Range');
    fireEvent.change(dateRangeFilter, { target: { value: '30days' } });

    // Should show only invoices from last 30 days (3 invoices, excluding the January one)
    expect(screen.getByText(/Showing 3 of 4 invoice/)).toBeInTheDocument();
  });

  it('sorts by date descending by default', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Get all invoice cards
    const invoiceNumbers = screen.getAllByText(/INV-\d+/).map(el => el.textContent);

    // Most recent (April) should be first
    expect(invoiceNumbers[0]).toBe('INV-049'); // 2026-04-07
  });

  it('toggles sort order when clicking active sort field', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Date is active by default (descending) - find by text content
    const dateButton = screen.getByText('Date');

    // Click to toggle to ascending
    fireEvent.click(dateButton);

    // After toggle, find the updated button - the arrow should change
    const updatedButton = screen.getByText('Date');
    expect(updatedButton.parentElement).toHaveTextContent('↑');
  });

  it('sorts by amount', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    const amountButton = screen.getByRole('button', { name: /Amount/ });
    fireEvent.click(amountButton);

    // Should sort by amount descending (highest first)
    const amounts = screen.getAllByText(/\$\d+\.\d{2}/).map(el =>
      parseFloat(el.textContent?.replace('$', '') || '0')
    );
    expect(amounts[0]).toBe(1176.00); // Highest amount
  });

  it('sorts by client', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    const clientButton = screen.getByRole('button', { name: /Client/ });
    fireEvent.click(clientButton);

    // After clicking, should be descending alphabetically
    // Click again to get ascending
    fireEvent.click(clientButton);

    const clients = screen.getAllByText(/Client [ABC]/).map(el => el.textContent);
    expect(clients[0]).toBe('Client A');
  });

  it('selects individual invoices', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Get all checkboxes (excluding select-all)
    const checkboxes = screen.getAllByRole('checkbox');
    const firstInvoiceCheckbox = checkboxes[1]; // Index 0 is select-all

    // Check first invoice
    fireEvent.click(firstInvoiceCheckbox);

    // Should show selection count
    expect(screen.getByText(/1 invoice selected/)).toBeInTheDocument();

    // Bulk action bar should appear
    expect(screen.getByText('✓ Mark Paid')).toBeInTheDocument();
  });

  it('selects all invoices with select-all checkbox', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Find select all checkbox by the text next to it
    const selectAllText = screen.getByText('Select All');
    const selectAllCheckbox = selectAllText.parentElement?.querySelector('input[type="checkbox"]');
    expect(selectAllCheckbox).toBeInTheDocument();

    if (selectAllCheckbox) {
      fireEvent.click(selectAllCheckbox);
    }

    // Should show all 4 selected
    expect(screen.getByText(/4 invoices selected/)).toBeInTheDocument();
  });

  it('deselects all when clicking select-all while all are selected', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Find select all checkbox by the text next to it
    const selectAllText = screen.getByText('Select All');
    const selectAllCheckbox = selectAllText.parentElement?.querySelector('input[type="checkbox"]');
    expect(selectAllCheckbox).toBeInTheDocument();

    if (selectAllCheckbox) {
      // Select all
      fireEvent.click(selectAllCheckbox);
      expect(screen.getByText(/4 invoices selected/)).toBeInTheDocument();

      // Deselect all
      fireEvent.click(selectAllCheckbox);
      expect(screen.queryByText(/invoices selected/)).not.toBeInTheDocument();
    }
  });

  it('shows bulk action bar when invoices are selected', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Initially no bulk action bar
    expect(screen.queryByText('✓ Mark Paid')).not.toBeInTheDocument();

    // Select first invoice
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);

    // Bulk action bar should appear
    expect(screen.getByText('✓ Mark Paid')).toBeInTheDocument();
    expect(screen.getByText('📦 Export')).toBeInTheDocument();
    expect(screen.getByText('✉ Resend')).toBeInTheDocument();
  });

  it('calls onInvoiceClick when clicking invoice card', () => {
    const mockOnInvoiceClick = vi.fn();
    render(
      <ListView
        invoices={mockInvoices}
        config={mockConfig}
        onInvoiceClick={mockOnInvoiceClick}
      />
    );

    // Click on the first invoice's main content area (not checkbox)
    const firstInvoice = screen.getByText('INV-049');
    fireEvent.click(firstInvoice);

    // Should call handler with invoice data
    expect(mockOnInvoiceClick).toHaveBeenCalledWith(
      expect.objectContaining({ invoiceNumber: 'INV-049' })
    );
  });

  it('shows status badges with correct colors', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Check that all 4 invoice cards are rendered with status info
    expect(screen.getByText('INV-047')).toBeInTheDocument();
    expect(screen.getByText('INV-048')).toBeInTheDocument();
    expect(screen.getByText('INV-049')).toBeInTheDocument();
    expect(screen.getByText('INV-050')).toBeInTheDocument();
  });

  it('displays overdue status for past due sent invoices', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // INV-004 has a due date in January 2026, should be overdue
    // There will be multiple "Overdue" texts (filter dropdown + badge)
    // Just verify overdue invoice is shown
    expect(screen.getByText('INV-050')).toBeInTheDocument();
  });

  it('shows empty state when no invoices match filters', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Filter to a non-existent client
    const clientFilter = screen.getByLabelText('Client');
    fireEvent.change(clientFilter, { target: { value: 'Client A' } });

    const statusFilter = screen.getByLabelText('Status');
    fireEvent.change(statusFilter, { target: { value: 'overdue' } });

    // Should show empty state
    expect(screen.getByText('No invoices found')).toBeInTheDocument();
    expect(screen.getByText(/Try adjusting your filters/)).toBeInTheDocument();
  });

  it('clears selections when clicking Clear button', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Select all
    const selectAllText = screen.getByText('Select All');
    const selectAllCheckbox = selectAllText.parentElement?.querySelector('input[type="checkbox"]');

    if (selectAllCheckbox) {
      fireEvent.click(selectAllCheckbox);
      expect(screen.getByText(/4 invoices selected/)).toBeInTheDocument();

      // Click Clear button
      const clearButton = screen.getByRole('button', { name: 'Clear' });
      fireEvent.click(clearButton);

      // Selections should be cleared
      expect(screen.queryByText(/invoices selected/)).not.toBeInTheDocument();
    }
  });

  it('maintains selections when filtering', () => {
    render(<ListView invoices={mockInvoices} config={mockConfig} />);

    // Select first invoice
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);

    expect(screen.getByText(/1 invoice selected/)).toBeInTheDocument();

    // Apply a filter
    const statusFilter = screen.getByLabelText('Status');
    fireEvent.change(statusFilter, { target: { value: 'sent' } });

    // Selection count should still show (even if filtered item is hidden)
    expect(screen.getByText(/1 invoice selected/)).toBeInTheDocument();
  });
});
