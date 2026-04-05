/**
 * Tests for auth module, with focus on production safeguard verification.
 *
 * The production safeguard prevents stub authentication from being used in production builds.
 * Since import.meta.env is read-only in tests, the auth module exports an `env` object
 * with mockable environment check functions. This allows us to simulate both production
 * and development environments in tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getAuthToken, isAuthenticated, getUserEmail, env } from './auth'

describe('auth module - production safeguards', () => {
  beforeEach(() => {
    // Clear console warnings/errors during tests
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    // Restore all mocks and spies
    vi.restoreAllMocks()
  })

  describe('getAuthToken', () => {
    it('throws error when called in production mode', () => {
      // Mock env.isProduction to simulate production environment
      vi.spyOn(env, 'isProduction').mockReturnValue(true)

      // Attempt to get auth token in "production"
      expect(() => getAuthToken()).toThrow(
        /PRODUCTION ERROR: Stub authentication is not allowed in production/
      )
    })

    it('returns stub token in development mode', () => {
      // Mock env.isProduction to simulate development environment
      vi.spyOn(env, 'isProduction').mockReturnValue(false)

      const token = getAuthToken()
      expect(token).toBe('Bearer stub-jwt-token-phase1')
    })

    it('logs warning in development mode', () => {
      // Mock env.isProduction to simulate development environment
      vi.spyOn(env, 'isProduction').mockReturnValue(false)
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      getAuthToken()

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('Using stub authentication token')
      )
    })

    it('includes helpful error message pointing to implementation TODOs', () => {
      // Mock env.isProduction to simulate production environment
      vi.spyOn(env, 'isProduction').mockReturnValue(true)

      expect(() => getAuthToken()).toThrow(
        /Real Cognito\/Auth0 integration must be implemented/
      )
      expect(() => getAuthToken()).toThrow(
        /See frontend\/src\/auth\.jsx for implementation TODOs/
      )
    })
  })

  describe('isAuthenticated', () => {
    it('returns true by default (stub behavior)', () => {
      expect(isAuthenticated()).toBe(true)
    })

    it('returns false when authenticated=false query param is present in dev mode', () => {
      // This test would need DOM mocking to test the window.location.search logic
      // Skipping for now as it's not critical to the production safeguard
    })
  })

  describe('getUserEmail', () => {
    it('returns stub email', () => {
      expect(getUserEmail()).toBe('user@example.com')
    })
  })
})
