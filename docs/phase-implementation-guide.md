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

## Phase 3 deliverables

Public layout shell (`app/(public)/layout.tsx`):

- Sticky transparent navbar (`components/site/navbar.tsx`) – becomes
  glass with backdrop-blur on scroll.
- Desktop dropdown menu (hover/focus) for Group Companies.
- Mobile hamburger drawer (`components/site/mobile-menu.tsx`) – slide-in
  from the right, body scroll lock, escape to close, route change
  auto-close, expandable submenus.
- Light/dark theme toggle (`components/site/theme-toggle.tsx`) backed
  by `next-themes` (already wired in Phase 1's root layout).
- Search button + collapsible search bar (UI only – wires to backend
  in Phase 6).
- Footer with brand column, contact details, three link columns,
  social links.
- Floating "Ask PUG AI" launcher (`components/site/ask-pug-ai-button.tsx`)
  with placeholder modal – the actual Azure OpenAI chat lands in
  Phase 17.
- Skip-to-content link for keyboard users.

Reusable primitives:

- `GlassCard` – glassmorphism card with Framer Motion fade-in on scroll.
- `Section` – page section wrapper with eyebrow / title / description.
- `ComingSoon` – shared placeholder used by every Phase 4 route.
- Stronger global CSS safety net (images cap to 100% width, body locks
  horizontal scroll, `.bg-decor` utility for soft coloured background
  blobs, `.break-anywhere` for long URLs/IDs).

Route shells (all rendered through the public layout):

- `/` – Phase 3 shell preview (hero, capabilities, live backend health
  card, roadmap).
- `/about`, `/companies`, `/news`, `/careers`, `/contact`, `/media` –
  shared `ComingSoon` stub with the per-page feature list. Real
  content lands in Phase 4.

## Definition of done for any phase

- Code lives on the agreed feature branch.
- Backend tests pass: `pytest -q`.
- Frontend type-check passes: `npm run type-check`.
- Frontend production build succeeds: `npm run build`.
- Documentation updated (this guide, setup guide, api reference,
  testing checklist).
- Summary message lists added files, migrations, run commands, and
  any open questions.
