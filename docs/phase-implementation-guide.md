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

## Phase 4 deliverables

Pages (all under `app/(public)/`):

- `/` – Home: auto-rotating hero slider with pause/play, animated
  stats strip, sector cards, featured company grid, leadership
  preview, latest news, careers highlight, contact CTA, newsletter.
- `/about` – company intro, vision, mission, core values, history
  timeline, full leadership messages.
- `/companies` – category-filtered listing (All / Distribution /
  Retail / Services) using URL query (`?category=...`).
- `/companies/[slug]` – 14 generated detail pages with logo, banner
  accent, long description, services, gallery placeholders, contact
  panel, related companies.
- `/news` – featured strip + latest grid.
- `/news/[slug]` – 6 generated article pages with cover, body, gallery,
  share buttons (UI), related stories.
- `/careers` – client-side filtered listing (search, department,
  company, location, employment type, reset).
- `/careers/[slug]` – 8 generated job pages with responsibilities,
  requirements, required + preferred skills, quick facts, **Apply Now
  form** (UI only — Phase 10 wires it to the HR ATS).
- `/contact` – contact form with department routing, contact details,
  WhatsApp / phone quick actions, map placeholder.
- `/media` – category-filtered gallery with lightbox.

Data layer (`lib/dummy-data/`):

- `companies.ts` – 14 companies (5 distribution, 4 retail, 5 services)
  matching the master prompt.
- `news.ts` – 6 articles + helpers.
- `jobs.ts` – 8 open job openings + filters.
- `leadership.ts` – Chairman, MD, two Executive Directors.
- `site-content.ts` – hero slides, stats, sectors, vision/mission/
  values, history timeline.
- `media.ts` – 12 media tiles across stores / events / team / campaigns.

> Phase 6 will replace each `getX()` helper with an API call without
> changing any consumer component.

New shadcn primitives:

- `Badge` (8 variants: default, secondary, destructive, outline,
  soft, muted, success, warning).
- `Textarea`.
- `Select` (lightweight native wrapper).

New site components (`components/site/`):

- `hero-slider.tsx`, `stats-strip.tsx`, `sector-cards.tsx`,
  `company-card.tsx`, `leadership-card.tsx`, `news-card.tsx`,
  `job-card.tsx`, `timeline.tsx`, `media-gallery.tsx`,
  `page-hero.tsx`, `contact-form.tsx`, `apply-form.tsx`,
  `newsletter-form.tsx`, `job-filters.tsx`.

Form behaviour:

- Newsletter, contact, and apply-now forms validate on the client and
  show a success state with a "Phase 6/10 will wire this to the
  backend" note. Phase 6 and Phase 10 swap in real submission.

## Definition of done for any phase

- Code lives on the agreed feature branch.
- Backend tests pass: `pytest -q`.
- Frontend type-check passes: `npm run type-check`.
- Frontend production build succeeds: `npm run build`.
- Documentation updated (this guide, setup guide, api reference,
  testing checklist).
- Summary message lists added files, migrations, run commands, and
  any open questions.
