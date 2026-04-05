/**
 * PKCE (Proof Key for Code Exchange) utilities for OAuth 2.0 authorization code flow
 *
 * PKCE is a security extension to OAuth 2.0 that protects against authorization code
 * interception attacks. It's required for public clients like SPAs that cannot securely
 * store client secrets.
 *
 * Flow:
 * 1. Generate a random code_verifier (cryptographically random string)
 * 2. Create code_challenge by hashing the verifier with SHA-256
 * 3. Send code_challenge with authorization request
 * 4. Store code_verifier in sessionStorage
 * 5. Exchange authorization code + code_verifier for tokens
 *
 * AWS Cognito requires the S256 challenge method (SHA-256).
 *
 * @see https://datatracker.ietf.org/doc/html/rfc7636
 * @see https://docs.aws.amazon.com/cognito/latest/developerguide/using-pkce-in-authorization-code.html
 */

// SessionStorage key for storing the code verifier during OAuth flow
const VERIFIER_KEY = 'pkce_code_verifier';

/**
 * Generate a cryptographically random code verifier for PKCE.
 *
 * The verifier must be a high-entropy cryptographic random string using the
 * unreserved characters [A-Z] / [a-z] / [0-9] / "-" / "." / "_" / "~".
 *
 * Per RFC 7636, the verifier should be at least 43 characters and no more than 128 characters.
 * We use 128 characters for maximum entropy.
 *
 * @returns {string} A base64url-encoded random string (128 characters)
 */
export function generateCodeVerifier() {
  // Generate 96 random bytes (will become 128 base64url characters)
  // 96 bytes * 4/3 (base64 encoding ratio) = 128 characters
  const randomBytes = new Uint8Array(96);
  crypto.getRandomValues(randomBytes);

  // Convert to base64url encoding (RFC 4648 Section 5)
  // base64url uses - and _ instead of + and /, and removes padding =
  return base64UrlEncode(randomBytes);
}

/**
 * Generate a code challenge from a code verifier using SHA-256 hashing.
 *
 * AWS Cognito only supports the S256 challenge method, which creates the challenge as:
 * BASE64URL(SHA256(ASCII(code_verifier)))
 *
 * @param {string} verifier - The code verifier to hash
 * @returns {Promise<string>} A promise that resolves to the base64url-encoded SHA-256 hash
 */
export async function generateCodeChallenge(verifier) {
  // Encode the verifier as ASCII bytes
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);

  // Hash with SHA-256 using Web Crypto API
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);

  // Convert ArrayBuffer to Uint8Array and encode as base64url
  const hashArray = new Uint8Array(hashBuffer);
  return base64UrlEncode(hashArray);
}

/**
 * Store the code verifier in sessionStorage for later retrieval during token exchange.
 *
 * SessionStorage is appropriate because:
 * - It's cleared when the browser tab closes (reducing exposure window)
 * - It's isolated per tab (supporting multiple concurrent auth flows)
 * - It persists across page reloads during the OAuth redirect
 *
 * @param {string} verifier - The code verifier to store
 */
export function storePKCEVerifier(verifier) {
  sessionStorage.setItem(VERIFIER_KEY, verifier);
}

/**
 * Retrieve the stored code verifier from sessionStorage.
 *
 * Called during the OAuth callback to get the verifier for token exchange.
 *
 * @returns {string|null} The stored code verifier, or null if not found
 */
export function retrievePKCEVerifier() {
  return sessionStorage.getItem(VERIFIER_KEY);
}

/**
 * Clear the stored code verifier from sessionStorage.
 *
 * Should be called after successful token exchange or on auth errors to prevent reuse.
 *
 * @returns {void}
 */
export function clearPKCEVerifier() {
  sessionStorage.removeItem(VERIFIER_KEY);
}

/**
 * Complete PKCE setup for an authorization request.
 *
 * Convenience function that generates both verifier and challenge,
 * stores the verifier, and returns the challenge for the auth URL.
 *
 * @returns {Promise<{verifier: string, challenge: string}>} The verifier and challenge
 *
 * @example
 * const { challenge } = await setupPKCE();
 * const authUrl = `${cognitoUrl}/oauth2/authorize?` +
 *   `response_type=code&` +
 *   `client_id=${clientId}&` +
 *   `redirect_uri=${redirectUri}&` +
 *   `code_challenge=${challenge}&` +
 *   `code_challenge_method=S256`;
 * window.location.href = authUrl;
 */
export async function setupPKCE() {
  const verifier = generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);
  storePKCEVerifier(verifier);

  return { verifier, challenge };
}

/**
 * Helper function to encode a Uint8Array as base64url.
 *
 * base64url encoding (RFC 4648 Section 5) is base64 with URL-safe characters:
 * - Replace + with -
 * - Replace / with _
 * - Remove padding =
 *
 * @param {Uint8Array} buffer - The bytes to encode
 * @returns {string} The base64url-encoded string
 */
function base64UrlEncode(buffer) {
  // Convert bytes to binary string
  let binary = '';
  for (let i = 0; i < buffer.length; i++) {
    binary += String.fromCharCode(buffer[i]);
  }

  // Encode as base64
  const base64 = btoa(binary);

  // Convert to base64url format
  return base64
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}
