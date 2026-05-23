# Testing Checklist

A living checklist that grows with every phase. Tick items as their
phase ships.

## Phase 1 — Project foundation

- [x] Backend installs cleanly (`pip install -r requirements.txt`).
- [x] FastAPI imports and exposes `/`, `/docs`, `/api/v1/health`,
      `/api/v1/health/live`.
- [x] Frontend installs cleanly (`npm install`).
- [x] Frontend type-check passes (`npm run type-check`).
- [x] Frontend production build succeeds (`npm run build`).
- [x] Landing splash renders backend health card.

## Phase 2 — Auth + separate logins

Automated (pytest):

- [x] Password hashing roundtrip.
- [x] JWT access/refresh tokens encode the right claims.
- [x] Invalid JWT decode raises `JWTError`.
- [x] Website admin can login at `/api/v1/admin/auth/login`.
- [x] HR admin can login at `/api/v1/hr/auth/login`.
- [x] Super admin can login at both endpoints.
- [x] HR user **cannot** login via `/admin/auth/login` (403).
- [x] Website user **cannot** login via `/hr/auth/login` (403).
- [x] Admin token rejected on `/hr/auth/me` (403).
- [x] HR token rejected on `/admin/auth/me` (403).
- [x] Invalid password returns 401.
- [x] Unknown email returns 401.
- [x] Inactive user cannot login.
- [x] `/me` endpoints require a token (401 without).
- [x] Logout writes `auth.logout` audit entry.
- [x] Failed login writes `auth.login.failed` audit entry with reason.
- [x] Wrong-scope login writes `auth.login.wrong_scope` audit entry.

Manual:

- [ ] `python -m app.scripts.seed_users` succeeds and reports five users.
- [ ] Re-running the seed script is idempotent (no errors, no
      duplicate users).
- [ ] Visit `/admin/login`, sign in with
      `websiteadmin@pug.example.com / ChangeMe!123`, land on `/admin`.
- [ ] Visit `/hr/login`, sign in with
      `hrmanager@pug.example.com / ChangeMe!123`, land on `/hr`.
- [ ] HR user sees a 403 error when attempting `/admin/login`.
- [ ] Sign-out button on each portal returns you to the login page and
      clears the token from `localStorage`.

## Phase 3 — Public UI foundation (planned)

- [ ] No horizontal overflow at 360px, 390px, 430px, 768px,
      1024px, 1440px.
- [ ] Theme toggle persists across reloads.
- [ ] Hamburger menu opens/closes on mobile.
- [ ] Floating Ask PUG AI placeholder visible.

## Phase 19 — Security and validation (planned)

- [ ] Input validation rejects malformed payloads.
- [ ] File uploads enforce allowed types and size limits.
- [ ] Permission tests for both admin surfaces pass.
- [ ] Public AI cannot expose private candidate data.
- [ ] HR AI cannot select/reject candidates automatically.
- [ ] Audit log covers every sensitive action.
- [ ] Bearer token storage hardening (httpOnly cookies + CSRF).

> Phases 4–18 add their own sections to this file as they ship.
