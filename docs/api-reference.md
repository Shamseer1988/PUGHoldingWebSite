# API Reference

The backend exposes a versioned REST API mounted at `/api/v1`.

## Conventions

- All requests/responses are JSON unless noted.
- Authentication (added in Phase 2) is `Authorization: Bearer <token>`.
- Errors follow FastAPI defaults: `{ "detail": "..." }`.
- Interactive docs: <http://localhost:8000/docs>.
- OpenAPI schema: <http://localhost:8000/openapi.json>.

## Phase 1 endpoints

### `GET /`

Returns service metadata and the location of the docs/health endpoints.

```json
{
  "service": "PUG Holding API",
  "version": "0.1.0",
  "docs": "/docs",
  "health": "/api/v1/health"
}
```

### `GET /api/v1/health`

Reports service status and a live PostgreSQL ping.

**Response 200**

```json
{
  "status": "ok",
  "service": "PUG Holding API",
  "version": "0.1.0",
  "environment": "development",
  "database": "connected",
  "timestamp": "2026-05-23T10:23:45.123456+00:00"
}
```

`database` is `"disconnected"` when PostgreSQL is unreachable.

### `GET /api/v1/health/live`

Lightweight liveness probe (no database call).

**Response 200**

```json
{ "status": "alive" }
```

## Future surfaces (added in later phases)

- Public website APIs (Phase 6): site settings, menus, hero slides,
  pages, companies, leadership messages, news, jobs, careers
  applications, contact, newsletter, media, public AI assistant.
- Website Admin APIs (Phase 5): login, CRUD for every CMS resource,
  settings, audit log.
- HR ATS APIs (Phase 7+): HR login, dashboard stats, jobs, candidates,
  CV upload + parsing, scoring, AI review, workflow, interviews,
  reports, exports, HR audit log.
