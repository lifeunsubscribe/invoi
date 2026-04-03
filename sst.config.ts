/// <reference path="./.sst/platform/config.d.ts" />

export default $config({
  app(input) {
    return {
      name: "invoi",
      removal: input?.stage === "production" ? "retain" : "remove",
      home: "aws",
    };
  },
  async run() {
    // Google OAuth credentials (set via `sst secret set GoogleClientId <value>`)
    const googleClientId = new sst.Secret("GoogleClientId");
    const googleClientSecret = new sst.Secret("GoogleClientSecret");

    // Cognito User Pool for authentication
    // Uses email as username for sign-in, creates stage-specific hosted UI domain
    const userPool = new sst.aws.CognitoUserPool("InvoiUserPool", {
      usernames: ["email"],
      domain: {
        prefix: `invoi-${$app.stage}`, // e.g., invoi-dev.auth.us-east-1.amazoncognito.com
      },
    });

    // Configure Google as OAuth provider
    // Maps Google user attributes to Cognito user pool attributes
    // Requires Google OAuth app configured with matching callback URLs
    userPool.addIdentityProvider("Google", {
      type: "google",
      details: {
        authorize_scopes: "email profile openid",
        client_id: googleClientId.value,
        client_secret: googleClientSecret.value,
      },
      attributes: {
        email: "email",      // Google email -> Cognito email
        name: "name",        // Google name -> Cognito name
        picture: "picture",  // Google profile pic -> Cognito picture
        username: "sub",     // Google user ID -> Cognito username
      },
    });

    // Static site (React frontend) - defined early to get URL for Cognito callbacks
    const site = new sst.aws.StaticSite("InvoiWeb", {
      path: "frontend",
      build: {
        command: "npm run build",
        output: "dist",
      },
      environment: {
        VITE_API_URL: "", // Will be set after API is defined below
      },
    });

    // User pool client for React app
    // Configures OAuth flow with environment-specific callback URLs
    const userPoolClient = userPool.addClient("Web", {
      providers: ["Google"],
      oauth: {
        // Use localhost for dev, deployed site URL for production
        callbackUrls: [
          $dev ? "http://localhost:5173/auth/callback" : $interpolate`${site.url}/auth/callback`
        ],
        logoutUrls: [
          $dev ? "http://localhost:5173/auth/logout" : $interpolate`${site.url}/auth/logout`
        ],
        flows: ["authorization_code"], // Standard OAuth 2.0 flow
        scopes: ["email", "openid", "profile"], // Request user's basic info
      },
    });

    // S3 bucket for PDFs and user assets
    const bucket = new sst.aws.Bucket("InvoiStorage");

    // DynamoDB tables
    const usersTable = new sst.aws.Dynamo("UsersTable", {
      fields: { userId: "string" },
      primaryIndex: { hashKey: "userId" },
    });

    const invoicesTable = new sst.aws.Dynamo("InvoicesTable", {
      fields: { userId: "string", invoiceId: "string" },
      primaryIndex: { hashKey: "userId", rangeKey: "invoiceId" },
    });

    // API Gateway + Lambda functions
    const api = new sst.aws.ApiGatewayV2("InvoiApi", {
      cors: {
        allowOrigins: ["*"],
        allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allowHeaders: ["Content-Type", "Authorization"],
      },
    });

    // TODO: REMOVE AFTER PHASE 0 - Temporary route for end-to-end verification only
    // Phase 0: Hello endpoint for end-to-end verification
    api.route("GET /hello", {
      handler: "backend/functions/hello.handler",
    });

    // TODO: Add routes pointing to Lambda functions in Phase 1+

    // Update site environment variables with API URL and Cognito config
    // These VITE_* variables are exposed to the React app at build time
    site.environment = {
      VITE_API_URL: api.url,
      VITE_COGNITO_USER_POOL_ID: userPool.id,
      VITE_COGNITO_CLIENT_ID: userPoolClient.id,
      VITE_COGNITO_DOMAIN: userPool.domainUrl, // Hosted UI domain for auth flows
    };

    return {
      api: api.url,
      site: site.url,
      userPool: userPool.id,
      userPoolClient: userPoolClient.id,
      hostedUI: userPool.domainUrl,
    };
  },
});
