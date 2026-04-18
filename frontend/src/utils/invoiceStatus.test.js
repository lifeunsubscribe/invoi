import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getInvoiceStatus } from './invoiceStatus.js';

describe('getInvoiceStatus', () => {
  // Mock Date.now() to ensure consistent test results
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-15T00:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should return "paid" for paid invoices', () => {
    const invoice = { status: 'paid' };
    expect(getInvoiceStatus(invoice)).toBe('paid');
  });

  it('should return "draft" for draft invoices', () => {
    const invoice = { status: 'draft' };
    expect(getInvoiceStatus(invoice)).toBe('draft');
  });

  it('should return "sent" for sent invoices without dueDate', () => {
    const invoice = { status: 'sent' };
    expect(getInvoiceStatus(invoice)).toBe('sent');
  });

  it('should return "sent" for sent invoices not yet overdue', () => {
    const invoice = {
      status: 'sent',
      dueDate: '2026-04-20' // Future date
    };
    expect(getInvoiceStatus(invoice)).toBe('sent');
  });

  it('should return "overdue" for sent invoices past due date', () => {
    const invoice = {
      status: 'sent',
      dueDate: '2026-04-10' // Past date
    };
    expect(getInvoiceStatus(invoice)).toBe('overdue');
  });

  it('should return "overdue" for sent invoices due today (boundary case)', () => {
    const invoice = {
      status: 'sent',
      dueDate: '2026-04-14' // Yesterday
    };
    expect(getInvoiceStatus(invoice)).toBe('overdue');
  });

  it('should return "draft" for invoices with no status', () => {
    const invoice = {};
    expect(getInvoiceStatus(invoice)).toBe('draft');
  });

  it('should return "paid" regardless of dueDate for paid invoices', () => {
    const invoice = {
      status: 'paid',
      dueDate: '2026-04-01' // Past due, but paid
    };
    expect(getInvoiceStatus(invoice)).toBe('paid');
  });
});
