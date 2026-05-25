# HR ATS User Guide

The HR ATS portal lives under <http://localhost:3000/hr>. Phase 2 ships
the login and a placeholder dashboard; the real ATS modules arrive
across Phases 7–16.

## Logging in

1. Visit <http://localhost:3000/hr/login>.
2. Enter your email and password.
3. After a successful login you land on the protected dashboard
   placeholder showing your account, roles, and permissions.

Default seed credentials (development only):

| Email                          | Role          |
| ------------------------------ | ------------- |
| `hrmanager@pug.example.com`    | HR Manager    |
| `hrexecutive@pug.example.com`  | HR Executive  |
| `interviewer@pug.example.com`  | Interviewer   |

All seed users share the password **`ChangeMe!123`**. Run
`python -m app.scripts.seed_users` from the `backend/` directory (with
the venv active) to create them.

## Role differences (Phase 2 baseline permissions)

- **HR Manager** – full recruitment access: dashboard, jobs, candidates
  (incl. salary), CV download, score override, blacklist, interviews,
  reports + export, HR users, audit log.
- **HR Executive** – day-to-day recruitment: dashboard, jobs (read),
  candidates (read/write), CV download, interviews, reports (read).
- **Interviewer** – dashboard + interview read/write only.

These map to the permission keys defined in
`backend/app/scripts/seed_users.py`. Later phases (Phases 7–16) will
enforce these keys at every CRUD endpoint and toggle UI visibility
accordingly.

## Cross-portal isolation

HR accounts cannot log in at `/admin/login` — the backend returns `403`
and writes an `auth.login.wrong_scope` row to the audit log.

## Logging out

Use the **Sign out** button on the dashboard placeholder. Logout calls
`POST /api/v1/hr/auth/logout`, writes an audit row, clears the
`pug.auth.hr` token from localStorage, and redirects you to
`/hr/login`.

## Coming in Phases 7–16

- HR dashboard with KPIs and Recharts widgets (pipeline funnel,
  monthly application trend, etc.)
- Job opening master (create / edit / close)
- Candidate applications from the public careers page
- HR manual CV upload and bulk ZIP import
- CV parsing (PDF, DOCX, optional OCR)
- Rule-based scoring engine out of 100 with breakdown and manual
  override (requires reason)
- Optional Azure OpenAI candidate review (advisory only — never
  selects or rejects)
- Candidate workflow (CV Received → … → Joined / Rejected /
  Blacklisted) with mandatory rejection reasons and blacklist approval
- Interview scheduling and interviewer feedback
- Offer tracking
- Advanced search and filters
- HR reports + Excel / CSV / PDF export
- HR users, roles, and permissions
- HR audit log
