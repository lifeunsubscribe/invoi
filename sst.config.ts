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

    // Alert email for CloudWatch alarms (set via `sst secret set AlertEmail <value>`)
    const alertEmail = new sst.Secret("AlertEmail");

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
    // In dev: uses localhost. In production: uses goinvoi.com custom domain
    const userPoolClient = userPool.addClient("Web", {
      providers: ["Google"],
      oauth: {
        // Use localhost for dev, custom domain for production
        callbackUrls: [
          $dev ? "http://localhost:5173/auth/callback" : "https://goinvoi.com/auth/callback"
        ],
        logoutUrls: [
          $dev ? "http://localhost:5173/auth/logout" : "https://goinvoi.com/auth/logout"
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
    // In production, uses custom domain api.goinvoi.com with ACM certificate
    // In dev, uses auto-generated API Gateway URL
    const api = new sst.aws.ApiGatewayV2("InvoiApi", {
      domain: $app.stage === "production" ? {
        name: "api.goinvoi.com",
        dns: sst.aws.dns(), // Use Route53 for DNS management
      } : undefined,
      cors: {
        // Allow requests from custom domain in production, localhost in dev
        allowOrigins: $app.stage === "production"
          ? ["https://goinvoi.com", "https://www.goinvoi.com"]
          : ["*"],
        allowMethods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allowHeaders: ["Content-Type", "Authorization"],
      },
      transform: {
        // Stage-level throttling: aggregate across all users (API Gateway built-in)
        // Per-user throttling is handled in Lambda handlers via services/rate_limit.py
        // Rate limit: 100 requests/second aggregate
        // Burst limit: 200 requests (handles short traffic spikes)
        // When exceeded, API Gateway returns 429 Too Many Requests
        api: (args) => {
          args.defaultRouteSettings = {
            throttlingBurstLimit: 200,
            throttlingRateLimit: 100,
          };
        },
      },
    });

    // JWT Authorizer for protected routes
    api.addAuthorizer({
      name: "cognito",
      jwt: {
        issuer: $interpolate`https://cognito-idp.${aws.getRegionOutput().name}.amazonaws.com/${userPool.id}`,
        audiences: [userPoolClient.id],
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

    // Phase 2: Submit weekly invoice (generate PDF, store in S3, save metadata)
    // Uses TransactWriteItems to atomically increment invoice number and create record
    api.route("POST /api/submit/weekly", {
      handler: "backend/functions/submit_weekly.handler",
      link: [usersTable, invoicesTable, bucket],
      layers: [reportlabLayer.arn],
      timeout: "30 seconds",
      memory: "1024 MB",
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

    // Phase 3: Update invoice status (mark paid, sent, etc.)
    api.route("PATCH /api/invoices/{id}/status", {
      handler: "backend/functions/invoices.handler",
      link: [invoicesTable],
    });

    // Phase 4: List invoices with filtering and pagination
    api.route("GET /api/invoices", {
      handler: "backend/functions/invoices.handler",
      link: [invoicesTable],
    });

    // Phase 4: Get single invoice by ID
    api.route("GET /api/invoices/{id}", {
      handler: "backend/functions/invoices.handler",
      link: [invoicesTable],
    });

    // Phase 4: Get signed S3 URL for PDF download
    api.route("GET /api/pdf/{id}", {
      handler: "backend/functions/pdf.handler",
      link: [invoicesTable, bucket],
      timeout: "10 seconds",
      memory: "256 MB",
    });

    // Phase 4: Export invoices as ZIP or CSV
    api.route("POST /api/export", {
      handler: "backend/functions/export.handler",
      link: [invoicesTable, bucket],
      timeout: "30 seconds",
      memory: "1024 MB",
      auth: { jwt: { authorizer: "cognito" } },
    });

    // Phase 4: Resend invoices to clients
    api.route("POST /api/invoices/resend", {
      handler: "backend/functions/resend.handler",
      link: [usersTable, invoicesTable, bucket],
      timeout: "60 seconds",
      memory: "512 MB",
      auth: { jwt: { authorizer: "cognito" } },
      permissions: [
        {
          actions: ["ses:SendEmail", "ses:SendRawEmail"],
          resources: [
            $interpolate`arn:aws:ses:${aws.getRegionOutput().name}:${aws.getCallerIdentityOutput().accountId}:identity/${emailIdentity.email}`,
          ],
        },
      ],
    });

    // Phase 5: Import historical invoices with sidecar JSON
    api.route("POST /api/import", {
      handler: "backend/functions/import_data.handler",
      link: [usersTable, invoicesTable, bucket],
      timeout: "60 seconds",
      memory: "1024 MB",
      auth: { jwt: { authorizer: "cognito" } },
    });

    // Phase 4: Logo upload, retrieval, and deletion
    api.route("GET /api/logo", {
      handler: "backend/functions/logo.handler",
      link: [usersTable, bucket],
      timeout: "10 seconds",
      memory: "512 MB",
    });

    api.route("POST /api/logo", {
      handler: "backend/functions/logo.handler",
      link: [usersTable, bucket],
      timeout: "10 seconds",
      memory: "512 MB",
    });

    api.route("DELETE /api/logo", {
      handler: "backend/functions/logo.handler",
      link: [usersTable, bucket],
      timeout: "10 seconds",
      memory: "256 MB",
    });

    // Phase 3: Test SES email sending (temporary endpoint for validation)
    // Restricted to dev stage and requires TEST_SES_SECRET header for authentication
    if ($app.stage === "dev") {
      const testSesSecret = new sst.Secret("TestSesSecret");
      api.route("GET /api/test-ses", {
        handler: "backend/functions/test_ses.handler",
        timeout: "10 seconds",
        memory: "256 MB",
        link: [testSesSecret],
        permissions: [
          {
            actions: ["ses:SendEmail", "ses:SendRawEmail"],
            resources: [
              $interpolate`arn:aws:ses:${aws.getRegionOutput().name}:${aws.getCallerIdentityOutput().accountId}:identity/${emailIdentity.email}`,
            ],
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

    // ==========================================
    // CloudWatch Monitoring & Alerts (Phase 6)
    // ==========================================

    // SNS Topic for CloudWatch alarm notifications
    // Sends email alerts when Lambda errors or API Gateway 5xx responses exceed threshold
    const alarmTopic = new aws.sns.Topic("InvoiAlarmTopic", {
      displayName: "Invoi CloudWatch Alarms",
    });

    // Email subscription for alarm notifications
    // Note: Email address will need to confirm subscription after deployment
    new aws.sns.TopicSubscription("InvoiAlarmEmailSubscription", {
      topic: alarmTopic.arn,
      protocol: "email",
      endpoint: alertEmail.value,
    });

    // Lambda Error Rate Alarm
    // Triggers when Lambda error rate exceeds 1% over 5 minutes
    // Monitors aggregate errors across all Lambda functions
    const lambdaErrorAlarm = new aws.cloudwatch.MetricAlarm("InvoiLambdaErrorAlarm", {
      name: "Invoi-Lambda-Errors",
      comparisonOperator: "GreaterThanThreshold",
      evaluationPeriods: 2, // Requires 2 consecutive 5-min periods (10 min total) to alarm
      threshold: 1, // 1% error rate
      actionsEnabled: true,
      alarmActions: [alarmTopic.arn], // Notify when alarm triggers
      okActions: [alarmTopic.arn], // Notify when alarm recovers
      alarmDescription: "Alerts when Lambda error rate exceeds 1%",
      treatMissingData: "notBreaching", // Don't alarm if no data (e.g., no invocations)

      // Using metric math to calculate error rate percentage
      // (Errors / Invocations) * 100
      metrics: [
        {
          id: "errors",
          metric: {
            namespace: "AWS/Lambda",
            metricName: "Errors",
            stat: "Sum",
            period: 300, // 5 minutes
          },
          returnData: false,
        },
        {
          id: "invocations",
          metric: {
            namespace: "AWS/Lambda",
            metricName: "Invocations",
            stat: "Sum",
            period: 300,
          },
          returnData: false,
        },
        {
          id: "error_rate",
          expression: "IF(invocations > 0, (errors / invocations) * 100, 0)",
          label: "Error Rate (%)",
          returnData: true,
        },
      ],
    });

    // API Gateway 5xx Error Rate Alarm
    // Triggers when API Gateway 5xx response rate exceeds 1% over 5 minutes
    const apiErrorAlarm = new aws.cloudwatch.MetricAlarm("InvoiApi5xxAlarm", {
      name: "Invoi-API-5xx",
      comparisonOperator: "GreaterThanThreshold",
      evaluationPeriods: 2, // Requires 2 consecutive 5-min periods (10 min total) to alarm
      threshold: 1, // 1% error rate
      actionsEnabled: true,
      alarmActions: [alarmTopic.arn], // Notify when alarm triggers
      okActions: [alarmTopic.arn], // Notify when alarm recovers
      alarmDescription: "Alerts when API Gateway 5xx error rate exceeds 1%",
      treatMissingData: "notBreaching", // Don't alarm if no data (e.g., no API requests)

      // Calculate 5xx error rate as percentage of total requests
      metrics: [
        {
          id: "errors5xx",
          metric: {
            namespace: "AWS/ApiGateway",
            metricName: "5XXError",
            stat: "Sum",
            period: 300,
            dimensions: {
              ApiId: api.nodes.api.id,
            },
          },
          returnData: false,
        },
        {
          id: "requests",
          metric: {
            namespace: "AWS/ApiGateway",
            metricName: "Count",
            stat: "Sum",
            period: 300,
            dimensions: {
              ApiId: api.nodes.api.id,
            },
          },
          returnData: false,
        },
        {
          id: "error_rate",
          expression: "IF(requests > 0, (errors5xx / requests) * 100, 0)",
          label: "5xx Error Rate (%)",
          returnData: true,
        },
      ],
    });

    // CloudWatch Dashboard
    // Displays key metrics: Lambda errors/invocations, API Gateway requests/5xx errors
    // Uses $interpolate (not $jsonStringify) to properly embed Pulumi outputs like api.nodes.api.id
    // Dashboard body is JSON string with 4 metric widgets in 2x2 grid layout
    const dashboard = new aws.cloudwatch.Dashboard("InvoiDashboard", {
      dashboardName: "Invoi-Metrics",
      dashboardBody: $interpolate`{
        "widgets": [
          {
            "type": "metric",
            "properties": {
              "metrics": [
                ["AWS/Lambda", "Invocations", { "stat": "Sum", "label": "Total Invocations" }],
                [".", "Errors", { "stat": "Sum", "label": "Total Errors" }]
              ],
              "period": 300,
              "stat": "Sum",
              "region": "${aws.getRegionOutput().name}",
              "title": "Lambda Invocations & Errors",
              "yAxis": { "left": { "min": 0 } }
            },
            "width": 12,
            "height": 6,
            "x": 0,
            "y": 0
          },
          {
            "type": "metric",
            "properties": {
              "metrics": [
                ["AWS/Lambda", "Duration", { "stat": "Average", "label": "Avg Duration" }],
                ["...", { "stat": "Maximum", "label": "Max Duration" }]
              ],
              "period": 300,
              "stat": "Average",
              "region": "${aws.getRegionOutput().name}",
              "title": "Lambda Duration (ms)",
              "yAxis": { "left": { "min": 0 } }
            },
            "width": 12,
            "height": 6,
            "x": 12,
            "y": 0
          },
          {
            "type": "metric",
            "properties": {
              "metrics": [
                ["AWS/ApiGateway", "Count", { "stat": "Sum", "label": "Total Requests", "dimensions": { "ApiId": "${api.nodes.api.id}" } }],
                [".", "5XXError", { "stat": "Sum", "label": "5xx Errors", "dimensions": { "ApiId": "${api.nodes.api.id}" } }],
                [".", "4XXError", { "stat": "Sum", "label": "4xx Errors", "dimensions": { "ApiId": "${api.nodes.api.id}" } }]
              ],
              "period": 300,
              "stat": "Sum",
              "region": "${aws.getRegionOutput().name}",
              "title": "API Gateway Requests & Errors",
              "yAxis": { "left": { "min": 0 } }
            },
            "width": 12,
            "height": 6,
            "x": 0,
            "y": 6
          },
          {
            "type": "metric",
            "properties": {
              "metrics": [
                ["AWS/ApiGateway", "Latency", { "stat": "Average", "label": "Avg Latency", "dimensions": { "ApiId": "${api.nodes.api.id}" } }],
                ["...", { "stat": "p99", "label": "P99 Latency", "dimensions": { "ApiId": "${api.nodes.api.id}" } }]
              ],
              "period": 300,
              "stat": "Average",
              "region": "${aws.getRegionOutput().name}",
              "title": "API Gateway Latency (ms)",
              "yAxis": { "left": { "min": 0 } }
            },
            "width": 12,
            "height": 6,
            "x": 12,
            "y": 6
          }
        ]
      }`,
    });

    // Set log retention to 30 days for all Lambda function log groups
    // SST Ion creates Lambda functions with naming pattern based on the handler path
    // For api.route() handlers, SST uses the handler file name (without extension) as the function name
    // Pattern: /aws/lambda/<app-name>-<stage>-<handler-basename>
    // Example: /aws/lambda/invoi-dev-hello (from backend/functions/hello.handler)
    const logRetentionDays = 30;

    // Helper function to set log retention for a Lambda function log group
    // Uses skipDestroy to avoid conflicts with SST-managed log groups
    // and retentionInDays to ensure 30-day retention regardless of when the group was created
    const setLogRetention = (handlerBaseName: string, logicalName: string) => {
      return new aws.cloudwatch.LogGroup(`${logicalName}LogGroup`, {
        name: $interpolate`/aws/lambda/${$app.name}-${$app.stage}-${handlerBaseName}`,
        retentionInDays: logRetentionDays,
        skipDestroy: true, // Don't delete log group on destroy - let SST manage lifecycle
      });
    };

    // Set log retention for all API route handlers
    // Handler base names are extracted from the handler paths (e.g., "backend/functions/hello.handler" -> "hello")
    const handlerBaseNames = [
      "hello",
      "config",
      "scan_month",
      "submit_weekly",
      "submit_monthly",
      "test_reportlab",
      "invoices",
      "pdf",
      "export",
      "resend",
      "import_data",
      "logo",
    ];

    handlerBaseNames.forEach((baseName) => {
      setLogRetention(baseName, `${baseName}Function`);
    });

    // Add test-ses function log retention for dev stage only
    if ($app.stage === "dev") {
      setLogRetention("test_ses", "testSesFunction");
    }

    // Static site (React frontend) - defined after API/Cognito to pass correct env vars
    // These VITE_* variables are exposed to the React app at build time
    // In production, uses custom domain goinvoi.com with ACM certificate and CloudFront
    // ACM certificate is created in us-east-1 (required for CloudFront)
    // DNS validation happens automatically via Route53
    const site = new sst.aws.StaticSite("InvoiWeb", {
      path: "frontend",
      build: {
        command: "npm run build",
        output: "dist",
      },
      domain: $app.stage === "production" ? {
        name: "goinvoi.com",
        aliases: ["www.goinvoi.com"], // Redirect www to apex
        dns: sst.aws.dns(), // Use Route53 for DNS management
      } : undefined,
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
      // Custom domain outputs (production only)
      // After deploying to production, point your domain registrar to the Route53 nameservers
      customDomain: $app.stage === "production" ? "goinvoi.com" : "N/A (dev stage)",
      apiDomain: $app.stage === "production" ? "api.goinvoi.com" : "N/A (dev stage)",
      // CloudWatch monitoring outputs (Phase 6)
      alarmTopicArn: alarmTopic.arn,
      dashboardName: dashboard.dashboardName,
      lambdaErrorAlarmName: lambdaErrorAlarm.name,
      apiErrorAlarmName: apiErrorAlarm.name,
    };
  },
});
