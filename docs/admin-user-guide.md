# Website Admin User Guide

The Website Admin portal lives under <http://localhost:3000/admin>.
Phase 2 ships the login and a placeholder dashboard; full CRUD modules
arrive in Phase 5.

## Logging in

1. Visit <http://localhost:3000/admin/login>.
2. Enter your email and password.
3. After a successful login you land on the protected dashboard
   placeholder, which shows your account, roles, and permissions.

The default seed credentials (development only) are:

- **Email:** `websiteadmin@pug.example.com`
- **Password:** `ChangeMe!123`

Run `python -m app.scripts.seed_users` (with the backend venv active)
to (re)create the seed accounts.

## Cross-portal isolation

Accounts that only have HR roles cannot log in here — the API returns
`403 This account does not have access to this portal` and writes an
`auth.login.wrong_scope` row to the audit log. The reverse is also
true: a website-only account is rejected at `/hr/login`.

The Super Admin account (`superadmin@pug.example.com`) has
`scope=system` and can sign in to either portal.

## Logging out

Use the **Sign out** button on the dashboard placeholder. Logout:

1. Calls `POST /api/v1/admin/auth/logout` on the backend (writes an
   `auth.logout` audit row).
2. Clears the `pug.auth.admin` token from `localStorage`.
3. Redirects you to `/admin/login`.

If the backend is down, the client-side token is still cleared so the
session can't be reused.

## Coming in Phase 5

- Dashboard with KPIs and Recharts widgets
- Menu management (drag-to-reorder, dropdown structure)
- Hero slider management (image/video uploads, scheduling)
- Page content management
- Group companies management
- Leadership messages management
- News and events management
- Media gallery management
- Contact inbox with reply history
- Newsletter subscribers (with CSV export)
- Site / theme / SEO settings
- Email and AI configuration pages
- Sitemap management
- Website audit log viewer
