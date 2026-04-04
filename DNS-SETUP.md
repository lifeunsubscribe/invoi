# DNS Setup Guide for goinvoi.com

This guide explains how to configure DNS for the custom domain after deploying to production.

## Overview

The SST infrastructure is now configured to use `goinvoi.com` as the custom domain in production. The setup includes:

- **goinvoi.com** - Main site (CloudFront + S3)
- **www.goinvoi.com** - Redirects to apex domain
- **api.goinvoi.com** - API Gateway endpoint

## Prerequisites

1. Domain `goinvoi.com` must be registered
2. Access to domain registrar account (where the domain was purchased)
3. Production deployment completed: `sst deploy --stage production`

## Step 1: Deploy to Production

```bash
# Deploy the infrastructure to production stage
sst deploy --stage production
```

This will:
- Create Route53 hosted zone for `goinvoi.com`
- Request ACM certificates for both the site and API
- Set up CloudFront distribution
- Configure API Gateway custom domain
- Output the Route53 nameservers

## Step 2: Get Route53 Nameservers

After deployment, run:

```bash
# List the hosted zone
aws route53 list-hosted-zones | grep -A 5 "goinvoi.com"

# Get the nameservers for your hosted zone (replace HOSTED_ZONE_ID)
aws route53 get-hosted-zone --id HOSTED_ZONE_ID
```

You'll get 4 nameservers that look like:
- ns-1234.awsdns-12.org
- ns-5678.awsdns-34.com
- ns-9012.awsdns-56.net
- ns-3456.awsdns-78.co.uk

## Step 3: Update Domain Registrar

Go to your domain registrar (GoDaddy, Namecheap, Google Domains, etc.) and:

1. Navigate to DNS settings for `goinvoi.com`
2. Change the nameservers to the 4 Route53 nameservers from Step 2
3. Save the changes

**Note:** DNS propagation can take up to 48 hours, but usually completes within 1-2 hours.

## Step 4: Verify DNS Configuration

After DNS has propagated, verify the setup:

```bash
# Check DNS resolution
dig goinvoi.com
dig www.goinvoi.com
dig api.goinvoi.com

# Check HTTPS (should return 200 with CloudFront headers)
curl -I https://goinvoi.com

# Check HTTP redirect (should redirect to HTTPS)
curl -I http://goinvoi.com
```

## Step 5: Verify ACM Certificate

Check that the SSL certificate is active:

```bash
# List certificates
aws acm list-certificates --region us-east-1

# Get certificate details (replace CERTIFICATE_ARN)
aws acm describe-certificate --certificate-arn CERTIFICATE_ARN --region us-east-1
```

The certificate should show:
- Status: `ISSUED`
- Domain: `goinvoi.com` and `www.goinvoi.com`
- Validation method: `DNS`

## Troubleshooting

### Certificate Pending Validation

If the ACM certificate is stuck in "Pending Validation":

1. Verify nameservers are correctly updated at the registrar
2. Check DNS propagation: `dig NS goinvoi.com`
3. Wait for DNS to propagate (can take up to 48 hours)
4. SST will automatically retry certificate validation

### HTTPS Not Working

1. Ensure DNS has propagated: `dig goinvoi.com`
2. Check CloudFront distribution status: should be "Deployed"
3. Check certificate status: should be "Issued"
4. Clear browser cache and try incognito mode
5. Wait for CloudFront cache to update (can take 15-20 minutes)

### API Subdomain Not Working

1. Verify `api.goinvoi.com` DNS record exists in Route53
2. Check API Gateway custom domain configuration
3. Ensure ACM certificate includes the API subdomain
4. Test the API directly: `curl https://api.goinvoi.com/hello`

## Expected Results

After DNS configuration is complete:

✅ `https://goinvoi.com` - Loads the React app with valid SSL
✅ `https://www.goinvoi.com` - Redirects to apex domain
✅ `http://goinvoi.com` - Redirects to HTTPS
✅ `https://api.goinvoi.com` - API Gateway responds to requests
✅ Certificate shows valid for goinvoi.com in browser
✅ CloudFront headers visible in response

## DNS Records Created by SST

SST automatically creates these Route53 records:

| Type | Name | Purpose |
|------|------|---------|
| A | goinvoi.com | Points to CloudFront distribution (IPv4) |
| AAAA | goinvoi.com | Points to CloudFront distribution (IPv6) |
| A | www.goinvoi.com | Alias to apex domain |
| AAAA | www.goinvoi.com | Alias to apex domain |
| A | api.goinvoi.com | Points to API Gateway |
| AAAA | api.goinvoi.com | Points to API Gateway |
| CNAME | _validation | ACM certificate validation record |

## Security Features

The configuration includes:

- **HTTPS Only** - HTTP automatically redirects to HTTPS
- **ACM Managed Certificates** - Auto-renewal, no manual cert management
- **CloudFront HTTPS** - TLS 1.2+ enforced
- **CORS Protection** - Only allows requests from goinvoi.com in production

## Cost

Custom domain configuration adds minimal cost:

- Route53 Hosted Zone: $0.50/month
- ACM Certificate: **FREE**
- CloudFront HTTPS: **FREE**
- DNS Queries: $0.40 per million queries (effectively free at this scale)

Estimated total: **$0.50/month**

## Next Steps

1. Update Google OAuth credentials with new callback URL
2. Test the full authentication flow at https://goinvoi.com
3. Update any hardcoded URLs in frontend code
4. Monitor CloudFront access logs for traffic patterns
5. Set up CloudWatch alarms for certificate expiration (optional)
