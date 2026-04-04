# Phase 3: SES Configuration - Verification Steps

## Summary

This phase configures AWS SES (Simple Email Service) for sending invoice emails from the `goinvoi.com` domain.

## Changes Made

### 1. Infrastructure (sst.config.ts)
- Added `aws.ses.EmailIdentity` resource for domain verification
- Added `aws.ses.DomainDkim` resource for DKIM email authentication
- Added outputs: `sesIdentity` and `sesDkimTokens` for DNS configuration
- Added test endpoint: `GET /api/test-ses` for email verification

### 2. Email Service (backend/services/mail_service.py)
- Implemented `send_email()` function using boto3 SES client
- Supports plain text emails with PDF attachments
- Uses MIME multipart encoding
- Error handling for SES ClientErrors
- Default sender: `noreply@goinvoi.com`

### 3. Test Endpoint (backend/functions/test_ses.py)
- Lambda function for testing SES email delivery
- Usage: `GET /api/test-ses?to=recipient@example.com`
- Returns MessageId on success

### 4. Tests (backend/tests/test_mail_service.py)
- 12 unit tests covering:
  - Basic email sending
  - Email with attachments
  - Multiple recipients
  - Error handling
  - Email body templates
- All tests passing ✓

### 5. Documentation (docs/SES-DNS-SETUP.md)
- Complete DNS configuration guide
- Instructions for domain verification
- DKIM and SPF record setup
- Sandbox mode explanation
- Troubleshooting tips

## Deployment Steps

### 1. Deploy Infrastructure

```bash
sst deploy
```

This will:
- Create SES email identity for goinvoi.com
- Generate DKIM tokens
- Deploy the test endpoint

### 2. Get DNS Records

After deployment, retrieve the required DNS records:

```bash
# Get DKIM tokens
sst output sesDkimTokens

# Or use AWS CLI
aws ses get-identity-dkim-attributes --identities goinvoi.com
aws ses get-identity-verification-attributes --identities goinvoi.com
```

### 3. Configure DNS

Add the following records to your domain registrar (see `docs/SES-DNS-SETUP.md` for details):

**TXT Record (Domain Verification):**
- Name: `_amazonses.goinvoi.com`
- Value: `<verification-token-from-aws>`

**CNAME Records (DKIM - 3 records):**
- Name: `<token1>._domainkey.goinvoi.com`
- Value: `<token1>.dkim.amazonses.com`
- (Repeat for all 3 DKIM tokens)

**TXT Record (SPF - optional but recommended):**
- Name: `goinvoi.com`
- Value: `v=spf1 include:amazonses.com ~all`

### 4. Wait for DNS Propagation

DNS changes typically take 1-2 hours (up to 48 hours max).

Check propagation:
```bash
dig TXT _amazonses.goinvoi.com
dig CNAME <token>._domainkey.goinvoi.com
```

### 5. Verify Domain Status

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

### 6. Test Email Sending

**Option 1: Test endpoint**
```bash
curl "$(sst output ApiEndpoint)/api/test-ses?to=your-email@example.com"
```

**Option 2: AWS CLI**
```bash
aws ses send-email \
  --from noreply@goinvoi.com \
  --to your-email@example.com \
  --subject "Test Email from Invoi" \
  --text "This is a test email to verify SES configuration."
```

## Sandbox Mode Considerations

By default, SES starts in **sandbox mode** with these restrictions:
- Can only send to verified email addresses
- Limited to 200 emails/day
- Max 1 email/second

### For Beta Testing (Sandbox Mode)

Verify each beta tester's email:
```bash
aws ses verify-email-identity --email-address tester@example.com
```

They will receive a verification email to click.

### For Production

Request production access via AWS SES Console:
1. Navigate to SES → Account Dashboard
2. Click "Request production access"
3. Fill out form with:
   - Use case: Transactional emails (invoices)
   - Website: https://goinvoi.com
   - Volume: 100-500/month initially
4. Wait 24-48 hours for approval

## Acceptance Criteria Checklist

- [ ] Domain goinvoi.com verified in SES
- [ ] DNS records (DKIM, SPF) configured
- [ ] Test email sends successfully from noreply@goinvoi.com
- [ ] SES sandbox mode acceptable for beta (or production access requested)

## Verification Commands Summary

```bash
# Check domain verification status
aws ses get-identity-verification-attributes --identities goinvoi.com

# Check DKIM status
aws ses get-identity-dkim-attributes --identities goinvoi.com

# Check account sending status
aws ses get-account-sending-enabled

# Send test email
aws ses send-email \
  --from noreply@goinvoi.com \
  --to your-email@example.com \
  --subject "Test" \
  --text "Test email from Invoi"
```

## Troubleshooting

If emails fail to send, check:

1. **Domain verification status** - Must show "Success"
2. **DKIM records** - All 3 CNAME records must be present
3. **Sandbox mode** - Recipient must be verified if in sandbox
4. **IAM permissions** - Lambda needs `ses:SendEmail` and `ses:SendRawEmail`

See `docs/SES-DNS-SETUP.md` for detailed troubleshooting.

## Next Steps (Phase 4+)

After SES is verified and working:
- Integrate email sending into `POST /api/submit/weekly` endpoint
- Integrate email sending into `POST /api/submit/monthly` endpoint
- Add "Save & Send" functionality to frontend
- Implement invoice status tracking (draft → sent → paid)
- Add email tracking (sent to whom, when)

## Files Modified

- `sst.config.ts` - Added SES resources and test endpoint
- `backend/services/mail_service.py` - Implemented send_email()
- `backend/functions/test_ses.py` - Created test endpoint
- `backend/tests/test_mail_service.py` - Created unit tests
- `docs/SES-DNS-SETUP.md` - Created DNS configuration guide
- `PHASE-3-VERIFICATION.md` - This file

## Dependencies

This phase depends on:
- AWS account with SES access
- Domain goinvoi.com registered
- Access to domain DNS settings
- boto3 (already in Lambda Python runtime)

No new Python dependencies required.
