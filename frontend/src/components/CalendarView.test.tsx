import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import CalendarView from './CalendarView'

const mockConfig = {
  name: 'Test User',
  accent: '#b76e79'
}

// Use current month for test invoices to ensure they show up
const now = new Date()
const year = now.getFullYear()
const month = String(now.getMonth() + 1).padStart(2, '0')

const mockInvoices = [
  {
    invoiceId: 'INV-20260401',
    invoiceNumber: 'INV-001',
    clientId: 'Sunrise Home Health',
    weekStart: `${year}-${month}-07`,
    weekEnd: `${year}-${month}-13`,
    totalHours: 40,
    totalPay: 1120.0,
    status: 'sent',
    dueDate: `${year}-${month}-13`
  },
  {
    invoiceId: 'INV-20260415',
    invoiceNumber: 'INV-002',
    clientId: 'Acme Corp',
    weekStart: `${year}-${month}-14`,
    weekEnd: `${year}-${month}-20`,
    totalHours: 35,
    totalPay: 980.0,
    status: 'paid'
  },
  {
    invoiceId: 'INV-20260420',
    invoiceNumber: 'INV-003',
    clientId: 'Test Client',
    weekStart: `${year}-${month}-21`,
    weekEnd: `${year}-${month}-27`,
    totalHours: 38,
    totalPay: 1064.0,
    status: 'draft'
  },
  {
    invoiceId: 'INV-20251215',
    invoiceNumber: 'INV-004',
    clientId: 'Overdue Inc',
    weekStart: '2025-12-15',
    weekEnd: '2025-12-21',
    totalHours: 42,
    totalPay: 1176.0,
    status: 'sent',
    dueDate: '2025-12-21'
  }
]

describe('CalendarView', () => {
  it('renders month navigation header with current month and year', () => {
    render(<CalendarView invoices={[]} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Should show a month name and year (current date)
    const monthYear = new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    const parts = monthYear.split(' ')

    expect(screen.getByText(new RegExp(parts[0]))).toBeInTheDocument()
    expect(screen.getByText(new RegExp(parts[1]))).toBeInTheDocument()
  })

  it('renders weekday headers', () => {
    render(<CalendarView invoices={[]} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Check all weekday labels
    expect(screen.getByText('Sun')).toBeInTheDocument()
    expect(screen.getByText('Mon')).toBeInTheDocument()
    expect(screen.getByText('Tue')).toBeInTheDocument()
    expect(screen.getByText('Wed')).toBeInTheDocument()
    expect(screen.getByText('Thu')).toBeInTheDocument()
    expect(screen.getByText('Fri')).toBeInTheDocument()
    expect(screen.getByText('Sat')).toBeInTheDocument()
  })

  it('renders calendar grid with 42 cells (6 weeks)', () => {
    const { container } = render(<CalendarView invoices={[]} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Find the calendar grid (should have 42 day cells after the weekday header)
    const gridContainer = container.querySelector('[style*="grid-template-rows"]')
    expect(gridContainer).toBeInTheDocument()

    // Grid should have 42 child divs (6 weeks × 7 days)
    const dayCells = gridContainer?.children
    expect(dayCells?.length).toBe(42)
  })

  it('renders invoice pills with correct content', () => {
    render(<CalendarView invoices={mockInvoices} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Should show client initials, hours, and amount
    // "Sunrise Home Health" -> "SH"
    expect(screen.getByText(/SH/)).toBeInTheDocument()
    // "Acme Corp" -> "AC"
    expect(screen.getByText(/AC/)).toBeInTheDocument()
  })

  it('calls onInvoiceClick when pill is clicked', () => {
    const onInvoiceClickMock = vi.fn()
    render(<CalendarView invoices={mockInvoices} config={mockConfig} onInvoiceClick={onInvoiceClickMock} />)

    // Find and click an invoice pill
    const pill = screen.getByText(/SH/)
    fireEvent.click(pill)

    // Should have called the handler with the invoice
    expect(onInvoiceClickMock).toHaveBeenCalledTimes(1)
    expect(onInvoiceClickMock).toHaveBeenCalledWith(
      expect.objectContaining({
        invoiceId: 'INV-20260401',
        clientId: 'Sunrise Home Health'
      })
    )
  })

  it('navigates to previous month when ‹ button clicked', () => {
    const { container } = render(<CalendarView invoices={[]} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Get current month
    const currentMonth = new Date().getMonth()

    // Click previous month button
    const prevButton = screen.getByText('‹')
    fireEvent.click(prevButton)

    // Calculate expected previous month
    const expectedMonth = currentMonth === 0 ? 11 : currentMonth - 1
    const monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ]

    // Should show previous month
    expect(screen.getByText(new RegExp(monthNames[expectedMonth]))).toBeInTheDocument()
  })

  it('navigates to next month when › button clicked', () => {
    render(<CalendarView invoices={[]} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Get current month
    const currentMonth = new Date().getMonth()

    // Click next month button
    const nextButton = screen.getByText('›')
    fireEvent.click(nextButton)

    // Calculate expected next month
    const expectedMonth = (currentMonth + 1) % 12
    const monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ]

    // Should show next month
    expect(screen.getByText(new RegExp(monthNames[expectedMonth]))).toBeInTheDocument()
  })

  it('renders status legend with all status types', () => {
    render(<CalendarView invoices={[]} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Check legend labels
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByText('Sent')).toBeInTheDocument()
    expect(screen.getByText('Paid')).toBeInTheDocument()
    expect(screen.getByText('Overdue')).toBeInTheDocument()
  })

  it('groups multiple invoices on the same date', () => {
    const now = new Date()
    const year = now.getFullYear()
    const month = String(now.getMonth() + 1).padStart(2, '0')

    const sameDateInvoices = [
      {
        invoiceId: 'INV-001',
        invoiceNumber: 'INV-001',
        clientId: 'Client A',
        weekStart: `${year}-${month}-07`,
        weekEnd: `${year}-${month}-13`,
        totalHours: 40,
        totalPay: 1120.0,
        status: 'sent'
      },
      {
        invoiceId: 'INV-002',
        invoiceNumber: 'INV-002',
        clientId: 'Client B',
        weekStart: `${year}-${month}-07`,
        weekEnd: `${year}-${month}-13`,
        totalHours: 35,
        totalPay: 980.0,
        status: 'paid'
      }
    ]

    render(<CalendarView invoices={sameDateInvoices} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Both client initials should be present (multiple pills in same cell)
    expect(screen.getByText(/CA/)).toBeInTheDocument()
    expect(screen.getByText(/CB/)).toBeInTheDocument()
  })

  it('extracts client initials correctly from different name formats', () => {
    const now = new Date()
    const year = now.getFullYear()
    const month = String(now.getMonth() + 1).padStart(2, '0')

    const diverseNameInvoices = [
      {
        invoiceId: 'INV-001',
        invoiceNumber: 'INV-001',
        clientId: 'Single',
        weekStart: `${year}-${month}-07`,
        weekEnd: `${year}-${month}-13`,
        totalHours: 40,
        totalPay: 1120.0,
        status: 'sent'
      },
      {
        invoiceId: 'INV-002',
        invoiceNumber: 'INV-002',
        clientId: 'Two Words',
        weekStart: `${year}-${month}-14`,
        weekEnd: `${year}-${month}-20`,
        totalHours: 35,
        totalPay: 980.0,
        status: 'sent'
      }
    ]

    render(<CalendarView invoices={diverseNameInvoices} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // "Single" -> "SI"
    expect(screen.getByText(/SI/)).toBeInTheDocument()
    // "Two Words" -> "TW"
    expect(screen.getByText(/TW/)).toBeInTheDocument()
  })

  it('handles empty invoices array gracefully', () => {
    const { container } = render(<CalendarView invoices={[]} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Should still render the calendar grid
    const gridContainer = container.querySelector('[style*="grid-template-rows"]')
    expect(gridContainer).toBeInTheDocument()

    // Should show month/year and weekday headers
    expect(screen.getByText('Sun')).toBeInTheDocument()
  })

  it('displays status indicators on pills', () => {
    const { container } = render(<CalendarView invoices={mockInvoices} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Different statuses should have different indicators
    // Find the paid invoice pill (Acme Corp)
    const paidPillText = screen.getByText(/AC • 35h • \$980/)
    expect(paidPillText).toBeInTheDocument()

    // The parent button should contain the checkmark in a sibling span
    const paidButton = paidPillText.closest('button')
    expect(paidButton?.textContent).toContain('✓')
  })

  it('formats invoice amount without decimals', () => {
    render(<CalendarView invoices={mockInvoices} config={mockConfig} onInvoiceClick={vi.fn()} />)

    // Should display amounts like "$1120" not "$1120.00"
    expect(screen.getByText(/\$1120/)).toBeInTheDocument()
    expect(screen.getByText(/\$980/)).toBeInTheDocument()
  })
})
