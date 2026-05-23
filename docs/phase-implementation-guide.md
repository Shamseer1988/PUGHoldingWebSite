# Phase Implementation Guide

This document tracks the 20-phase delivery plan for the Paris United
Group Holding website and HR ATS portal. The full project master prompt
lives at the repo root in
[`PUG_Dynamic_Website_HR_ATS_Phase_Prompt.txt`](../PUG_Dynamic_Website_HR_ATS_Phase_Prompt.txt).

## Workflow

1. Implement one phase end-to-end.
2. Document scope, files touched, migrations added, test commands.
3. Stop and wait for review and approval.
4. Only then start the next phase.

## Phase status

| Phase | Title                                            | Status      |
| ----- | ------------------------------------------------ | ----------- |
| 1     | Project foundation                               | **Done**    |
| 2     | Authentication, roles, separate logins           | **Done**    |
| 3     | Public website UI foundation                     | Planned     |
| 4     | Public pages (dummy content)                     | Planned     |
| 5     | Website admin content management                 | Planned     |
| 6     | Public website backend API integration           | Planned     |
| 7     | HR ATS database and core models                  | Planned     |
| 8     | HR ATS admin dashboard                           | Planned     |
| 9     | Job opening management                           | Planned     |
| 10    | Candidate application and CV upload              | Planned     |
| 11    | CV parsing and data extraction                   | Planned     |
| 12    | Candidate scoring engine                         | Planned     |
| 13    | HR AI candidate review                           | Planned     |
| 14    | Candidate workflow pipeline                      | Planned     |
| 15    | Interview management                             | Planned     |
| 16    | HR advanced search, filters, reports, export     | Planned     |
| 17    | Public AI assistant                              | Planned     |
| 18    | Responsive UI polish and mobile testing          | Planned     |
| 19    | Security, audit, validation, and testing         | Planned     |
| 20    | Deployment documentation and final package       | Planned     |

## Phase 2 deliverables

Backend:
- Tables: `users`, `roles`, `permissions`, `user_roles`,
  `role_permissions`, `audit_logs`.
- bcrypt-backed password hashing (pre-hashed with SHA-256 to sidestep
  the 72-byte bcrypt limit).
- JWT issuance / verification (`python-jose`) with distinct
  `access` / `refresh` token types.
- Two separate auth routers:
  - `/api/v1/admin/auth/login | logout | me`
  - `/api/v1/hr/auth/login | logout | me`
- Scope guards (`require_website_admin`, `require_hr_admin`,
  `require_permission(...)`).
- Audit log entries on every login success, failed login (with reason),
  wrong-scope login, and logout.
- Alembic migration `20260523_0001_phase2_auth_tables`.
- Idempotent seed CLI: `python -m app.scripts.seed_users`.

Frontend:
- New shadcn primitives: `Input`, `Label`, `Card`.
- `lib/auth.ts` – two isolated token slots (`pug.auth.admin`,
  `pug.auth.hr`), `login`, `logout`, `fetchMe`, error types.
- `AuthProvider` + `useAuth` keyed per scope, `AuthGuard` for
  client-side route protection.
- `/admin/login` and `/hr/login` pages with shared `LoginForm`
  component (glass card, show/hide password, seed-credentials hint
  in dev).
- `/admin` and `/hr` now show a protected dashboard placeholder with
  the signed-in user, scopes, roles, permission count, and a logout
  button.

Docs:
- Auth endpoints documented in `docs/api-reference.md`.
- Seed users walkthrough in `docs/setup-guide.md`.
- Login instructions in `docs/admin-user-guide.md` and
  `docs/hr-ats-user-guide.md`.

## Definition of done for any phase

- Code lives on the agreed feature branch.
- Backend tests pass: `pytest -q`.
- Frontend type-check passes: `npm run type-check`.
- Frontend production build succeeds: `npm run build`.
- Documentation updated (this guide, setup guide, api reference,
  testing checklist).
- Summary message lists added files, migrations, run commands, and
  any open questions.
