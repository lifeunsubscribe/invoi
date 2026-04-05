import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import InvoiceDetailPanel from './InvoiceDetailPanel.jsx';

describe('InvoiceDetailPanel - Focus Trapping', () => {
  let mockInvoice;
  let mockConfig;
  let mockOnClose;
  let user;

  beforeEach(() => {
    // Setup common test data
    mockInvoice = {
      invoiceId: 'INV-001',
      invoiceNumber: 'INV-2026-001',
      clientId: 'Test Client',
      weekStart: '2026-01-01',
      weekEnd: '2026-01-07',
      totalHours: 40,
      rate: 100,
      totalPay: 4000,
      status: 'sent',
      pdfKey: 'invoices/test.pdf'
    };

    mockConfig = {
      accent: '#d4601a'
    };

    mockOnClose = vi.fn();
    user = userEvent.setup();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('should have proper ARIA attributes for accessibility', () => {
    render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
      />
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'invoice-detail-title');
  });

  it('should have a labeled dialog title', () => {
    render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
      />
    );

    const title = document.getElementById('invoice-detail-title');
    expect(title).toBeInTheDocument();
    expect(title).toHaveTextContent('Invoice Details');
  });

  it('should focus the close button when modal opens', async () => {
    render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
      />
    );

    // Wait for the animation delay (350ms) plus a buffer
    await waitFor(() => {
      const closeButton = screen.getByRole('button', { name: /close invoice details/i });
      expect(closeButton).toHaveFocus();
    }, { timeout: 500 });
  });

  it('should trap focus within the modal when tabbing forward', async () => {
    render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
        onNavigate={vi.fn()}
      />
    );

    // Wait for initial focus
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /close invoice details/i })).toHaveFocus();
    }, { timeout: 500 });

    const closeButton = screen.getByRole('button', { name: /close invoice details/i });
    const downloadButton = screen.getByRole('button', { name: /download/i });

    // Tab from close button to next focusable elements
    await user.tab();
    expect(screen.getByRole('button', { name: /mark as paid/i })).toHaveFocus();

    await user.tab();
    expect(downloadButton).toHaveFocus();

    // Tab from last focusable element - should cycle back to first (close button)
    // Previous and Next buttons are disabled when there's only one invoice
    await user.tab();
    expect(closeButton).toHaveFocus();
  });

  it('should trap focus within the modal when tabbing backward', async () => {
    render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
        onNavigate={vi.fn()}
      />
    );

    // Wait for initial focus on close button
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /close invoice details/i })).toHaveFocus();
    }, { timeout: 500 });

    // Shift+Tab from the first element should cycle to the last focusable element
    await user.tab({ shift: true });

    // The last focusable element should be the download button
    // (Previous and Next buttons are disabled when there's only one invoice)
    const downloadButton = screen.getByRole('button', { name: /download/i });
    expect(downloadButton).toHaveFocus();
  });

  it('should close the modal on Escape key', async () => {
    render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
      />
    );

    // Press Escape
    await user.keyboard('{Escape}');

    // Wait for the animation delay (300ms)
    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled();
    }, { timeout: 400 });
  });

  it('should restore focus to previously focused element when closed', async () => {
    // Create a trigger button and focus it BEFORE rendering the modal
    const triggerButton = document.createElement('button');
    triggerButton.setAttribute('data-testid', 'trigger-button');
    triggerButton.textContent = 'Open Invoice';
    document.body.appendChild(triggerButton);

    // Focus the trigger button BEFORE the modal renders
    triggerButton.focus();
    expect(triggerButton).toHaveFocus();

    // Now render the modal - it will capture the trigger button as previouslyFocusedElement
    const { unmount } = render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
      />
    );

    // Wait for modal to open and focus its close button
    await waitFor(() => {
      const closeButton = screen.getByRole('button', { name: /close invoice details/i });
      expect(closeButton).toHaveFocus();
    }, { timeout: 500 });

    // Verify trigger button lost focus
    expect(triggerButton).not.toHaveFocus();

    // Click close button
    const closeButton = screen.getByRole('button', { name: /close invoice details/i });
    await user.click(closeButton);

    // Wait for the close animation and focus restoration (300ms)
    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled();
      // Verify focus was actually restored to the trigger button
      expect(triggerButton).toHaveFocus();
    }, { timeout: 500 });

    // Cleanup
    document.body.removeChild(triggerButton);
  });

  it('should have aria-hidden on backdrop', () => {
    const { container } = render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
      />
    );

    // Find the backdrop div (the first div with fixed position)
    const backdrop = container.querySelector('[aria-hidden="true"]');
    expect(backdrop).toBeInTheDocument();
  });

  it('should handle focus trap with navigation buttons present', async () => {
    const invoices = [
      { ...mockInvoice, invoiceId: 'INV-001' },
      { ...mockInvoice, invoiceId: 'INV-002' },
      { ...mockInvoice, invoiceId: 'INV-003' }
    ];

    render(
      <InvoiceDetailPanel
        invoice={invoices[1]} // Middle invoice
        invoices={invoices}
        config={mockConfig}
        onClose={mockOnClose}
        onNavigate={vi.fn()}
      />
    );

    // Wait for focus
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /close invoice details/i })).toHaveFocus();
    }, { timeout: 500 });

    // Both prev and next buttons should be enabled and focusable
    const prevButton = screen.getByRole('button', { name: /previous/i });
    const nextButton = screen.getByRole('button', { name: /next/i });

    expect(prevButton).not.toBeDisabled();
    expect(nextButton).not.toBeDisabled();

    // Tab to next button and verify it's focusable
    await user.tab();
    await user.tab();
    await user.tab();

    // We should be able to focus on the navigation buttons
    expect(prevButton.matches(':focus') || nextButton.matches(':focus')).toBeTruthy();
  });

  it('should close modal when backdrop is clicked', async () => {
    const { container } = render(
      <InvoiceDetailPanel
        invoice={mockInvoice}
        invoices={[mockInvoice]}
        config={mockConfig}
        onClose={mockOnClose}
      />
    );

    // Find and click the backdrop
    const backdrop = container.querySelector('[aria-hidden="true"]');
    await user.click(backdrop);

    // Wait for the animation delay (300ms)
    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled();
    }, { timeout: 400 });
  });
});
