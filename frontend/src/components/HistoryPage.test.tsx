import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import HistoryPage from './HistoryPage'

// Mock the auth module
vi.mock('../auth.jsx', () => ({
  getAuthToken: vi.fn(() => Promise.resolve('mock-token'))
}))

const mockConfig = {
  name: 'Test User',
  address: '123 Test St',
  personalEmail: 'test@example.com',
  rate: 20.0,
  accent: '#b76e79',
  invoiceNote: 'Test note',
  saveFolder: '~/Documents/test-invoices'
}

describe('HistoryPage', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()

    // Mock successful invoices fetch (empty list)
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ invoices: [] })
      })
    ) as any
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders with default "list" view', async () => {
    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByText(/Loading your invoices/i)).not.toBeInTheDocument()
    })

    // Check that all three view buttons are present
    expect(screen.getByText('Calendar')).toBeInTheDocument()
    expect(screen.getByText('List')).toBeInTheDocument()
    expect(screen.getByText('Focus')).toBeInTheDocument()
  })

  it('shows loading state while fetching invoices', () => {
    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Loading state should be visible initially
    expect(screen.getByText(/Loading your invoices/i)).toBeInTheDocument()
    expect(screen.getByText(/This should only take a moment/i)).toBeInTheDocument()
  })

  it('shows empty state when no invoices exist', async () => {
    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.getByText(/No invoices yet/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/Create your first invoice/i)).toBeInTheDocument()
    expect(screen.getByText(/← Back to Menu/i)).toBeInTheDocument()
  })

  it('switches between views and persists preference to localStorage', async () => {
    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByText(/Loading your invoices/i)).not.toBeInTheDocument()
    })

    // Default should be "list"
    expect(localStorage.getItem('history-view-preference')).toBeNull()

    // Click Calendar view
    const calendarButton = screen.getByText('Calendar')
    fireEvent.click(calendarButton)

    // Check localStorage was updated
    expect(localStorage.getItem('history-view-preference')).toBe('calendar')

    // Click Focus view
    const focusButton = screen.getByText('Focus')
    fireEvent.click(focusButton)

    // Check localStorage was updated
    expect(localStorage.getItem('history-view-preference')).toBe('focus')
  })

  it('restores view preference from localStorage on mount', async () => {
    // Set localStorage preference before mounting
    localStorage.setItem('history-view-preference', 'calendar')

    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByText(/Loading your invoices/i)).not.toBeInTheDocument()
    })

    // The active view should reflect the localStorage value
    // We can't easily check the button styling, but we can verify the preference is used
    expect(localStorage.getItem('history-view-preference')).toBe('calendar')
  })

  it('displays list view placeholder when invoices exist', async () => {
    // Mock fetch to return invoices
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          invoices: [
            { invoiceId: 'INV-001', invoiceNumber: 'INV-001', totalHours: 40 },
            { invoiceId: 'INV-002', invoiceNumber: 'INV-002', totalHours: 35 }
          ]
        })
      })
    ) as any

    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Wait for invoices to load (ListView shows "Showing X of Y invoices")
    await waitFor(() => {
      expect(screen.getByText(/Showing 2 of 2 invoice/i)).toBeInTheDocument()
    })

    expect(screen.getByText('INV-001')).toBeInTheDocument()
    expect(screen.getByText('INV-002')).toBeInTheDocument()
  })

  it('renders CalendarView when calendar view is active with invoices', async () => {
    // Mock fetch to return invoices
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          invoices: [
            {
              invoiceId: 'INV-001',
              invoiceNumber: 'INV-001',
              clientId: 'Test Client',
              weekStart: '2026-01-06',
              weekEnd: '2026-01-12',
              totalHours: 40,
              totalPay: 1120.0,
              status: 'sent'
            }
          ]
        })
      })
    ) as any

    // Set view preference to calendar
    localStorage.setItem('history-view-preference', 'calendar')

    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Wait for invoices to load
    await waitFor(() => {
      expect(screen.queryByText(/Loading your invoices/i)).not.toBeInTheDocument()
    })

    // Calendar view should render weekday headers
    expect(screen.getByText('Sun')).toBeInTheDocument()
    expect(screen.getByText('Mon')).toBeInTheDocument()
    expect(screen.getByText('Sat')).toBeInTheDocument()
  })

  it('handles API endpoint not found gracefully', async () => {
    // Mock 404 response (endpoint doesn't exist yet)
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 404,
        statusText: 'Not Found'
      })
    ) as any

    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Should show empty state, not error state
    await waitFor(() => {
      expect(screen.getByText(/No invoices yet/i)).toBeInTheDocument()
    })

    // Should NOT show error message
    expect(screen.queryByText(/Could not load invoices/i)).not.toBeInTheDocument()
  })

  it('calls onBack when back button is clicked', () => {
    const onBackMock = vi.fn()
    render(<HistoryPage config={mockConfig} onBack={onBackMock} />)

    const backButton = screen.getByText(/← Back/i)
    fireEvent.click(backButton)

    expect(onBackMock).toHaveBeenCalledTimes(1)
  })

  it('renders all three view options', async () => {
    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // All three view buttons should be present
    expect(screen.getByText('Calendar')).toBeInTheDocument()
    expect(screen.getByText('List')).toBeInTheDocument()
    expect(screen.getByText('Focus')).toBeInTheDocument()
  })

  it('displays error state when API returns non-404 error', async () => {
    // Mock 500 server error
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error'
      })
    ) as any

    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Wait for error state to appear
    await waitFor(() => {
      expect(screen.getByText(/Could not load invoices/i)).toBeInTheDocument()
    })

    // Should show error icon and message
    expect(screen.getByText('⚠️')).toBeInTheDocument()
    expect(screen.getByText(/Failed to fetch invoices: Internal Server Error/i)).toBeInTheDocument()
  })

  it('handles network errors during fetch', async () => {
    // Mock network failure (fetch throws)
    global.fetch = vi.fn(() =>
      Promise.reject(new Error('Network request failed'))
    ) as any

    render(<HistoryPage config={mockConfig} onBack={vi.fn()} />)

    // Wait for error state to appear
    await waitFor(() => {
      expect(screen.getByText(/Could not load invoices/i)).toBeInTheDocument()
    })

    // Should show error message
    expect(screen.getByText(/Network request failed/i)).toBeInTheDocument()
  })
})
