# PKCE Implementation Guide

## Overview

PKCE (Proof Key for Code Exchange, pronounced "pixy") is a security extension to the OAuth 2.0 authorization code flow that protects against authorization code interception attacks. It is **required** for public clients like single-page applications (SPAs) that cannot securely store client secrets.

**Status**: PKCE utilities are implemented in `frontend/src/utils/pkce.js` and ready for integration when the real OAuth flow is implemented.

## Why PKCE is Required

### The Security Problem

In a traditional OAuth authorization code flow for SPAs:
1. User is redirected to authorization server (Cognito)
2. After authentication, authorization server redirects back with an authorization code
3. App exchanges code for access tokens

**Attack Vector**: An attacker who intercepts the authorization code (e.g., through a malicious app, compromised redirect URI, or browser history) can exchange it for tokens, gaining unauthorized access to the user's account.

### How PKCE Mitigates the Attack

PKCE adds a cryptographic binding between the authorization request and token exchange:

1. **Authorization Request**: Client generates a random `code_verifier` and sends a SHA-256 hash (`code_challenge`) to the authorization server
2. **Token Exchange**: Client proves possession of the original `code_verifier` when exchanging the authorization code

An attacker who intercepts only the authorization code cannot complete the token exchange without the `code_verifier`, which is stored securely in the client's sessionStorage.

## Architecture

### Flow Diagram

```
┌─────────────┐                                        ┌─────────────┐
│             │  1. Generate code_verifier             │             │
│  React SPA  │     Generate code_challenge (SHA-256)  │   Cognito   │
│             │                                         │   (OAuth)   │
└──────┬──────┘                                        └──────┬──────┘
       │                                                      │
       │ 2. Redirect to /oauth2/authorize                    │
       │    ?code_challenge=...&code_challenge_method=S256   │
       ├────────────────────────────────────────────────────>│
       │                                                      │
       │                                                 3. User logs in
       │                                                 with Google
       │                                                      │
       │ 4. Redirect to callback with authorization code     │
       │<─────────────────────────────────────────────────────┤
       │                                                      │
       │ 5. POST to /oauth2/token                            │
       │    code=...&code_verifier=...                       │
       ├─────────────────────────────────────────────────────>│
       │                                                      │
       │                                              6. Validate:
       │                                              SHA256(verifier)
       │                                              == stored challenge
       │                                                      │
       │ 7. Return access_token, id_token, refresh_token     │
       │<─────────────────────────────────────────────────────┤
       │                                                      │
```

### Components

#### PKCE Utilities (`frontend/src/utils/pkce.js`)

Provides cryptographically secure functions for PKCE:

- `generateCodeVerifier()` - Creates 128-character random string using Web Crypto API
- `generateCodeChallenge(verifier)` - Hashes verifier with SHA-256, encodes as base64url
- `storePKCEVerifier(verifier)` - Stores verifier in sessionStorage
- `retrievePKCEVerifier()` - Retrieves stored verifier for token exchange
- `clearPKCEVerifier()` - Removes verifier after auth (security cleanup)
- `setupPKCE()` - Convenience function that generates both verifier and challenge

#### SessionStorage Security

We use `sessionStorage` (not `localStorage`) because:
- **Tab-isolated**: Each browser tab has independent storage, preventing cross-tab attacks
- **Session-scoped**: Cleared when tab closes, reducing exposure window
- **Persists redirects**: Survives page reload during OAuth redirect flow

## Implementation Guide

### Prerequisites

Before implementing PKCE, ensure:
- [ ] Cognito User Pool is configured with OAuth authorization code flow (`sst.config.ts:70`)
- [ ] Callback URLs are registered in Cognito app client (`sst.config.ts:64-69`)
- [ ] Frontend environment variables are set (VITE_COGNITO_DOMAIN, VITE_COGNITO_CLIENT_ID)

### Step 1: Authorization Request (Login)

When the user clicks "Sign in with Google", redirect to Cognito with PKCE parameters:

```javascript
import { setupPKCE } from './utils/pkce';

async function initiateLogin() {
  // Generate PKCE challenge and store verifier
  const { challenge } = await setupPKCE();

  // Build Cognito authorization URL
  const cognitoUrl = import.meta.env.VITE_COGNITO_DOMAIN;
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  const redirectUri = window.location.origin + '/auth/callback';

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: redirectUri,
    code_challenge: challenge,
    code_challenge_method: 'S256',  // AWS Cognito requires S256
    scope: 'email openid profile',
    identity_provider: 'Google',    // Optional: direct to Google IdP
  });

  // Redirect to Cognito hosted UI
  window.location.href = `${cognitoUrl}/oauth2/authorize?${params}`;
}
```

### Step 2: OAuth Callback Handler

Handle the OAuth redirect at `/auth/callback`:

```javascript
import { retrievePKCEVerifier, clearPKCEVerifier } from './utils/pkce';

async function handleOAuthCallback() {
  // Extract authorization code from URL
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const error = params.get('error');

  if (error) {
    console.error('OAuth error:', error);
    clearPKCEVerifier(); // Clean up on error
    // Redirect to login page or show error
    return;
  }

  if (!code) {
    console.error('No authorization code received');
    clearPKCEVerifier();
    return;
  }

  // Retrieve the stored code verifier
  const codeVerifier = retrievePKCEVerifier();
  if (!codeVerifier) {
    console.error('PKCE verifier not found - possible CSRF attack');
    // Redirect to login page
    return;
  }

  try {
    // Exchange code + verifier for tokens
    await exchangeCodeForTokens(code, codeVerifier);

    // Clean up verifier after successful exchange
    clearPKCEVerifier();

    // Redirect to main app
    window.location.href = '/';
  } catch (err) {
    console.error('Token exchange failed:', err);
    clearPKCEVerifier();
    // Handle error (redirect to login, show message, etc.)
  }
}
```

### Step 3: Token Exchange

Exchange the authorization code and verifier for tokens:

```javascript
async function exchangeCodeForTokens(code, codeVerifier) {
  const cognitoUrl = import.meta.env.VITE_COGNITO_DOMAIN;
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  const redirectUri = window.location.origin + '/auth/callback';

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: clientId,
    code: code,
    code_verifier: codeVerifier,  // PKCE: prove possession of verifier
    redirect_uri: redirectUri,
  });

  const response = await fetch(`${cognitoUrl}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: body.toString(),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Token exchange failed: ${error}`);
  }

  const tokens = await response.json();
  // tokens = { access_token, id_token, refresh_token, expires_in, token_type }

  // Store tokens securely (consider using a token manager library)
  // DO NOT store in localStorage - use sessionStorage or memory
  sessionStorage.setItem('id_token', tokens.id_token);
  sessionStorage.setItem('access_token', tokens.access_token);
  sessionStorage.setItem('refresh_token', tokens.refresh_token);

  return tokens;
}
```

### Step 4: Error Handling

Always clean up the PKCE verifier to prevent reuse:

```javascript
// On any auth error
clearPKCEVerifier();

// On successful token exchange
clearPKCEVerifier();

// On user logout
clearPKCEVerifier();
```

## Testing

### Unit Tests

PKCE utilities have comprehensive test coverage in `frontend/src/utils/pkce.test.js`:

```bash
npm test pkce.test.js
```

Tests verify:
- Code verifier generation (128 characters, base64url, high entropy)
- Code challenge hashing (SHA-256, RFC 7636 test vectors)
- Storage operations (sessionStorage isolation)
- End-to-end PKCE flow
- Security properties (cryptographic randomness, irreversible hashing)

### Integration Testing

Manual testing checklist:

1. **Happy Path**:
   - [ ] Click login → redirected to Cognito with `code_challenge` parameter
   - [ ] Authenticate with Google → redirected to callback with authorization code
   - [ ] Token exchange succeeds with `code_verifier`
   - [ ] Verifier is cleared from sessionStorage after exchange

2. **Error Cases**:
   - [ ] Missing verifier in callback → auth fails gracefully
   - [ ] Invalid code → token exchange fails, verifier cleared
   - [ ] User cancels auth → verifier cleared

3. **Security**:
   - [ ] Code challenge in URL is different from code verifier in storage
   - [ ] Verifier cannot be derived from challenge (SHA-256 is one-way)
   - [ ] Multiple tabs maintain separate verifiers (sessionStorage isolation)

### Security Testing

Verify PKCE protection against attacks:

```bash
# Attempt to exchange authorization code without verifier
curl -X POST "${COGNITO_DOMAIN}/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&client_id=${CLIENT_ID}&code=${CODE}&redirect_uri=${REDIRECT_URI}"
# Expected: 400 Bad Request - "PKCE verification failed"

# Attempt with wrong verifier
curl -X POST "${COGNITO_DOMAIN}/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&client_id=${CLIENT_ID}&code=${CODE}&code_verifier=wrong&redirect_uri=${REDIRECT_URI}"
# Expected: 400 Bad Request - "PKCE verification failed"
```

## AWS Cognito Configuration

### Current Configuration

The Cognito User Pool app client is configured in `sst.config.ts:60-73`:

```typescript
const userPoolClient = userPool.addClient("Web", {
  providers: ["Google"],
  oauth: {
    callbackUrls: [
      $dev ? "http://localhost:5173/auth/callback" : "https://goinvoi.com/auth/callback"
    ],
    logoutUrls: [
      $dev ? "http://localhost:5173/auth/logout" : "https://goinvoi.com/auth/logout"
    ],
    flows: ["authorization_code"],  // ✓ Correct flow for PKCE
    scopes: ["email", "openid", "profile"],
  },
});
```

### PKCE Configuration

**No infrastructure changes required**. AWS Cognito automatically supports PKCE when:
1. The app client uses `authorization_code` flow (already configured)
2. The authorization request includes `code_challenge` and `code_challenge_method` parameters (client-side)

Cognito will:
- Store the `code_challenge` when authorization code is issued
- Validate `SHA256(code_verifier) == code_challenge` during token exchange
- Reject token exchange if verifier is missing or incorrect

### Challenge Method

AWS Cognito **only supports S256** (SHA-256 hashing). The plain challenge method is not supported for security reasons.

## Security Considerations

### Best Practices

✅ **DO**:
- Use `setupPKCE()` before every authorization request
- Clear verifier after token exchange or errors
- Use sessionStorage (not localStorage) for verifier storage
- Validate presence of verifier in callback handler
- Use S256 challenge method (only method supported by Cognito)

❌ **DON'T**:
- Reuse the same code verifier across multiple auth flows
- Store verifier in localStorage (persists across sessions)
- Skip PKCE for "quick testing" (creates security debt)
- Use Math.random() for verifier generation (not cryptographically secure)
- Send code_verifier in authorization request (only challenge goes in URL)

### OWASP Recommendations

PKCE addresses OWASP Top 10 vulnerabilities:

- **A01:2021 - Broken Access Control**: Prevents unauthorized code exchange
- **A02:2021 - Cryptographic Failures**: Uses SHA-256 for challenge generation
- **A07:2021 - Identification and Authentication Failures**: Strengthens OAuth flow

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| Authorization code interception | Attacker cannot exchange code without verifier |
| Redirect URI manipulation | Cognito validates redirect_uri matches registered URLs |
| Code replay attack | Cognito invalidates code after first use |
| CSRF attack | Verifier bound to user's session (sessionStorage) |
| Man-in-the-middle | HTTPS required for OAuth endpoints |

## Compliance

### RFC 7636 Compliance

Our implementation follows RFC 7636 (Proof Key for Code Exchange):
- Code verifier: 128 characters (high entropy, recommended length)
- Character set: [A-Z] / [a-z] / [0-9] / "-" / "." / "_" / "~" (base64url)
- Challenge method: S256 (SHA-256)
- Encoding: Base64url (RFC 4648 Section 5)

### AWS Cognito Requirements

Meets AWS Cognito PKCE requirements:
- Uses S256 challenge method (plain not supported)
- Includes `code_challenge_method=S256` in authorization request
- Provides `code_verifier` in token exchange POST body
- Uses application/x-www-form-urlencoded content type for token endpoint

## Troubleshooting

### "PKCE verification failed"

**Cause**: Code verifier doesn't match the stored challenge.

**Solutions**:
- Verify `setupPKCE()` is called before redirecting to Cognito
- Check that verifier isn't cleared before token exchange
- Ensure browser doesn't block sessionStorage
- Verify same browser tab is used for auth flow (verifier is tab-isolated)

### "Missing code_challenge"

**Cause**: Authorization request doesn't include PKCE parameters.

**Solutions**:
- Verify `setupPKCE()` is awaited (it's async)
- Check that `code_challenge` is included in authorization URL
- Ensure `code_challenge_method=S256` is set

### Verifier not found in callback

**Cause**: SessionStorage was cleared or callback opened in new tab.

**Solutions**:
- Ensure Cognito callback redirects to same tab (not popup or new window)
- Check browser settings allow sessionStorage
- Verify callback URL matches registered URL exactly (no trailing slash mismatches)

### Token exchange timeout

**Cause**: Authorization code expires (10 minutes) or network issues.

**Solutions**:
- Exchange code immediately in callback handler
- Add retry logic with exponential backoff
- Check network connectivity to Cognito

## References

### Standards
- [RFC 7636: Proof Key for Code Exchange](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 6749: OAuth 2.0 Authorization Framework](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 4648: Base64 Encoding (Section 5: base64url)](https://datatracker.ietf.org/doc/html/rfc4648#section-5)

### AWS Documentation
- [AWS Cognito: Using PKCE in authorization code grants](https://docs.aws.amazon.com/cognito/latest/developerguide/using-pkce-in-authorization-code.html)
- [AWS Cognito: Authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html)
- [AWS Cognito: Token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html)

### Security Resources
- [OWASP: OAuth 2.0 Security Best Practices](https://oauth.net/2/oauth-best-practice/)
- [OAuth 2.0 for Browser-Based Apps (BCP)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-browser-based-apps)

## Next Steps

1. **When implementing real OAuth flow**:
   - Import PKCE utilities from `frontend/src/utils/pkce.js`
   - Follow integration steps in `frontend/src/auth.jsx` comments
   - Test end-to-end flow with Google OAuth

2. **Before production deployment**:
   - [ ] Verify PKCE is working with manual tests
   - [ ] Run security tests (attempt code exchange without verifier)
   - [ ] Confirm challenge method is S256 in network logs
   - [ ] Validate verifier cleanup in all code paths

3. **Monitoring**:
   - Log PKCE failures (potential attack attempts)
   - Monitor token exchange error rates
   - Alert on missing verifier in callback (possible CSRF)

---

**Last Updated**: 2026-04-04
**Issue**: #52 - No PKCE Configuration for OAuth Flow
**Status**: ✅ PKCE utilities implemented and documented
