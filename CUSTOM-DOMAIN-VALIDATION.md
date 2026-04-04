# Custom Domain Configuration Validation

## Configuration Summary

This document validates the custom domain configuration for `goinvoi.com`.

## ✅ Configuration Checklist

### 1. API Gateway Custom Domain
- **Location:** sst.config.ts:100-103
- **Domain:** api.goinvoi.com
- **Stage Gating:** Only enabled for production stage
- **DNS Management:** Route53 (sst.aws.dns())
- **ACM Certificate:** Auto-created and validated

### 2. CloudFront/StaticSite Custom Domain
- **Location:** sst.config.ts:288-292
- **Primary Domain:** goinvoi.com
- **Aliases:** www.goinvoi.com (redirects to apex)
- **Stage Gating:** Only enabled for production stage
- **DNS Management:** Route53 (sst.aws.dns())
- **ACM Certificate:** Auto-created in us-east-1 (required for CloudFront)

### 3. CORS Configuration
- **Location:** sst.config.ts:106-108
- **Production Origins:** 
  - https://goinvoi.com
  - https://www.goinvoi.com
- **Dev Origins:** * (wildcard)
- **Methods:** GET, POST, PUT, DELETE, OPTIONS
- **Headers:** Content-Type, Authorization

### 4. Cognito Callback URLs
- **Location:** sst.config.ts:62-66
- **Production Callback:** https://goinvoi.com/auth/callback
- **Production Logout:** https://goinvoi.com/auth/logout
- **Dev Callback:** http://localhost:5173/auth/callback
- **Dev Logout:** http://localhost:5173/auth/logout

### 5. SST Outputs
- **Location:** sst.config.ts:313-314
- **Custom Domain:** goinvoi.com (production only)
- **API Domain:** api.goinvoi.com (production only)

## 📋 Acceptance Criteria Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| ACM certificate requested for goinvoi.com and www.goinvoi.com | ✅ | Auto-requested on production deploy |
| Certificate validated via DNS | ⏳ | Will auto-validate after DNS setup |
| CloudFront distribution configured with custom domain | ✅ | StaticSite configured with domain |
| DNS records point goinvoi.com to CloudFront | ⏳ | Requires manual DNS setup at registrar |
| HTTPS works at https://goinvoi.com | ⏳ | Will work after DNS propagation |
| HTTP redirects to HTTPS | ✅ | CloudFront handles automatically |
| api.goinvoi.com configured for API Gateway | ✅ | API Gateway custom domain configured |

## 🔧 Next Steps (Manual)

After merging this configuration:

1. **Deploy to production:**
   ```bash
   sst deploy --stage production
   ```

2. **Get Route53 nameservers:**
   ```bash
   aws route53 list-hosted-zones | grep -A 5 "goinvoi.com"
   aws route53 get-hosted-zone --id <HOSTED_ZONE_ID>
   ```

3. **Update domain registrar:**
   - Point goinvoi.com nameservers to Route53 nameservers
   - Wait for DNS propagation (1-48 hours)

4. **Verify setup:**
   ```bash
   # Should return 200 with CloudFront headers
   curl -I https://goinvoi.com
   
   # Should return 301 redirect to HTTPS
   curl -I http://goinvoi.com
   
   # Should resolve to API Gateway
   dig api.goinvoi.com
   ```

5. **Update Google OAuth:**
   - Add https://goinvoi.com/auth/callback to authorized redirect URIs
   - Add https://goinvoi.com/auth/logout to authorized logout URIs

## 🏗️ Architecture

```
goinvoi.com (CloudFront + S3)
├── ACM Certificate (auto-created in us-east-1)
├── DNS (Route53)
└── Aliases: www.goinvoi.com

api.goinvoi.com (API Gateway)
├── ACM Certificate (auto-created in deployment region)
└── DNS (Route53)
```

## 🔐 Security Features

- ✅ HTTPS enforced (HTTP → HTTPS redirect)
- ✅ ACM managed certificates (auto-renewal)
- ✅ CORS restricted to custom domain in production
- ✅ TLS 1.2+ enforced by CloudFront
- ✅ Stage-gated configuration (dev uses localhost)

## 📝 Documentation

- **DNS Setup Guide:** DNS-SETUP.md
- **SST Config:** sst.config.ts
- **Architecture Decision:** docs/ADR-webapp-migration.md

## 🚨 Important Notes

1. **Stage Gating:** Custom domain only applies to production stage. Dev stage continues to use auto-generated URLs.
2. **DNS Propagation:** Can take up to 48 hours but usually completes in 1-2 hours.
3. **Certificate Validation:** Happens automatically once DNS points to Route53.
4. **No Breaking Changes:** Dev workflow is unaffected; custom domain only used in production.
5. **Cost:** ~$0.50/month for Route53 hosted zone. ACM certificates are free.

## ✅ Validation Complete

All configuration changes are in place. The infrastructure is ready for production deployment.
