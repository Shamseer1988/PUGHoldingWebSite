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
| 6     | Public website backend API integration           | **Done**    |
| 7     | HR ATS database and core models                  | **Done**    |
| 8     | HR ATS admin dashboard                           | **Done**    |
| 9     | Job opening management                           | **Done**    |
| 10    | Candidate application and CV upload              | **Done**    |
| 11    | CV parsing and data extraction                   | **Done**    |
| 12    | Candidate scoring engine                         | **Done**    |
| 13    | HR AI candidate review                           | **Done**    |
| 14    | Candidate workflow pipeline                      | **Done**    |
| 15    | Interview management                             | **Done**    |
| 16    | HR advanced search, filters, reports, export     | **Done**    |
| 17    | Public AI assistant                              | **Done**    |
| 18    | Responsive UI polish and mobile testing          | Partial     |
| 19    | Security, audit, validation, and testing         | Partial     |
| 20    | Deployment documentation and final package       | In progress |

### Phase 18 — outstanding gaps
- Responsive Tailwind classes are applied throughout, but there is no
  formal mobile test pass at 360 / 390 / 430 / 768 / 1024 / 1440
  breakpoints, and no documented device-compatibility matrix.

### Phase 19 — outstanding gaps
- 306 backend tests across 27 files; audit logging on every HR write;
  soft deletes on candidates and applications; Pydantic validation on
  every endpoint; AI safety guards covered by tests.
- **No rate limiting** on public endpoints
  (`/contact`, `/candidate-applications`, `/ai-assistant/ask`).
- No explicit XSS / CSRF / SQL-injection test cases.
- No admin viewer for the `public_ai_queries` usage log.
- No documented privacy / data-retention policy.

### Phase 20 — in progress
- `docs/deployment-guide.md` was a placeholder until this iteration.
- AWS Ubuntu install guide, PostgreSQL hardening + backup, Nginx
  reverse proxy, systemd units for uvicorn (with gunicorn workers)
  and Next.js, Cloudflare DNS / SSL, log rotation, monitoring, and
  the troubleshooting runbook are being added in this phase.

## Phase 8 deliverables

**Backend (dashboard + audit endpoints)**

- `GET /api/v1/hr/dashboard` — aggregated read-only summary:
  - **13 KPI cards**: open jobs, total candidates, applications (total
    + this month), AI reviewed, AI recommended, HR review pending,
    shortlisted, rejected, selected, joined, pending interviews,
    pending offers.
  - **Pipeline funnel**: canonical 10-stage funnel (`cv_received` →
    `joined`) returned even when empty so the UI renders the shape.
  - **Applications-per-month** trend (Python-side bucketing so SQLite
    and Postgres share one code path).
  - **Candidates by job** (top 10) + **by department** (top 10) rollups.
  - **Pending interviews** (next 10 scheduled, joined to candidate +
    job + interviewer) and **pending offers** (draft/sent, joined to
    candidate + job).
- `GET /api/v1/hr/audit-logs` — HR-scoped slice of the shared
  `audit_logs` table with `action_prefix` filter.
- Both routes mounted behind `require_hr_admin` — a website-admin
  token is rejected with 403.
- **5 new tests (58 total)** — scope guard, empty-state aggregations,
  seeded-data aggregations, interview filtering (excludes past +
  cancelled), unauthenticated rejection.

**Frontend (HR shell + dashboard + stubs)**

- New shell components (`components/hr/`):
  - `HrShell` mirrors `AdminShell` but routes through `AuthGuard`
    against the **hr** scope (separate localStorage slot from admin).
  - `HrSidebar` with HR-branded "HR" pill on the logo, 4 nav groups
    (Overview / Recruitment / Insights / System), and "Soon" badges
    on modules deferred to later phases.
  - `HrTopbar` + `HrEmptyState` helpers.
- New typed client + types: `lib/hr/api.ts`, `lib/hr/types.ts`.
- **`/hr` dashboard** — 13 KPI cards in a responsive grid, the pipeline
  funnel (custom bar list), the monthly-trend area chart (Recharts),
  pending interviews + pending offers tables with empty-state cards,
  and two "applications by job / department" bar lists. All
  brand-coloured (`pug-green-*` + `pug-gold-*`).
- **`/hr/audit`** — HR-scoped audit log viewer with action-prefix
  filter.
- Stub pages with `HrEmptyState` cards for `/hr/jobs`, `/hr/candidates`,
  `/hr/interviews`, `/hr/offers`, `/hr/reports`, `/hr/users` — each
  explicitly labels which phase fills it in.

The dashboard correctly shows empty / zero values today because
candidates and interviews don't exist yet — they land in Phase 10 and
Phase 15.

## Phase 7 deliverables

14 new SQLAlchemy models covering every HR ATS table called out in the
master prompt — and the Alembic migration that creates them.

**Tables (all `hr_*`)**

- `hr_job_openings` — job postings (slug, title, department, division,
  company, location, employment_type, experience range, salary range,
  visa / nationality / language / notice preferences, description,
  responsibilities, requirements, required_skills, preferred_skills,
  status, posted_at, closed_at, created_by_id).
- `hr_candidates` — master candidate record (name, email, mobile,
  nationality, current location / designation / company, experience
  totals incl. GCC + Qatar, expected_salary, notice_period, visa_status,
  availability, blacklist + archive flags, source).
- `hr_candidate_documents` — CV files (filename, path, mime_type, size,
  sha256 hash for dedup, is_primary, uploaded_by).
- `hr_candidate_extracted_data` — 1:1 with candidate; skills, education
  (JSON), certifications (JSON), languages (JSON), previous_companies
  (JSON), full_text, parser_version.
- `hr_candidate_tags` — many tags per candidate, unique within candidate.
- `hr_candidate_notes` — free-form HR notes.
- `hr_candidate_job_applications` — the link table carrying pipeline
  state (status, applied_at, source, cover_letter,
  last_rejection_reason). Unique on (candidate_id, job_opening_id).
- `hr_candidate_scores` — 1:1 with application; total /100, manual
  override fields.
- `hr_candidate_score_breakdowns` — 1:1 with score; one column per
  weighted component (relevant_experience /25, required_skills /20,
  education /10, industry_experience /10, gcc_qatar_experience /10,
  salary_fit /10, notice_period /5, visa_status /5, language_match /5),
  plus a JSON `notes` map for per-component explanations.
- `hr_candidate_ai_reviews` — 1:1 with application; summary, strengths,
  weaknesses, missing_information, risk_points, suggested_questions,
  recommendation, model_name, token counts, raw_response JSON,
  generated_at.
- `hr_candidate_status_history` — pipeline state-change audit
  (old_status, new_status, changed_by, remarks, rejection_reason,
  blacklist_approval, created_at).
- `hr_interviews` — round_name, round_number, scheduled_at, duration,
  mode, location_or_link, interviewer_id, status, created_by_id.
- `hr_interview_feedback` — rating, recommendation, free-form feedback,
  per-axis sub-scores (technical, communication, cultural fit).
- `hr_offer_tracking` — 1:1 with application; salary_offered,
  joining_date, benefits_summary, status, sent_at, responded_at,
  decline_reason.

**Constants**

Status / mode strings exposed as Python constants in `app.models.hr_ats`
so every later phase shares the same vocabulary
(`STATUS_*`, `JOB_STATUS_*`, `INTERVIEW_*`, `OFFER_*`, `AI_*`,
`SCORE_WEIGHTS`). `SCORE_WEIGHTS` totals 100 (asserted at import time).

**Cross-cutting**

The existing `audit_logs` table (Phase 2) is reused for HR-scoped audit
entries — every HR write action will populate it with `scope='hr'`
and rich `details` JSON. No separate `hr_audit_logs` table.

**Migration**

`20260524_0001_phase7_hr_ats_tables` creates all 14 tables in dependency
order, with FK constraints, the (candidate_id, job_opening_id) unique
constraint, the (candidate_id, tag) unique constraint, and indexes on
every column later phases will filter on (status, scheduled_at, slug,
email, mobile, file_hash, etc.).

**Seed**

`python -m app.scripts.seed_hr` upserts the eight job openings the
Phase 4 careers page already shows on the public site. Phase 9 will
swap the public careers page to read from this table.

**Tests (12 new, 53 total)**

- `SCORE_WEIGHTS` sums to 100.
- Job opening round-trip + slug uniqueness.
- Candidate with documents, extracted_data, tags, notes round-trip.
- Cascade delete on candidate removes children.
- (candidate_id, tag) unique constraint.
- Application unique on (candidate_id, job_opening_id).
- Score + breakdown + AI review round-trip.
- Status history insertion.
- Interview + feedback round-trip.
- Offer round-trip + uniqueness per application.

## Phase 6 deliverables

**Backend (new public router).** A 10-endpoint unauthenticated router
at `/api/v1/public/*`:

- `GET  /public/hero-slides`           active only, ordered.
- `GET  /public/companies`             active only, optional `?category=`.
- `GET  /public/companies/{slug}`      active only, 404 for hidden.
- `GET  /public/leadership`            active only, ordered.
- `GET  /public/news`                  published only, optional `?featured=` and `?limit=`.
- `GET  /public/news/{slug}`           published only, 404 for drafts.
- `GET  /public/site-settings`         falls back to defaults if not configured.
- `POST /public/contact`               persists to `contact_messages`, audit-logged.
- `POST /public/newsletter`            idempotent subscribe (re-activates inactive emails).

13 new integration tests (41 total) covering active/published filters,
404 behaviour, featured filter, idempotent newsletter, email validation.

**Frontend (everything swapped from dummy data to API).**

- `lib/public-api.ts` — typed server-side fetch helpers with 60-second
  revalidation, graceful fallbacks (returns `null` / `[]` instead of
  crashing if the backend is unreachable).
- `lib/public-api-client.ts` — client-side helpers for newsletter and
  contact submissions with typed errors.
- All public pages now use `async` Server Components fetching from
  `/api/v1/public/*`:
  - Home: hero slides, featured companies, leadership preview, latest
    news, contact phone/whatsapp from site settings.
  - About: leadership messages.
  - Companies list: filtered/grouped from API.
  - Company detail: 404 for hidden/missing, related companies from API.
  - News list: featured strip + others from API.
  - News detail: 404 for drafts, related news from API.
  - Contact: contact rows, phone, WhatsApp from site settings.
  - Public layout: site settings flow down to the footer (tagline,
    contact, dynamic social links).
- Newsletter form: POSTs to `/public/newsletter` with error surface.
- Contact form: POSTs to `/public/contact` with error surface.
- `generateMetadata` on company + news detail pages pulls title and
  description from the actual record.

**Cleanup:**

- Removed `lib/dummy-data/companies.ts`, `news.ts`, `leadership.ts`
  (no longer used).
- Trimmed `lib/dummy-data/site-content.ts` to only the bits that
  still come from config (stats, sectors, vision/mission/values,
  timeline). A Phase 5 follow-up CMS module can move those too.
- Card components (`CompanyCard`, `NewsCard`, `LeadershipCard`,
  `HeroSlider`) updated to use the API schema (snake_case fields,
  `services: {id, name}[]`, etc.).

**Still on dummy data (intentional):**

- Careers list + job detail (`lib/dummy-data/jobs.ts`) — wires to
  the HR ATS in Phase 9.
- Media gallery (`lib/dummy-data/media.ts`) — needs the media CMS
  module + file upload, deferred Phase 5 follow-up.
- Apply Now form — wires to ATS candidate intake in Phase 10.

## Definition of done for any phase

- Code lives on the agreed feature branch.
- Backend tests pass: `pytest -q`.
- Frontend type-check passes: `npm run type-check`.
- Frontend production build succeeds: `npm run build`.
- Documentation updated.
- Summary message lists added files, migrations, run commands, and
  any open questions.
