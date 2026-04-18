import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { parseDateInLocalTimezone, getTodayAtMidnight } from './dateUtils.js';

describe('dateUtils', () => {
  describe('parseDateInLocalTimezone', () => {
    it('should parse YYYY-MM-DD format in local timezone', () => {
      const date = parseDateInLocalTimezone('2024-03-25');

      expect(date).toBeInstanceOf(Date);
      expect(date.getFullYear()).toBe(2024);
      expect(date.getMonth()).toBe(2); // March = 2 (0-indexed)
      expect(date.getDate()).toBe(25);
      expect(date.getHours()).toBe(0);
      expect(date.getMinutes()).toBe(0);
      expect(date.getSeconds()).toBe(0);
      expect(date.getMilliseconds()).toBe(0);
    });

    it('should return null for empty string', () => {
      expect(parseDateInLocalTimezone('')).toBe(null);
    });

    it('should return null for null', () => {
      expect(parseDateInLocalTimezone(null)).toBe(null);
    });

    it('should return null for undefined', () => {
      expect(parseDateInLocalTimezone(undefined)).toBe(null);
    });

    it('should return null for invalid format', () => {
      expect(parseDateInLocalTimezone('not-a-date')).toBe(null);
      expect(parseDateInLocalTimezone('2024/03/25')).toBe(null);
      expect(parseDateInLocalTimezone('03-25-2024')).toBe(null);
    });

    it('should return null for malformed date string', () => {
      expect(parseDateInLocalTimezone('2024-13-01')).toBe(null); // Invalid month
      expect(parseDateInLocalTimezone('2024-02-30')).not.toBe(null); // Date constructor accepts this
    });

    it('should handle different months correctly', () => {
      const jan = parseDateInLocalTimezone('2024-01-15');
      const dec = parseDateInLocalTimezone('2024-12-31');

      expect(jan.getMonth()).toBe(0); // January
      expect(dec.getMonth()).toBe(11); // December
    });

    it('should parse dates consistently regardless of timezone', () => {
      // This test ensures that "2024-03-25" always represents March 25 in local time,
      // not UTC midnight which would shift the day in some timezones
      const date = parseDateInLocalTimezone('2024-03-25');

      // The key assertion: getDate() should return 25, not 24 (which would happen with UTC parsing)
      expect(date.getDate()).toBe(25);
    });

    it('should create dates at midnight local time', () => {
      const date = parseDateInLocalTimezone('2024-06-15');

      expect(date.getHours()).toBe(0);
      expect(date.getMinutes()).toBe(0);
      expect(date.getSeconds()).toBe(0);
      expect(date.getMilliseconds()).toBe(0);
    });
  });

  describe('getTodayAtMidnight', () => {
    let originalDate;

    beforeEach(() => {
      // Save the original Date constructor
      originalDate = global.Date;
    });

    afterEach(() => {
      // Restore the original Date constructor
      global.Date = originalDate;
    });

    it('should return today at midnight', () => {
      const today = getTodayAtMidnight();
      const now = new Date();

      expect(today).toBeInstanceOf(Date);
      expect(today.getFullYear()).toBe(now.getFullYear());
      expect(today.getMonth()).toBe(now.getMonth());
      expect(today.getDate()).toBe(now.getDate());
      expect(today.getHours()).toBe(0);
      expect(today.getMinutes()).toBe(0);
      expect(today.getSeconds()).toBe(0);
      expect(today.getMilliseconds()).toBe(0);
    });

    it('should strip time component from current date', () => {
      const today = getTodayAtMidnight();

      // Even if called at 3:45 PM, should return midnight
      expect(today.getHours()).toBe(0);
      expect(today.getMinutes()).toBe(0);
    });
  });

  describe('date comparison scenarios', () => {
    it('should correctly identify overdue dates', () => {
      // Create yesterday at midnight local time
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      yesterday.setHours(0, 0, 0, 0);

      // Format as YYYY-MM-DD using local date components
      const year = yesterday.getFullYear();
      const month = String(yesterday.getMonth() + 1).padStart(2, '0');
      const day = String(yesterday.getDate()).padStart(2, '0');
      const yesterdayStr = `${year}-${month}-${day}`;

      const dueDate = parseDateInLocalTimezone(yesterdayStr);
      const today = getTodayAtMidnight();

      expect(dueDate < today).toBe(true);
    });

    it('should correctly identify non-overdue dates', () => {
      // Create tomorrow at midnight local time
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(0, 0, 0, 0);

      // Format as YYYY-MM-DD using local date components
      const year = tomorrow.getFullYear();
      const month = String(tomorrow.getMonth() + 1).padStart(2, '0');
      const day = String(tomorrow.getDate()).padStart(2, '0');
      const tomorrowStr = `${year}-${month}-${day}`;

      const dueDate = parseDateInLocalTimezone(tomorrowStr);
      const today = getTodayAtMidnight();

      expect(dueDate < today).toBe(false);
    });

    it('should handle today as not overdue', () => {
      // Create today using local date components
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const todayStr = `${year}-${month}-${day}`;

      const dueDate = parseDateInLocalTimezone(todayStr);
      const today = getTodayAtMidnight();

      // Today should not be considered overdue (dueDate >= today)
      expect(dueDate < today).toBe(false);
    });
  });
});
