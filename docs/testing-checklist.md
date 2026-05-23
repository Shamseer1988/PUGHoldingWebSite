# Testing Checklist

A living checklist that grows with every phase. Tick items as their
phase ships.

## Phase 1 — Project foundation

- [x] Backend installs cleanly (`pip install -r requirements.txt`).
- [x] Backend smoke tests pass (`pytest -q`).
- [x] FastAPI imports without error and exposes
      `/`, `/docs`, `/api/v1/health`, `/api/v1/health/live`.
- [x] Frontend installs cleanly (`npm install`).
- [x] Frontend type-check passes (`npm run type-check`).
- [x] Frontend production build succeeds (`npm run build`).
- [x] Routes rendered by build: `/`, `/admin`, `/hr`, `/api/health`.
- [x] Landing splash includes a backend health card.
- [ ] Manual: visit `http://localhost:3000` with the backend running
      and confirm the health card shows `connected`.

## Phase 2 — Auth + separate logins (planned)

- [ ] Seed users created (Super Admin, Website Admin, HR Manager,
      HR Executive, Interviewer).
- [ ] `/admin/login` and `/hr/login` reject invalid credentials.
- [ ] HR user cannot reach `/admin/*` API surface.
- [ ] Website admin cannot reach `/hr/*` API surface.
- [ ] Login/logout entries appear in the audit log.

## Phase 3 — Public UI foundation (planned)

- [ ] No horizontal overflow at 360px, 390px, 430px, 768px,
      1024px, 1440px.
- [ ] Theme toggle persists across reloads.
- [ ] Hamburger menu opens/closes on mobile.
- [ ] Floating Ask PUG AI placeholder visible.

## Phase 19 — Security and validation (planned)

- [ ] Input validation rejects malformed payloads.
- [ ] File uploads enforce allowed types and size limits.
- [ ] Permission tests for both admin surfaces pass.
- [ ] Public AI cannot expose private candidate data.
- [ ] HR AI cannot select/reject candidates automatically.
- [ ] Audit log covers every sensitive action.

> Phases 4-18 add their own sections to this file as they ship.
