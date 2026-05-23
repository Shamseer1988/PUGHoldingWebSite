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
| 2     | Authentication, roles, separate logins           | Planned     |
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

## Phase 1 deliverables (this commit)

- Monorepo with `/backend`, `/frontend`, `/docs`.
- Backend: FastAPI app factory, Pydantic v2 settings, SQLAlchemy 2 engine
  and base class, Alembic config, health-check endpoint, smoke tests,
  `requirements.txt`, `.env.example`, `run.py`.
- Frontend: Next.js 14 App Router with TypeScript, Tailwind, shadcn
  conventions (`components.json`, CSS variables), Framer Motion,
  Lucide, theme provider, Phase 1 landing splash that pings the
  backend health endpoint, placeholders for `/admin` and `/hr`.
- Documentation set under `/docs`.

## Definition of done for any phase

- Code lives on the agreed feature branch.
- Backend tests pass: `pytest -q`.
- Frontend type-check passes: `npm run type-check`.
- Frontend production build succeeds: `npm run build`.
- Documentation updated (this guide, setup guide, api reference,
  testing checklist).
- Summary message lists added files, migrations, run commands, and
  any open questions.
