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
