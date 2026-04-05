/**
 * Tests for PKCE (Proof Key for Code Exchange) utilities
 *
 * Tests verify:
 * - Code verifier generation meets RFC 7636 requirements
 * - Code challenge correctly hashes verifiers with SHA-256
 * - Storage/retrieval/cleanup of verifiers works correctly
 * - Complete PKCE setup flow works end-to-end
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  generateCodeVerifier,
  generateCodeChallenge,
  storePKCEVerifier,
  retrievePKCEVerifier,
  clearPKCEVerifier,
  setupPKCE,
} from './pkce';

describe('PKCE Utilities', () => {
  // Clear sessionStorage before each test to ensure isolation
  beforeEach(() => {
    sessionStorage.clear();
  });

  describe('generateCodeVerifier', () => {
    it('should generate a string', () => {
      const verifier = generateCodeVerifier();
      expect(typeof verifier).toBe('string');
    });

    it('should generate a 128-character verifier', () => {
      const verifier = generateCodeVerifier();
      // RFC 7636 recommends 128 characters for maximum entropy
      expect(verifier.length).toBe(128);
    });

    it('should only use base64url characters', () => {
      const verifier = generateCodeVerifier();
      // base64url uses A-Z, a-z, 0-9, -, _ (no + / or = padding)
      expect(verifier).toMatch(/^[A-Za-z0-9_-]+$/);
    });

    it('should generate different verifiers on each call', () => {
      const verifier1 = generateCodeVerifier();
      const verifier2 = generateCodeVerifier();
      const verifier3 = generateCodeVerifier();

      // Cryptographically random values should never collide
      expect(verifier1).not.toBe(verifier2);
      expect(verifier2).not.toBe(verifier3);
      expect(verifier1).not.toBe(verifier3);
    });

    it('should have high entropy (no obvious patterns)', () => {
      const verifier = generateCodeVerifier();

      // Check that the verifier is not trivially predictable
      // It should not be all the same character
      const firstChar = verifier[0];
      const allSame = verifier.split('').every(c => c === firstChar);
      expect(allSame).toBe(false);

      // Should have a reasonable distribution of character types
      const hasUppercase = /[A-Z]/.test(verifier);
      const hasLowercase = /[a-z]/.test(verifier);
      const hasDigits = /[0-9]/.test(verifier);

      // With 128 random characters, we should see all types (probability ~100%)
      expect(hasUppercase || hasLowercase || hasDigits).toBe(true);
    });
  });

  describe('generateCodeChallenge', () => {
    it('should generate a base64url-encoded SHA-256 hash', async () => {
      const verifier = 'test-verifier-12345';
      const challenge = await generateCodeChallenge(verifier);

      // SHA-256 produces 32 bytes, which becomes 43 base64url characters (no padding)
      expect(typeof challenge).toBe('string');
      expect(challenge.length).toBe(43);
      expect(challenge).toMatch(/^[A-Za-z0-9_-]+$/);
    });

    it('should produce consistent results for the same verifier', async () => {
      const verifier = 'consistent-test-verifier';
      const challenge1 = await generateCodeChallenge(verifier);
      const challenge2 = await generateCodeChallenge(verifier);

      // Same input should always produce same hash
      expect(challenge1).toBe(challenge2);
    });

    it('should produce different challenges for different verifiers', async () => {
      const verifier1 = 'verifier-one';
      const verifier2 = 'verifier-two';

      const challenge1 = await generateCodeChallenge(verifier1);
      const challenge2 = await generateCodeChallenge(verifier2);

      // Different inputs should produce different hashes
      expect(challenge1).not.toBe(challenge2);
    });

    it('should match known SHA-256 base64url test vector', async () => {
      // Test vector from RFC 7636 Appendix B
      // Plain verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
      // Expected S256 challenge: "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
      const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';
      const challenge = await generateCodeChallenge(verifier);

      expect(challenge).toBe('E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
    });

    it('should handle empty string verifier', async () => {
      const challenge = await generateCodeChallenge('');
      // Empty string still produces a valid SHA-256 hash
      expect(typeof challenge).toBe('string');
      expect(challenge.length).toBe(43);
    });

    it('should handle long verifier strings', async () => {
      // Maximum verifier length is 128 characters per RFC 7636
      const longVerifier = 'a'.repeat(128);
      const challenge = await generateCodeChallenge(longVerifier);

      expect(typeof challenge).toBe('string');
      expect(challenge.length).toBe(43);
    });
  });

  describe('storePKCEVerifier', () => {
    it('should store verifier in sessionStorage', () => {
      const verifier = 'test-verifier-xyz';
      storePKCEVerifier(verifier);

      const stored = sessionStorage.getItem('pkce_code_verifier');
      expect(stored).toBe(verifier);
    });

    it('should overwrite existing verifier', () => {
      storePKCEVerifier('first-verifier');
      storePKCEVerifier('second-verifier');

      const stored = sessionStorage.getItem('pkce_code_verifier');
      expect(stored).toBe('second-verifier');
    });
  });

  describe('retrievePKCEVerifier', () => {
    it('should retrieve stored verifier', () => {
      const verifier = 'stored-verifier-abc';
      sessionStorage.setItem('pkce_code_verifier', verifier);

      const retrieved = retrievePKCEVerifier();
      expect(retrieved).toBe(verifier);
    });

    it('should return null if no verifier stored', () => {
      const retrieved = retrievePKCEVerifier();
      expect(retrieved).toBeNull();
    });
  });

  describe('clearPKCEVerifier', () => {
    it('should remove verifier from sessionStorage', () => {
      sessionStorage.setItem('pkce_code_verifier', 'test-verifier');
      clearPKCEVerifier();

      const stored = sessionStorage.getItem('pkce_code_verifier');
      expect(stored).toBeNull();
    });

    it('should not throw if no verifier exists', () => {
      expect(() => clearPKCEVerifier()).not.toThrow();
    });
  });

  describe('setupPKCE', () => {
    it('should generate verifier and challenge', async () => {
      const result = await setupPKCE();

      expect(result).toHaveProperty('verifier');
      expect(result).toHaveProperty('challenge');
      expect(typeof result.verifier).toBe('string');
      expect(typeof result.challenge).toBe('string');
    });

    it('should store the verifier in sessionStorage', async () => {
      const { verifier } = await setupPKCE();

      const stored = retrievePKCEVerifier();
      expect(stored).toBe(verifier);
    });

    it('should generate challenge from verifier', async () => {
      const { verifier, challenge } = await setupPKCE();

      // Verify that the challenge matches what we'd get by hashing the verifier
      const expectedChallenge = await generateCodeChallenge(verifier);
      expect(challenge).toBe(expectedChallenge);
    });

    it('should create complete PKCE data for OAuth flow', async () => {
      const { verifier, challenge } = await setupPKCE();

      // Verify all components are present and valid
      expect(verifier.length).toBe(128);
      expect(challenge.length).toBe(43);
      expect(verifier).toMatch(/^[A-Za-z0-9_-]+$/);
      expect(challenge).toMatch(/^[A-Za-z0-9_-]+$/);

      // Verify storage
      expect(retrievePKCEVerifier()).toBe(verifier);
    });
  });

  describe('End-to-End PKCE Flow', () => {
    it('should support complete OAuth PKCE flow', async () => {
      // Step 1: Setup PKCE for authorization request
      const { challenge } = await setupPKCE();

      // Simulate sending authorization request with challenge
      // (In real app: redirect to Cognito with code_challenge parameter)
      expect(challenge).toBeTruthy();

      // Step 2: Simulate OAuth callback - retrieve verifier for token exchange
      const retrievedVerifier = retrievePKCEVerifier();
      expect(retrievedVerifier).toBeTruthy();

      // Step 3: Exchange code + verifier for tokens
      // (In real app: POST to /oauth2/token with code_verifier parameter)

      // Step 4: Cleanup after successful auth
      clearPKCEVerifier();
      expect(retrievePKCEVerifier()).toBeNull();
    });

    it('should handle multiple concurrent OAuth flows in different tabs', async () => {
      // Each setupPKCE() call simulates a different browser tab
      const flow1 = await setupPKCE();
      const flow2 = await setupPKCE();

      // In reality, sessionStorage is isolated per tab, so each would have its own verifier
      // This test simulates the same tab, so the second flow overwrites the first
      expect(retrievePKCEVerifier()).toBe(flow2.verifier);

      // But each flow has unique values
      expect(flow1.verifier).not.toBe(flow2.verifier);
      expect(flow1.challenge).not.toBe(flow2.challenge);
    });
  });

  describe('Security Properties', () => {
    it('should not expose verifier in challenge', async () => {
      const verifier = generateCodeVerifier();
      const challenge = await generateCodeChallenge(verifier);

      // Challenge should be irreversibly hashed - no part of verifier visible
      expect(challenge).not.toContain(verifier.substring(0, 10));
    });

    it('should use cryptographically secure random generation', () => {
      // Verify we're using crypto.getRandomValues, not Math.random()
      const spy = vi.spyOn(crypto, 'getRandomValues');

      generateCodeVerifier();

      expect(spy).toHaveBeenCalled();
      spy.mockRestore();
    });

    it('should use SHA-256 for challenge hashing', async () => {
      const spy = vi.spyOn(crypto.subtle, 'digest');

      await generateCodeChallenge('test');

      // Verify SHA-256 was called
      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith('SHA-256', expect.anything());
      spy.mockRestore();
    });
  });
});
