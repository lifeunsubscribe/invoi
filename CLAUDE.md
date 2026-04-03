# CLAUDE.md

## Git
- Do not add Co-Authored-By lines to commit messages.

## Project
- Invoi is a serverless invoicing app for hourly 1099 contractors.
- See `docs/ADR-webapp-migration.md` for architecture decisions and migration phases.
- Frontend: React SPA (Vite) in `frontend/`
- Backend: Python Lambda functions in `backend/`
- Infrastructure: SST (Ion) in `sst.config.ts`
- Do NOT modify the `invoice-builder` sibling repo — it is in maintenance mode.
