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

## Phase 7 — HR ATS database and core models

Automated (pytest):

- [x] 12 new model tests pass (53 total).
- [x] `SCORE_WEIGHTS` sums to 100.
- [x] Job opening round-trip + slug uniqueness.
- [x] Candidate + documents + extracted_data + tags + notes round-trip.
- [x] Candidate cascade delete removes documents / extracted data / tags.
- [x] (candidate_id, tag) unique constraint enforced.
- [x] Application unique on (candidate_id, job_opening_id).
- [x] Score + breakdown + AI review round-trip.
- [x] Status history persists.
- [x] Interview + feedback round-trip.
- [x] Offer round-trip + uniqueness per application.

Manual:

- [ ] `alembic upgrade head` applies `20260524_0001_phase7_hr_ats_tables`
      cleanly on the dev database.
- [ ] `alembic current` reports `20260524_0001 (head)`.
- [ ] `python -m app.scripts.seed_hr` reports `hr_job_openings : 8`.
- [ ] In psql / pgAdmin, the 14 `hr_*` tables exist with the right
      indexes and FKs.
- [ ] `alembic downgrade -1` removes them cleanly (then `upgrade head`
      brings them back).

## Phase 6 — Public website API integration

Automated (pytest):

- [x] 13 new public-endpoint tests pass (41 total).
- [x] Hero slides only return `is_active=true`.
- [x] Companies filter on `is_active=true` and optional `?category=`.
- [x] Company detail returns 404 for hidden slugs.
- [x] News only returns `is_published=true`; drafts → 404 on detail.
- [x] News `?featured=true` filter works.
- [x] Leadership only returns `is_active=true`.
- [x] Site settings returns defaults when no row exists.
- [x] Contact form persists + writes `public.contact.submit` audit.
- [x] Contact form rejects malformed email (422).
- [x] Newsletter subscribe creates row, is idempotent, reactivates
      inactive emails.

Automated (frontend):

- [x] Type-check clean.
- [x] Production build clean; public pages now ƒ (dynamic) or ●
      (SSG with revalidate).

Manual (start backend + frontend, log in as websiteadmin):

- [ ] Public home page renders hero slides, companies, news, leadership
      from the API (verify by editing one in `/admin` and refreshing
      after ~60s).
- [ ] Edit a company in `/admin/companies`, set `is_active=false`,
      refresh public site — company disappears.
- [ ] Add a new news item, set `is_published=false` — does NOT appear
      on the public news list.
- [ ] Visit `/companies/<hidden-slug>` → 404.
- [ ] Submit the newsletter form on the home page — `/admin/subscribers`
      shows the new entry.
- [ ] Submit the contact form on `/contact` — `/admin/inbox` shows the
      new message (with the department badge).
- [ ] Edit site settings (phone, email, social URLs) — public footer
      and contact page pick them up after revalidate.
- [ ] Stop the backend; reload public pages — they still render with
      empty arrays + the "fallback" site settings (no crash).

## Phase 5 — Website admin CMS

Automated (pytest):

- [x] 8 new integration tests pass (28 total).
- [x] Scope isolation: HR token rejected at `/admin/cms/*` (403).
- [x] Authentication required: no token returns 401.
- [x] Company CRUD round-trip (create, update, delete) + audit emission.
- [x] Company create rejects duplicate slug (409).
- [x] News create + list.
- [x] Hero slide create + patch + list + delete.
- [x] Site settings auto-create on first read; update persists.
- [x] Dashboard summary returns all stats + bucketed series.

Automated (frontend):

- [x] Type-check clean.
- [x] Production build generates 11 admin pages.

Manual (run the backend + frontend, log in as websiteadmin):

- [ ] Theme: navbar / footer / hero / sectors / cards all use the new
      forest green + warm gold brand palette.
- [ ] Logo: mandala SVG renders on the navbar, the footer, the admin
      sidebar, and the login page.
- [ ] /admin lands on the dashboard with KPI cards + two area charts.
- [ ] /admin/hero-slides — create / edit / delete a slide; toggling
      `is_active` changes the badge.
- [ ] /admin/companies — create with services, edit services list,
      delete. Duplicate-slug attempts surface a clear error.
- [ ] /admin/leadership — create / edit / delete entries.
- [ ] /admin/news — create with category / featured / published
      flags; delete works.
- [ ] /admin/inbox — list + click a message; replying saves and
      flags the message; archive hides it from default list.
- [ ] /admin/subscribers — CSV export downloads correctly.
- [ ] /admin/settings — saves and reloads with the new values.
- [ ] /admin/audit — every CRUD action above shows up in the log
      with action, target, actor, IP, timestamp.
- [ ] Sidebar collapses to drawer on mobile (≤ 1024 px).
- [ ] No horizontal overflow at 360 / 390 / 430 / 768 / 1024 / 1440 px.
- [ ] Public site still works end-to-end with the new theme.

## Phase 4 — Public pages (dummy content)

Automated:

- [x] Frontend type-check passes (`npm run type-check`).
- [x] Frontend production build succeeds (`npm run build`) and
      generates all 14 company detail pages, 6 news detail pages,
      and 8 job detail pages.
- [x] Backend test suite still green (20 passed).

Manual (run `npm run dev` and walk through):

- [ ] Home: hero auto-rotates between 3 slides; pause/play button
      works; clicking dot indicators jumps to that slide.
- [ ] Home: animated stats counters count up when scrolled into view.
- [ ] Home: sector cards (Retail / Distribution / Services) link to
      filtered `/companies?category=...`.
- [ ] Home: company cards, news cards, job cards all navigate to the
      right detail pages.
- [ ] Home: newsletter form shows a "Subscribing…" state and a success
      message on submit.
- [ ] About: vision, mission, core values, history timeline animate
      in; leadership cards show full messages.
- [ ] Companies: clicking a category chip filters the list and the
      URL updates (`?category=retail`).
- [ ] Company detail: page renders for all 14 companies (try
      `/companies/paris-hyper-market`, `/companies/yellowtech-garage`).
- [ ] News list: featured strip + latest grid.
- [ ] News detail: cover, body, gallery, share buttons render.
- [ ] Careers: search by title / skill works; department / company /
      location / type filters narrow results; reset clears all.
- [ ] Job detail: responsibilities, requirements, skills, quick facts
      render. **Apply Now form** opens, file picker accepts PDF/DOC,
      consent checkbox is required, success state appears on submit.
- [ ] Contact: department dropdown lists 7 options. Form shows a
      success state on submit.
- [ ] Media: 12 tiles, category chips filter, clicking a tile opens
      the lightbox; Esc / backdrop / X close it.
- [ ] All pages remain responsive at 360 / 390 / 430 / 768 / 1024 /
      1440 px with no horizontal overflow.
- [ ] Theme toggle still flips light/dark across every new page.
- [ ] Floating Ask PUG AI launcher visible on every public page.

## Phase 3 — Public UI foundation

Automated:

- [x] Frontend type-check passes (`npm run type-check`).
- [x] Frontend production build succeeds (`npm run build`) and
      generates `/`, `/about`, `/companies`, `/news`, `/careers`,
      `/contact`, `/media` under the public layout.
- [x] Backend test suite still green (20 passed).

Manual (run `npm run dev` and walk through):

- [ ] No horizontal overflow at 360px, 390px, 430px, 768px,
      1024px, 1440px (use Chrome DevTools device toolbar).
- [ ] Navbar starts transparent and turns into a glass bar after
      scrolling a few pixels.
- [ ] Desktop "Group Companies" dropdown opens on hover/focus and
      closes on outside hover.
- [ ] Mobile hamburger drawer opens, locks body scroll, closes on
      backdrop click / Escape / route change / X button.
- [ ] Submenus inside the mobile drawer expand/collapse.
- [ ] Theme toggle switches between light and dark and persists
      across reloads.
- [ ] Search button opens a search input bar and the X icon closes it.
- [ ] Floating "Ask PUG AI" launcher is pinned bottom-right and the
      modal opens / closes correctly (backdrop click, Escape, X).
- [ ] Skip-to-content link appears on first Tab press and jumps past
      the navbar.
- [ ] Footer renders 4 columns on desktop and stacks on mobile.
- [ ] All public stub pages (/about, /companies, /news, /careers,
      /contact, /media) load and show the per-page "Coming soon" card.
- [ ] Admin (`/admin`) and HR (`/hr`) pages still work end-to-end
      from Phase 2.

## Phase 19 — Security and validation (planned)

- [ ] Input validation rejects malformed payloads.
- [ ] File uploads enforce allowed types and size limits.
- [ ] Permission tests for both admin surfaces pass.
- [ ] Public AI cannot expose private candidate data.
- [ ] HR AI cannot select/reject candidates automatically.
- [ ] Audit log covers every sensitive action.
- [ ] Bearer token storage hardening (httpOnly cookies + CSRF).

> Phases 4–18 add their own sections to this file as they ship.
