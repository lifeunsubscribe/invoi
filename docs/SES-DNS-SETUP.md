# SES DNS Configuration Guide

## Overview

After deploying the infrastructure with `sst deploy`, AWS SES will generate DNS records that need to be added to the goinvoi.com domain registrar to complete email verification.

## Required DNS Records

### 1. Domain Verification (TXT Record)

SES will provide a verification token that must be added as a TXT record to prove domain ownership.

**How to get the token:**
```bash
aws ses get-identity-verification-attributes --identities goinvoi.com
```

**DNS Record Format:**
- Type: `TXT`
- Name: `_amazonses.goinvoi.com`
- Value: `<verification-token-from-aws>`
- TTL: `1800` (or your registrar's default)

### 2. DKIM Records (CNAME Records)

DKIM (DomainKeys Identified Mail) provides email authentication. SES generates 3 DKIM tokens.

**How to get DKIM tokens:**
```bash
# From SST outputs
sst output sesDkimTokens

# Or directly from AWS
aws ses get-identity-dkim-attributes --identities goinvoi.com
```

**DNS Record Format (3 records required):**

For each DKIM token, create a CNAME record:

- Type: `CNAME`
- Name: `<token>._domainkey.goinvoi.com`
- Value: `<token>.dkim.amazonses.com`
- TTL: `1800`

Example (tokens are placeholders):
```
abc123._domainkey.goinvoi.com  →  abc123.dkim.amazonses.com
def456._domainkey.goinvoi.com  →  def456.dkim.amazonses.com
ghi789._domainkey.goinvoi.com  →  ghi789.dkim.amazonses.com
```

### 3. SPF Record (TXT Record) - Optional but Recommended

SPF (Sender Policy Framework) specifies which servers can send email for your domain.

**DNS Record Format:**
- Type: `TXT`
- Name: `goinvoi.com`
- Value: `v=spf1 include:amazonses.com ~all`
- TTL: `1800`

**Note:** If an SPF record already exists, append `include:amazonses.com` to it instead of creating a new one.

## Verification Steps

### 1. Add DNS Records

Add all records above to your domain registrar (e.g., Namecheap, GoDaddy, Route53, Cloudflare).

### 2. Wait for DNS Propagation

DNS changes can take up to 48 hours to propagate, but usually complete within 1-2 hours.

Check propagation status:
```bash
# Check TXT record
dig TXT _amazonses.goinvoi.com

# Check DKIM CNAME records
dig CNAME <token>._domainkey.goinvoi.com
```

### 3. Verify Domain Status in AWS

Check if SES has verified the domain:

```bash
aws ses get-identity-verification-attributes --identities goinvoi.com
```

Expected output when verified:
```json
{
    "VerificationAttributes": {
        "goinvoi.com": {
            "VerificationStatus": "Success"
        }
    }
}
```

### 4. Test Email Sending

Once verified, test sending an email:

**Option 1: Via test endpoint**
```bash
curl "$(sst output ApiEndpoint)/api/test-ses?to=your-email@example.com"
```

**Option 2: Via AWS CLI**
```bash
aws ses send-email \
  --from noreply@goinvoi.com \
  --to your-email@example.com \
  --subject "Test Email from Invoi" \
  --text "This is a test email to verify SES configuration."
```

## SES Sandbox Mode

By default, SES starts in **sandbox mode**, which has the following restrictions:

- Can only send to **verified email addresses**
- Limited to **200 emails per day**
- Maximum send rate of **1 email per second**

### Verifying Test Email Addresses (Sandbox Only)

To test email sending while in sandbox mode, verify recipient addresses:

```bash
aws ses verify-email-identity --email-address test@example.com
```

The recipient will receive a verification email with a link to click.

### Moving Out of Sandbox (Production)

To send to any email address without verification:

1. Open the AWS SES console
2. Navigate to "Account dashboard"
3. Click "Request production access"
4. Fill out the request form:
   - Use case: Transactional emails (invoices)
   - Website URL: https://goinvoi.com
   - Expected sending volume: Start with 100-500/month
   - Describe how you handle bounces/complaints
5. Submit and wait for approval (usually 24-48 hours)

**Note:** For beta testing with a small number of users, sandbox mode is sufficient if you verify each beta tester's email address.

## Troubleshooting

### Domain Not Verifying

- **DNS not propagated:** Wait longer (up to 48 hours) or check with `dig` command
- **Wrong TXT record:** Ensure the verification token is exact (no extra quotes or spaces)
- **Wrong DNS name:** TXT record should be `_amazonses.goinvoi.com`, not just `goinvoi.com`

### DKIM Not Verifying

- **Missing CNAME records:** All 3 DKIM tokens must have CNAME records
- **Wrong CNAME target:** Each record should point to `<token>.dkim.amazonses.com`
- **Trailing dot issue:** Some registrars auto-append `.` to hostnames; check your registrar's documentation

### Email Send Fails with "Email address not verified"

- **Sandbox mode:** You're in sandbox mode and the recipient isn't verified. Either verify the recipient or request production access.

### Email Send Fails with "Access Denied"

- **IAM permissions:** The Lambda execution role needs `ses:SendEmail` and `ses:SendRawEmail` permissions. SST should configure this automatically, but verify in IAM console if needed.

## References

- [AWS SES Domain Verification](https://docs.aws.amazon.com/ses/latest/dg/verify-domain-procedure.html)
- [AWS SES DKIM](https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dkim.html)
- [AWS SES Sandbox](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html)
- [SPF Records](https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-spf.html)
