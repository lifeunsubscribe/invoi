# Invoi

Invoicing for people who work by the hour.

**Website:** [goinvoi.com](https://goinvoi.com)

## Architecture

React SPA on S3/CloudFront + Python Lambda API + DynamoDB + SES + S3.

See `docs/ADR-webapp-migration.md` for full architecture documentation.

## Development

### Frontend
```bash
cd frontend && npm install && npm run dev
```

### Infrastructure
```bash
npx sst dev
```

## Project Status

Migration from desktop app (`invoice-builder`) in progress. See ADR for migration phases.
