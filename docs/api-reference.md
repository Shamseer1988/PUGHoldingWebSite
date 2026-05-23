# API Reference

The backend exposes a versioned REST API mounted at `/api/v1`.

## Conventions

- All requests/responses are JSON unless noted.
- Authentication: `Authorization: Bearer <access_token>`.
- Errors follow FastAPI defaults: `{ "detail": "..." }`.
- Interactive docs: <http://localhost:8000/docs>.
- OpenAPI schema: <http://localhost:8000/openapi.json>.

## Scopes

Roles are tagged with one of three scopes:

- `system` – grants every scope (used by the Super Admin).
- `website` – Website Admin / CMS surface.
- `hr` – HR ATS portal surface.

Login endpoints reject users that do not hold a role for that surface,
and `/me` endpoints reject access tokens issued for the other portal.

---

## Health

### `GET /`

Returns service metadata and the location of the docs / health endpoints.

### `GET /api/v1/health`

Reports service status and a live PostgreSQL ping.

### `GET /api/v1/health/live`

Lightweight liveness probe (no database call).

---

## Website Admin Auth — `/api/v1/admin/auth`

### `POST /api/v1/admin/auth/login`

Body:

```json
{ "email": "websiteadmin@pug.example.com", "password": "ChangeMe!123" }
```

Response `200`:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 2,
    "email": "websiteadmin@pug.example.com",
    "full_name": "Website Admin",
    "is_active": true,
    "is_superuser": false,
    "last_login_at": "...",
    "roles": [ { "id": 2, "name": "Website Admin", "scope": "website", "permissions": [ ... ] } ],
    "scopes": ["website"],
    "permissions": ["website.menu.read", "website.menu.write", "..."]
  }
}
```

Failure modes:

| Code | Reason                                                                |
| ---- | --------------------------------------------------------------------- |
| 401  | Invalid email or password / inactive account.                         |
| 403  | Account exists but has no website-scoped role.                        |
| 422  | Invalid request payload (e.g. malformed email).                       |

Every attempt writes an `audit_logs` row tagged with one of:

- `auth.login.success`
- `auth.login.failed` (`details.reason`: `invalid_credentials` | `inactive`)
- `auth.login.wrong_scope`

### `POST /api/v1/admin/auth/logout`

Requires a valid website-scoped bearer token. Returns `204` and writes an
`auth.logout` audit row. The frontend is responsible for discarding the
token.

### `GET /api/v1/admin/auth/me`

Returns the same `user` payload as login for the bearer holder.

---

## HR Admin Auth — `/api/v1/hr/auth`

Identical surface, scoped to HR:

- `POST /api/v1/hr/auth/login`
- `POST /api/v1/hr/auth/logout`
- `GET  /api/v1/hr/auth/me`

A website-scoped token presented at any `/hr/auth/*` endpoint is
rejected with `403`. The reverse is also enforced.

---

## Future surfaces (added in later phases)

- Public website APIs (Phase 6): site settings, menus, hero slides,
  pages, companies, leadership messages, news, jobs, careers
  applications, contact, newsletter, media, public AI assistant.
- Website Admin APIs (Phase 5): CRUD for every CMS resource, settings,
  audit log.
- HR ATS APIs (Phase 7+): dashboard stats, jobs, candidates, CV upload
  + parsing, scoring, AI review, workflow, interviews, reports,
  exports, HR audit log.
