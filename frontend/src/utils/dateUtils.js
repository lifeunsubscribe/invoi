/**
 * Date Utilities
 *
 * Provides timezone-safe date parsing utilities to prevent the common bug
 * where date-only strings like "2024-03-25" are parsed as UTC midnight,
 * causing the displayed date to shift in non-UTC timezones.
 */

/**
 * Parse a date string in local timezone (not UTC).
 *
 * When you write `new Date("2024-03-25")`, JavaScript parses it as UTC midnight,
 * which becomes 2024-03-24 4:00 PM in PST (UTC-8). This causes "overdue" calculations
 * and date displays to show the wrong day for users in timezones west of UTC.
 *
 * This function parses the date in the user's local timezone instead, ensuring
 * "2024-03-25" represents March 25 at midnight in the user's timezone, not UTC.
 *
 * @param {string} dateString - Date string in YYYY-MM-DD format (e.g., "2024-03-25")
 * @returns {Date} Date object representing midnight in local timezone
 *
 * @example
 * // User in PST timezone (UTC-8):
 * const utcParsed = new Date("2024-03-25");
 * // => 2024-03-24T16:00:00.000Z (displays as Mar 24 in PST)
 *
 * const localParsed = parseDateInLocalTimezone("2024-03-25");
 * // => 2024-03-25T08:00:00.000Z (displays as Mar 25 in PST) ✓
 */
export function parseDateInLocalTimezone(dateString) {
  if (!dateString) return null;

  // Validate YYYY-MM-DD format with regex
  const dateRegex = /^(\d{4})-(\d{2})-(\d{2})$/;
  const match = dateString.match(dateRegex);

  if (!match) {
    console.warn(`Invalid date format: ${dateString}. Expected YYYY-MM-DD.`);
    return null;
  }

  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10) - 1; // JavaScript months are 0-indexed
  const day = parseInt(match[3], 10);

  // Validate parsed values
  if (isNaN(year) || isNaN(month) || isNaN(day)) {
    console.warn(`Invalid date components in: ${dateString}`);
    return null;
  }

  // Validate month range (0-11 after conversion)
  if (month < 0 || month > 11) {
    console.warn(`Invalid month in: ${dateString}`);
    return null;
  }

  // Create Date in local timezone (this constructor uses local timezone, not UTC)
  const date = new Date(year, month, day);

  // Set time to midnight to ensure consistent comparison
  date.setHours(0, 0, 0, 0);

  return date;
}

/**
 * Get today's date at midnight in local timezone.
 *
 * Useful for date comparisons (e.g., checking if an invoice is overdue).
 *
 * @returns {Date} Today at 00:00:00 in local timezone
 */
export function getTodayAtMidnight() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today;
}
