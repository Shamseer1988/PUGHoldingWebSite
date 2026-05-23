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
| 3     | Public website UI foundation                     | **Done**    |
| 4     | Public pages (dummy content)                     | **Done**    |
| 5     | Website admin content management                 | **Done**    |
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

## Phase 5 deliverables

**Brand theme refresh.** The full UI now uses the Paris United Group
brand palette — deep forest green primary, warm tan/gold accent, warm
cream surfaces in light mode, deep emerald-charcoal in dark mode.
The mandala logo mark is rendered inline as an SVG that adapts to both
themes. Hero slide and sector gradients use the new `pug-green-*` /
`pug-gold-*` Tailwind colour scales.

**Backend (FastAPI + SQLAlchemy + Alembic):**

- New tables: `hero_slides`, `companies`, `company_services`,
  `leadership_messages`, `news_items`, `contact_messages`,
  `newsletter_subscribers`, `site_settings` (single row).
- Alembic migration `20260523_0002_phase5_cms_tables`.
- 20-endpoint CMS router at `/api/v1/admin/cms/*` (CRUD for hero
  slides, companies, leadership, news, plus contact inbox actions
  (read/archive/reply), newsletter subscribers list/delete, site
  settings get/patch, dashboard summary, audit log viewer).
- Every CRUD action audit-logged with action, target_type, target_id,
  changed keys, ip, user-agent.
- Idempotent seed script: `python -m app.scripts.seed_cms` populates
  the 14 companies, 4 leadership entries, 6 news items, 3 hero slides,
  and default site settings.
- 8 new integration tests (scope isolation, CRUD round-trips, slug
  conflicts, dashboard summary, audit emission). 28 tests total.

**Frontend (Next.js admin shell):**

- New shell components (`components/admin/*`): `AdminShell`,
  `AdminSidebar`, `AdminTopbar`, `EmptyState`.
- New shadcn primitive: `Table` (`TableHeader`, `TableBody`,
  `TableRow`, `TableHead`, `TableCell`, `TableCaption`).
- New page routes (all guarded by `AuthGuard` against the admin scope):
  - `/admin` — dashboard with 6 KPI cards, two Recharts area charts
    (contact messages per month, news per month), and two preview
    tables (latest messages + latest news).
  - `/admin/hero-slides` — list + drawer-form CRUD.
  - `/admin/companies` — list + drawer-form CRUD with comma-separated
    services field.
  - `/admin/leadership` — list + drawer-form CRUD.
  - `/admin/news` — list + drawer-form CRUD.
  - `/admin/inbox` — message list + reading pane + reply textarea +
    archive.
  - `/admin/subscribers` — list + CSV export + remove.
  - `/admin/settings` — single-form editor for brand, contact, social,
    SEO defaults.
  - `/admin/audit` — filterable audit log viewer (scope + action prefix).
  - `/admin/media`, `/admin/pages`, `/admin/users` — placeholder stubs
    (Phase 5 follow-up).
- `lib/admin/api.ts` — typed authenticated fetch wrapper that pulls
  the bearer token from the per-scope localStorage slot established
  in Phase 2.
- `lib/admin/types.ts` — TypeScript mirrors of every Phase 5 schema.

## Definition of done for any phase

- Code lives on the agreed feature branch.
- Backend tests pass: `pytest -q`.
- Frontend type-check passes: `npm run type-check`.
- Frontend production build succeeds: `npm run build`.
- Documentation updated (this guide, setup guide, api reference,
  testing checklist).
- Summary message lists added files, migrations, run commands, and
  any open questions.
