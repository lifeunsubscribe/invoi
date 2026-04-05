# Phase 1 Verification: Cognito with Google OAuth

## Prerequisites

1. **Create Google OAuth Application**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Navigate to "APIs & Services" > "Credentials"
   - Create OAuth 2.0 Client ID (Application type: Web application)
   - Note down the Client ID and Client Secret

2. **Set SST Secrets** (before deploying):
   ```bash
   sst secret set GoogleClientId <your-google-client-id> --stage dev
   sst secret set GoogleClientSecret <your-google-client-secret> --stage dev
   ```

## Deployment

```bash
sst deploy --stage dev
```

Expected outputs:
- `api`: API Gateway URL
- `site`: CloudFront distribution URL
- `userPool`: Cognito User Pool ID
- `userPoolClient`: User Pool Client ID
- `hostedUI`: Cognito Hosted UI URL (e.g., `https://invoi-dev.auth.us-east-1.amazoncognito.com`)

## Configure Google OAuth Callback URLs

After deployment, update your Google OAuth application with the callback URLs:

**For development (localhost)**:
- Authorized redirect URIs: `http://localhost:5173/auth/callback`
- Authorized JavaScript origins: `http://localhost:5173`

**For deployed stage**:
- Authorized redirect URIs: `<site-url>/auth/callback`
- Authorized JavaScript origins: `<site-url>`

## Testing

### 1. Test Hosted UI Access

Visit the hosted UI URL with the login flow:
```
<hostedUI>/login?client_id=<userPoolClient>&response_type=code&scope=email+openid+profile&redirect_uri=<callback-url>
```

Example:
```
https://invoi-dev.auth.us-east-1.amazoncognito.com/login?client_id=abc123&response_type=code&scope=email+openid+profile&redirect_uri=http://localhost:5173/auth/callback
```

### 2. Verify Google Sign-In

1. Click "Sign in with Google" on the hosted UI
2. Authenticate with your Google account
3. Grant permissions to the app
4. You should be redirected to the callback URL with an authorization code

Expected callback URL format:
```
http://localhost:5173/auth/callback?code=<authorization-code>
```

### 3. Exchange Code for Tokens (Manual Test)

Use the authorization code to get JWT tokens:

```bash
curl -X POST https://invoi-dev.auth.us-east-1.amazoncognito.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "client_id=<userPoolClient>" \
  -d "code=<authorization-code>" \
  -d "redirect_uri=http://localhost:5173/auth/callback"
```

Expected response:
```json
{
  "id_token": "eyJraWQ...",
  "access_token": "eyJraWQ...",
  "refresh_token": "eyJjdHk...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

### 4. Verify JWT Token Contents

Decode the `id_token` at [jwt.io](https://jwt.io):

Expected claims:
- `sub`: User's unique identifier (from Google)
- `email`: User's email address
- `name`: User's full name
- `picture`: User's profile picture URL
- `cognito:username`: Cognito username
- `iss`: Issuer (Cognito User Pool URL)
- `aud`: Audience (User Pool Client ID)
- `exp`: Expiration timestamp
- `iat`: Issued at timestamp

## Acceptance Criteria Checklist

- [ ] Cognito User Pool created with Google OAuth provider
- [ ] Hosted UI endpoint accessible
- [ ] Google OAuth client ID/secret configured via SST secrets
- [ ] Test sign-in returns JWT tokens with correct claims

## Troubleshooting

### Error: "redirect_uri_mismatch"
- Verify the callback URL in your Google OAuth app matches exactly (including protocol and trailing slashes)

### Error: "invalid_client"
- Check that SST secrets are set correctly: `sst secret list --stage dev`

### Error: "unauthorized_client"
- Ensure the OAuth flow and scopes are configured correctly in the User Pool Client

### No Google button on Hosted UI
- Check that the Google identity provider is properly configured
- Verify the User Pool Client has "Google" in its providers list

## Cleanup

To remove all resources:
```bash
sst remove --stage dev
```

To remove secrets:
```bash
sst secret remove GoogleClientId --stage dev
sst secret remove GoogleClientSecret --stage dev
```
