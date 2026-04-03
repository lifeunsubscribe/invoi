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

    // Phase 2: Test ReportLab layer (temporary endpoint for validation)
    api.route("GET /api/test-reportlab", {
      handler: "backend/functions/test_reportlab.handler",
      layers: [reportlabLayer.arn],
      timeout: "10 seconds",
      memory: "512 MB",
    });

    // TODO: Add PDF generation routes in Phase 2+
    // Example route with ReportLab layer:
    // api.route("POST /api/invoices/generate", {
    //   handler: "backend/functions/generate_invoice.handler",
    //   link: [usersTable, invoicesTable, bucket],
    //   layers: [reportlabLayer.arn],
    //   timeout: "30 seconds",
    //   memory: "1024 MB",
    // });

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
      site: site.url,
      reportlabLayerArn: reportlabLayer.arn,  // For testing ReportLab imports
    };
  },
});
