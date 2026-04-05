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
 *
 * SECURITY: PKCE Implementation Required
 * PKCE (Proof Key for Code Exchange) utilities are available in utils/pkce.js
 * and MUST be used when implementing the real OAuth authorization code flow.
 *
 * Integration steps:
 * 1. Import { setupPKCE, retrievePKCEVerifier, clearPKCEVerifier } from './utils/pkce'
 * 2. Before redirecting to Cognito OAuth:
 *    const { challenge } = await setupPKCE();
 *    const authUrl = `${cognitoUrl}/oauth2/authorize?
 *      response_type=code&
 *      client_id=${clientId}&
 *      redirect_uri=${redirectUri}&
 *      code_challenge=${challenge}&
 *      code_challenge_method=S256&
 *      scope=email+openid+profile`;
 *    window.location.href = authUrl;
 *
 * 3. In OAuth callback handler (when receiving authorization code):
 *    const code_verifier = retrievePKCEVerifier();
 *    // Exchange code + verifier for tokens at /oauth2/token endpoint
 *    // Include code_verifier in POST body
 *    clearPKCEVerifier(); // After successful token exchange
 *
 * See docs/security/PKCE-IMPLEMENTATION.md for detailed implementation guide.
 */

import { useCallback } from 'react';

/**
 * Get the current authentication token for API requests.
 *
 * @returns {string|null} JWT token for Authorization header, or null if not authenticated
 *
 * TODO [Phase 1]: Replace with real token retrieval from Cognito/Auth0
 * For now, returns a stub token to unblock ProfilePage API integration.
 * The backend config.py currently has stub validation that checks for header presence.
 */
function getAuthTokenImpl() {
  // TODO [Phase 1]: Replace stub with real token retrieval
  // Real implementation will be:
  // - For Cognito: fetchAuthSession().then(session => session.tokens?.idToken?.toString())
  // - For Auth0: await auth0.getTokenSilently()

  // PRODUCTION SAFEGUARD: Prevent stub authentication from reaching production
  // This check ensures the app fails fast if deployed to production without real auth
  if (import.meta.env.PROD) {
    throw new Error(
      'PRODUCTION ERROR: Stub authentication is not allowed in production. ' +
      'Real Cognito/Auth0 integration must be implemented before production deployment. ' +
      'See frontend/src/auth.jsx for implementation TODOs.'
    );
  }

  // Development-only warning to remind developers this is temporary
  if (import.meta.env.DEV && typeof console !== 'undefined') {
    console.warn(
      '[DEV WARNING] Using stub authentication token. ' +
      'This is for development only and will not work in production.'
    );
  }

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
function isAuthenticatedImpl() {
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
 * Hook to get a stable reference to getAuthToken.
 * Prevents unnecessary re-renders when used in dependency arrays.
 */
export function useGetAuthToken() {
  return useCallback(getAuthTokenImpl, []);
}

/**
 * Hook to get a stable reference to isAuthenticated.
 * Prevents unnecessary re-renders when used in dependency arrays.
 */
export function useIsAuthenticated() {
  return useCallback(isAuthenticatedImpl, []);
}

// Export the raw functions for backwards compatibility
// These should only be used outside of React components
export const getAuthToken = getAuthTokenImpl;
export const isAuthenticated = isAuthenticatedImpl;

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
