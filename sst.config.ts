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

    // Phase 1: Config endpoint - user profile management
    api.route("GET /api/config", {
      handler: "backend/functions/config.handler",
      link: [usersTable],
    });

    // TODO: Add more routes in future phases

    // Static site (React frontend)
    const site = new sst.aws.StaticSite("InvoiWeb", {
      path: "frontend",
      build: {
        command: "npm run build",
        output: "dist",
      },
      environment: {
        VITE_API_URL: api.url,
      },
    });

    return {
      ApiEndpoint: api.url,  // Matches verification command: $(sst output ApiEndpoint)
      api: api.url,          // Kept for backward compatibility
      site: site.url
    };
  },
});
