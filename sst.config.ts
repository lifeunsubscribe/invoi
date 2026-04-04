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

    // SES Email Identity for sending invoices from noreply@goinvoi.com
    // Verifies the goinvoi.com domain and configures DKIM signing
    const emailIdentity = new aws.ses.EmailIdentity("GoinvoiDomain", {
      email: "goinvoi.com",
    });

    // Enable DKIM signing for email authentication
    const domainDkim = new aws.ses.DomainDkim("GoinvoiDomainDkim", {
      domain: emailIdentity.email,
    });

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

    // User pool client for React app
    // Configures OAuth flow with environment-specific callback URLs
    // Note: In dev, uses localhost. In production, uses placeholder that will be replaced
    // with actual site URL after deployment (Cognito allows updating callback URLs)
    const userPoolClient = userPool.addClient("Web", {
      providers: ["Google"],
      oauth: {
        // Use localhost for dev, wildcard placeholder for production (update after first deploy)
        callbackUrls: [
          $dev ? "http://localhost:5173/auth/callback" : "https://placeholder-update-after-deploy.com/auth/callback"
        ],
        logoutUrls: [
          $dev ? "http://localhost:5173/auth/logout" : "https://placeholder-update-after-deploy.com/auth/logout"
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

    // Lambda Layer: ReportLab for PDF generation
    // Contains ReportLab (>=4.1.0) and Pillow (>=10.0.0) Python dependencies
    // Built from backend/layers/reportlab/requirements.txt
    const reportlabLayer = new aws.lambda.LayerVersion("ReportLabLayer", {
      layerName: "invoi-reportlab-layer",
      code: new $stdlib.asset.FileArchive("./backend/layers/reportlab-build"),
      compatibleRuntimes: ["python3.12", "python3.11"],
      description: "ReportLab and Pillow for PDF generation",
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

    // Phase 1: User profile management
    api.route("GET /api/config", {
      handler: "backend/functions/config.handler",
      link: [usersTable],
    });

    api.route("POST /api/config", {
      handler: "backend/functions/config.handler",
      link: [usersTable],
    });

    // Phase 2: Scan month for existing invoices
    api.route("GET /api/scan-month", {
      handler: "backend/functions/scan_month.handler",
      link: [invoicesTable],
    });

    // Phase 2: Submit monthly report (aggregate weekly invoices into monthly PDF)
    api.route("POST /api/submit/monthly", {
      handler: "backend/functions/submit_monthly.handler",
      link: [usersTable, invoicesTable, bucket],
      layers: [reportlabLayer.arn],
      timeout: "30 seconds",
      memory: "1024 MB",
    });

    // Phase 2: Test ReportLab layer (temporary endpoint for validation)
    api.route("GET /api/test-reportlab", {
      handler: "backend/functions/test_reportlab.handler",
      layers: [reportlabLayer.arn],
      timeout: "10 seconds",
      memory: "512 MB",
    });

    // Phase 3: Test SES email sending (temporary endpoint for validation)
    if ($app.stage === "dev") {
      api.route("GET /api/test-ses", {
        handler: "backend/functions/test_ses.handler",
        timeout: "10 seconds",
        memory: "256 MB",
        permissions: [
          {
            actions: ["ses:SendEmail", "ses:SendRawEmail"],
            resources: ["*"],
          },
        ],
      });
    }

    // TODO: Add PDF generation routes in Phase 2+
    // Example route with ReportLab layer:
    // api.route("POST /api/invoices/generate", {
    //   handler: "backend/functions/generate_invoice.handler",
    //   link: [usersTable, invoicesTable, bucket],
    //   layers: [reportlabLayer.arn],
    //   timeout: "30 seconds",
    //   memory: "1024 MB",
    // });

    // Static site (React frontend) - defined after API/Cognito to pass correct env vars
    // These VITE_* variables are exposed to the React app at build time
    const site = new sst.aws.StaticSite("InvoiWeb", {
      path: "frontend",
      build: {
        command: "npm run build",
        output: "dist",
      },
      environment: {
        VITE_API_URL: api.url,
        VITE_COGNITO_USER_POOL_ID: userPool.id,
        VITE_COGNITO_CLIENT_ID: userPoolClient.id,
        VITE_COGNITO_DOMAIN: userPool.domainUrl, // Hosted UI domain for auth flows
      },
    });

    return {
      ApiEndpoint: api.url,  // Matches verification command: $(sst output ApiEndpoint)
      api: api.url,          // Kept for backward compatibility
      site: site.url,
      reportlabLayerArn: reportlabLayer.arn,  // For testing ReportLab imports
      userPool: userPool.id,
      userPoolClient: userPoolClient.id,
      hostedUI: userPool.domainUrl,
      sesIdentity: emailIdentity.email,  // SES verified domain
      sesDkimTokens: domainDkim.dkimTokens,  // DKIM tokens for DNS configuration
    };
  },
});
