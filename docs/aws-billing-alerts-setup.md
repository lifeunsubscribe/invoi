# AWS Billing Alerts Setup Guide

**Date Created:** 2026-04-03
**Project:** Invoi (Serverless Invoicing App)
**Target Cost:** $0-2/month (within AWS Free Tier)
**Alert Thresholds:** $5 and $10

---

## Overview

This guide walks through setting up AWS Budgets with email alerts to prevent unexpected charges during development and production. Critical for maintaining cost visibility on a serverless project.

---

## Prerequisites

- AWS account with appropriate permissions (Billing Console access)
- Access to the email address where alerts will be sent
- **Note:** You must be signed in as the root user OR have IAM permissions for:
  - `budgets:CreateBudget`
  - `budgets:ViewBudget`
  - `sns:CreateTopic` (for email notifications)
  - `sns:Subscribe`

---

## Step-by-Step Configuration

### 1. Access AWS Budgets Service

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/)
2. Navigate to **Billing and Cost Management**
   - Option A: Use the search bar at the top and type "Budgets"
   - Option B: Click your account name (top right) → **Billing and Cost Management** → **Budgets** (left sidebar)
3. Click **Create budget**

---

### 2. Create First Budget ($5 Threshold)

#### Budget Setup Type
- Select **Customize (advanced)**
- Click **Next**

#### Budget Type
- Select **Cost budget**
- Click **Next**

#### Set Budget Details
- **Budget name:** `Invoi-Alert-5-Dollars`
- **Period:** Monthly
- **Budget renewal type:** Recurring budget
- **Start month:** Current month (e.g., April 2026)
- **Budget effective dates:** Choose current date
- **Budgeting method:** Fixed
- **Enter your budgeted amount:** `5.00` USD
- Click **Next**

#### Configure Alert (Threshold #1)
- **Alert threshold:**
  - Select **Actual** (triggers when actual spend reaches threshold)
  - Set to `100%` of budgeted amount ($5.00)
- **Email recipients:** Enter your email address(es)
  - You can add multiple emails separated by commas
  - Example: `you@example.com, team@example.com`
- Click **Add an alert threshold** to add a forecasted alert (optional but recommended):
  - Select **Forecasted**
  - Set to `100%` of budgeted amount
  - Use the same email recipients
- Click **Next**

#### Attach Actions (Optional)
- Skip this section for now (actions like auto-shutdown can be added later)
- Click **Next**

#### Review
- Review all settings
- Click **Create budget**

---

### 3. Create Second Budget ($10 Threshold)

Repeat the process above with these changes:

- **Budget name:** `Invoi-Alert-10-Dollars`
- **Enter your budgeted amount:** `10.00` USD
- **Alert threshold:** Same configuration (100% actual + 100% forecasted)
- **Email recipients:** Same email address(es)

---

### 4. Verify Email Subscription

After creating the budgets:

1. Check your email inbox for messages from **AWS Notifications** (`no-reply@sns.amazonaws.com`)
2. You should receive **2 confirmation emails** (one per budget)
3. **Click "Confirm subscription"** in each email
   - This activates the SNS topic for alerts
   - If you don't confirm, you won't receive alerts!
4. You should see a confirmation page: "Subscription confirmed!"

---

## Verification

### Using AWS Console

1. Go to **Billing and Cost Management** → **Budgets**
2. You should see both budgets listed:
   - `Invoi-Alert-5-Dollars` with $5.00 threshold
   - `Invoi-Alert-10-Dollars` with $10.00 threshold
3. Click on each budget to verify:
   - Alert thresholds are configured (100% actual, 100% forecasted)
   - Email recipients are correct
   - Status shows as "Active"

### Using AWS CLI

Run this command to list all configured budgets:

```bash
aws budgets describe-budgets --account-id $(aws sts get-caller-identity --query Account --output text)
```

Expected output should include both budgets with their configurations.

If you get an error about AWS credentials, ensure the AWS CLI is configured:

```bash
aws configure
```

---

## Testing the Alerts

### Option 1: Wait for Natural Trigger
- AWS will automatically send an alert when your actual or forecasted spend crosses a threshold
- This is the recommended approach for production

### Option 2: Modify Thresholds for Immediate Test (Optional)
To verify email delivery works:

1. Check your current month-to-date spend in the **Billing Dashboard**
2. Temporarily lower one budget threshold to below your current spend
   - Example: If you've spent $0.50, set threshold to $0.25
3. Wait 5-10 minutes for AWS to detect the breach
4. You should receive an alert email
5. **Important:** Reset the threshold back to $5 or $10 after testing

---

## What the Alert Emails Look Like

You'll receive emails with subject lines like:

- `AWS Budgets: Invoi-Alert-5-Dollars has exceeded your alert threshold`

The email body will include:
- Your account ID
- Budget name
- Threshold that was crossed (actual or forecasted)
- Current spend amount
- Link to view details in AWS Console

---

## Monitoring Current Spend

To check your current AWS spend:

1. Go to **Billing and Cost Management** → **Bills**
2. View **Month-to-Date Spend** at the top
3. Expand **Charges by service** to see breakdown:
   - S3 storage and requests
   - DynamoDB read/write capacity
   - Lambda invocations and compute time
   - API Gateway requests
   - CloudFront data transfer
   - SES email sends

---

## Expected Costs for Invoi

Based on the serverless architecture in `sst.config.ts`:

| Service | Free Tier | Expected Usage (dev) | Expected Cost |
|---------|-----------|---------------------|---------------|
| **S3** | 5GB storage, 20k GET, 2k PUT | < 1GB, < 1k requests/mo | $0.00 |
| **DynamoDB** | 25GB storage, 200M requests/mo | < 100MB, < 10k requests/mo | $0.00 |
| **Lambda** | 1M requests, 400k GB-seconds/mo | < 100 requests/mo (dev) | $0.00 |
| **API Gateway** | 1M requests (HTTP API) | < 100 requests/mo (dev) | $0.00 |
| **CloudFront** | 1TB data transfer, 10M requests | Minimal during dev | $0.00 |
| **SES** | 62k emails/mo (if sending from EC2/Lambda) | < 10 emails/mo (dev) | $0.00 |

**Total Expected (Development):** $0.00/month (within Free Tier)

**Total Expected (Production, 10-100 users):** $0-2/month

The $5 and $10 alerts provide a safety buffer if something unexpected happens (e.g., accidental DDoS, runaway Lambda, data transfer spike).

---

## Troubleshooting

### Issue: Didn't receive confirmation email
- **Check spam/junk folder** - AWS emails sometimes get filtered
- **Verify email address** - Check for typos in the budget configuration
- **Resend confirmation:** Delete and recreate the budget, or modify the budget to re-trigger SNS subscription

### Issue: Confirmed subscription but no alerts
- **Check alert threshold configuration** - Ensure both actual and forecasted are set
- **Verify current spend** - Alerts only trigger when threshold is crossed
- **Check SNS topic status** - Go to **SNS** → **Subscriptions** → verify status is "Confirmed"

### Issue: AWS CLI verification fails
- **Credentials not configured:** Run `aws configure` and enter your Access Key ID and Secret Access Key
- **Insufficient permissions:** Ensure your IAM user has `budgets:ViewBudget` permission
- **Wrong account ID:** Ensure you're querying the correct AWS account

### Issue: Budget shows as "No data available"
- **Wait 24 hours** - AWS Budgets may take up to 24 hours to populate initial data
- **Verify billing data is enabled** - Go to **Billing and Cost Management** → **Billing preferences** → Enable **Receive Billing Alerts**

---

## Maintenance

### Monthly Review
- Review budget alerts and actual spend trends
- Adjust thresholds if usage patterns change
- Archive old alerts for audit trail

### When to Update Budgets
- Moving from development to production (expect higher traffic)
- Adding new AWS services (e.g., RDS, ElastiCache)
- Significant increase in user base
- New features that may impact costs (e.g., AI transcription in Pro tier)

### Deleting Budgets (if needed)
1. Go to **Budgets** → Select the budget
2. Click **Actions** → **Delete**
3. Confirm deletion
4. **Note:** This does NOT delete historical billing data, only the alert configuration

---

## Security Best Practices

- **Use IAM users** instead of root account for day-to-day access
- **Limit billing console access** to only trusted team members
- **Enable MFA** on root account and IAM users with billing permissions
- **Review CloudTrail logs** for budget creation/modification events
- **Set up AWS Cost Anomaly Detection** (free) as an additional layer of monitoring

---

## Next Steps After Setup

1. ✅ Confirm both email subscriptions
2. ✅ Verify budgets appear in AWS Console
3. ✅ Bookmark Billing Dashboard for quick access
4. ✅ Enable **Cost Explorer** in Billing preferences (free, useful for visualizing trends)
5. ✅ Set calendar reminder to review costs monthly
6. Consider setting up **AWS Cost Anomaly Detection** for ML-based alerts (complements Budgets)

---

## References

- [AWS Budgets Documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [AWS Free Tier](https://aws.amazon.com/free/)
- [AWS Billing and Cost Management](https://docs.aws.amazon.com/account-billing/index.html)
- [Invoi Architecture (ADR-webapp-migration.md)](./ADR-webapp-migration.md)

---

## Completion Checklist

- [ ] $5 budget created with actual + forecasted alerts
- [ ] $10 budget created with actual + forecasted alerts
- [ ] Both email subscriptions confirmed
- [ ] Budgets verified in AWS Console
- [ ] AWS CLI verification passed (optional, if credentials configured)
- [ ] Test alert received (optional)
- [ ] Team notified of alert email addresses
- [ ] Calendar reminder set for monthly cost review

---

**Setup Complete!** Your AWS billing alerts are now active and will notify you if costs exceed $5 or $10/month.
