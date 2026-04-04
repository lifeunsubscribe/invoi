/**
 * Authentication helpers for Invoi app
 *
 * TODO [Phase 1]: Replace stub implementation with real Cognito/Auth0 integration
 * This module provides a temporary auth implementation to unblock API integration work.
 *
 * Real implementation will:
 * - Use AWS Amplify or Auth0 SDK
 * - Handle OAuth flow with Google
 * - Store/refresh JWT tokens
 * - Provide sign-in/sign-out functions
 */

/**
 * Get the current authentication token for API requests.
 *
 * @returns {string|null} JWT token for Authorization header, or null if not authenticated
 *
 * TODO [Phase 1]: Replace with real token retrieval from Cognito/Auth0
 * For now, returns a stub token to unblock ProfilePage API integration.
 * The backend config.py currently has stub validation that checks for header presence.
 */
export function getAuthToken() {
  // TODO [Phase 1]: Replace stub with real token retrieval
  // Real implementation will be:
  // - For Cognito: fetchAuthSession().then(session => session.tokens?.idToken?.toString())
  // - For Auth0: await auth0.getTokenSilently()

  // Stub token for Phase 1 development
  // Backend currently validates presence but has TODO for full Cognito claim extraction
  return 'Bearer stub-jwt-token-phase1';
}

/**
 * Check if user is currently authenticated.
 *
 * @returns {boolean} True if user has valid auth session
 *
 * TODO [Phase 1]: Implement real auth state check
 */
export function isAuthenticated() {
  // TODO [Phase 1]: Check for valid Cognito/Auth0 session
  // Real implementation will check token expiry, refresh if needed

  // [Phase 5] Temporary: Check for ?authenticated=false in URL to demo landing page
  // This allows testing the unauthenticated landing page without breaking existing flows
  // Only available in development mode to prevent production bypass
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    if (params.get('authenticated') === 'false') {
      return false;
    }
  }

  return true; // Stub: assume always authenticated for Phase 1
}

/**
 * Get current authenticated user's email.
 *
 * @returns {string|null} User email from auth provider
 *
 * TODO [Phase 1]: Extract from real JWT claims
 */
export function getUserEmail() {
  // TODO [Phase 1]: Extract from Cognito/Auth0 user profile
  return 'user@example.com'; // Stub
}
