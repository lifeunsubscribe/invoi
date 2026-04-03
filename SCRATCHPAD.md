# Development Scratchpad

## Encountered Issues (Needs Triage)

- **2026-04-03** | `sst.config.ts:N/A` | missing-dependency | Cognito User Pool not configured - issue #5 is listed as dependency but is still OPEN | Affects: Authentication flow cannot be implemented without Cognito configuration | Fix: Complete issue #5 first - configure Cognito User Pool with Google OAuth in sst.config.ts, deploy to AWS, output userPoolId and userPoolClientId | Done: sst.config.ts contains Cognito construct, SST outputs include auth configuration, Cognito hosted UI is accessible

