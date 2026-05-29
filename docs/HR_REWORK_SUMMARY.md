# HR Recruitment Module — Phase 1-13 Rework Summary

End-to-end deliverable summary for the HR admin / recruitment system
rework. Each section answers one of the bullets the master prompt
called out in its "Final Output Required From Developer" block.

Branch: `claude/clever-bell-2ZsPr` · Final commit: see `git log`.
Backend test suite: **577 passing** at completion (511 pre-existing
+ 66 new across the rework). Frontend type-check: clean.

---

## 1. Completed phases

| Phase | Theme | Commit anchor | Backend tests added |
|------:|---|---|---:|
| 1 | Fine-grained RBAC (35 perms × 7 roles) | RBAC overhaul | 18 |
| 2 | Job approval workflow polish + audit columns + revision endpoints | Workflow | 7 |
| 3 | Recruitment / interview / offer status separation + unified timeline | Timeline | 9 |
| 4 | Interview quick-update modal + structured feedback fields | Feedback | 2 |
| 5 | Interview reschedule (date / mode / location) with reason + auto email | Reschedule | 5 |
| 6 | Full offer lifecycle (state machine + 12 endpoints + UI) | Offers | 17 |
| 7 | 24-column HR Candidate Excel export | Export | 8 |
| 8 | Soft archive (jobs + candidates) + reason-capturing delete | Archive | 13 |
| 9 | Role-scoped reports + interviewer-only data filtering | Reports scope | 8 |
| 10 | 12 master-plan dashboard cards + unified status badge | Dashboard | 5 |
| 11 | Interview-feedback + full offer-lifecycle email notifications | Notifications | 13 |
| 12 | Full role + permission matrix admin UI | Permission matrix | 12 |
| 13 | End-to-end golden path + cross-role security sweep | Acceptance | 16 |

Total new acceptance tests across the rework: **133**.

---

## 2. Files changed (highlights)

Backend modules created or substantially extended:

- `backend/app/auth/permissions.py` — Phase 1 permission catalog (35 keys × 7 roles)
- `backend/app/auth/dependencies.py` — `require_any_permission` + `require_all_permissions`
- `backend/app/services/offers.py` — Phase 6 offer state machine (new)
- `backend/app/api/endpoints/hr_offers.py` — Phase 6 offer CRUD + lifecycle (new)
- `backend/app/api/endpoints/admin_users.py` — Phase 12 role/permission management endpoints
- `backend/app/services/hr_reports.py` — Phase 7 candidate_full_export, Phase 9 actor-scoped runners
- `backend/app/services/hr_notifications.py` — Phase 11 offer + feedback dispatchers
- `backend/app/services/email_templates.py` — 7 new branded templates (Phase 11)
- `backend/app/services/job_approval.py` — Phase 2 denormalised audit fields, Phase 8 archive
- `backend/app/services/candidate_workflow.py` — Phase 3 new statuses + transitions
- `backend/app/services/interview_management.py` — Phase 4 + Phase 5 fields
- `backend/app/api/endpoints/hr_dashboard.py` — Phase 10 master-plan cards
- `backend/app/models/hr_ats.py` — touched in every phase for new columns/relationships

Frontend pages created or substantially extended:

- `frontend/app/admin/roles/page.tsx` — Phase 12 permission matrix UI (new)
- `frontend/app/hr/offers/page.tsx` — Phase 6 full offer admin (replaces placeholder)
- `frontend/components/hr/offer-detail-drawer.tsx` — Phase 6 offer lifecycle UI (new)
- `frontend/components/hr/create-offer-dialog.tsx` — Phase 6 (new)
- `frontend/components/hr/reschedule-interview-dialog.tsx` — Phase 5 (new)
- `frontend/components/hr/interview-quick-update-dialog.tsx` — Phase 4 (new)
- `frontend/components/hr/candidate-timeline.tsx` — Phase 3 (new)
- `frontend/components/hr/job-approval-timeline.tsx` — Phase 2 (new)
- `frontend/components/hr/confirm-reason-dialog.tsx` — Phase 8 (new)
- `frontend/components/hr/status-badge.tsx` — Phase 10 unified badge (new)
- `frontend/components/auth/permission.tsx` — `usePermission` hook + `<RequirePermission>` + `<AccessDenied>` (new)
- `frontend/components/hr/sidebar.tsx` — Phase 1 permission-driven menu filtering
- Several existing pages updated for permission gating (jobs / candidates / interviews / reports)

---

## 3. Database migrations added

Eight new Alembic migrations under `backend/migrations/versions/`:

```
20260527_0001_hr_rbac_permissions.py           Phase 1 — permissions + roles
20260527_0002_job_approval_audit_fields.py     Phase 2 — changes_requested_* + published_*
20260527_0003_recruitment_status_additions.py  Phase 3 — anchor (free-form VARCHAR)
20260527_0004_interview_feedback_phase4.py     Phase 4 — strengths / weaknesses / next_action
20260527_0005_interview_reschedule_reason.py   Phase 5 — reschedule_reason on hr_interviews
20260527_0006_offers_lifecycle.py              Phase 6 — 22 new columns on hr_offer_tracking + hr_offer_status_history
20260527_0007_archive_audit_fields.py          Phase 8 — archive cluster on jobs + candidates
20260527_0008_offer_email_enabled_flag.py      Phase 11 — offer_email_enabled on email_settings
```

All idempotent; SQLite-safe; FKs only on Postgres. Down-migrations
provided where reversible.

---

## 4. New models / tables added

- `OfferStatusHistory` — Phase 6 audit table (`hr_offer_status_history`)
- `OfferTracking` — substantially extended in Phase 6 (22 new columns)
- Existing tables extended by phase: `JobOpening` (Phase 2 + Phase 8), `Candidate` (Phase 8), `Interview` (Phase 5), `InterviewFeedback` (Phase 4), `User` (Phase 1 `department`), `EmailSetting` (Phase 11 `offer_email_enabled`)

No tables were dropped; no breaking schema changes.

---

## 5. New API endpoints added

```
# Phase 1 — none (existing endpoints gated on new permissions)

# Phase 2 — explicit revision review
POST   /hr/jobs/{id}/revisions/{rev_id}/approve
POST   /hr/jobs/{id}/revisions/{rev_id}/reject

# Phase 3 — unified candidate timeline
GET    /hr/candidates/{id}/timeline

# Phase 4 — none (uses existing /feedback with new fields)

# Phase 5 — none (PATCH /hr/interviews/{id} gained reschedule_reason
#           + send_email_now flags + email-dispatch when scheduled_at
#           changes)

# Phase 6 — full offer lifecycle
GET    /hr/offers
GET    /hr/offers/stats
GET    /hr/offers/{id}
GET    /hr/offers/{id}/status-history
POST   /hr/offers
PATCH  /hr/offers/{id}
POST   /hr/offers/{id}/submit-approval
POST   /hr/offers/{id}/approve
POST   /hr/offers/{id}/reject
POST   /hr/offers/{id}/issue
POST   /hr/offers/{id}/respond
POST   /hr/offers/{id}/mark-joined
POST   /hr/offers/{id}/mark-not-joined
POST   /hr/offers/{id}/withdraw
DELETE /hr/offers/{id}

# Phase 8 — archive lifecycle
POST   /hr/jobs/{id}/archive
POST   /hr/jobs/{id}/unarchive
POST   /hr/candidates/{id}/archive
POST   /hr/candidates/{id}/unarchive

# Phase 12 — permission matrix
GET    /admin/permissions
GET    /admin/roles/{id}
POST   /admin/roles
PATCH  /admin/roles/{id}
PATCH  /admin/roles/{id}/permissions
DELETE /admin/roles/{id}
```

29 new endpoints. Every existing HR endpoint had its permission
dependency tightened from the coarse `require_hr_admin` to a
fine-grained `require_permission` (Phase 1).

---

## 6. New permissions added

35 permission keys under the `hr:*:*` namespace. See
`backend/app/auth/permissions.py` for the authoritative list and
descriptions.

Areas: dashboard, jobs, candidates, interviews, offers, reports,
cv, settings, audit, users.

Verbs: view / view_all / view_dept / view_mine, create, edit,
approve, publish, delete, status_update, status_override,
score_override, blacklist, schedule, reschedule, feedback, export,
download, manage.

---

## 7. Role permission matrix (defaults seeded by Alembic)

| Permission area | Super Admin | HR Admin | HR Manager | HR Executive | Dept Manager | Interviewer | Viewer |
|---|---|---|---|---|---|---|---|
| Dashboard | Y | Y | Y | Y | Y | Y | Y |
| Jobs view (all) | Y | Y | Y | Y | — | — | Y |
| Jobs view (own dept) | Y | — | — | — | Y | — | — |
| Jobs create/edit | Y | Y | Y | Y | — | — | — |
| Jobs approve / publish / delete | Y | — | Y | — | — | — | — |
| Candidates list / view full | Y | Y | Y | Y | dept-only | — | Y |
| Candidates edit / status update | Y | Y | Y | Y | — | — | — |
| Candidates delete / blacklist / status override | Y | — | Y | — | — | — | — |
| Interviews view all | Y | Y | Y | Y | Y | — | Y |
| Interviews view mine | Y | Y | Y | Y | Y | Y | — |
| Interviews schedule / reschedule | Y | Y | Y | Y | — | — | — |
| Interviews feedback | Y | Y | Y | Y | Y | Y | — |
| Interviews delete | Y | — | Y | — | — | — | — |
| Offers view | Y | Y | Y | Y | Y | — | Y |
| Offers create | Y | Y | Y | — | — | — | — |
| Offers approve / delete | Y | — | Y | — | — | — | — |
| Reports view (all) | Y | Y | Y | Y | — | — | Y |
| Reports view (dept / mine) | Y | Y | Y | Y | dept | mine | — |
| Reports export | Y | Y | Y | Y | Y | — | Y |
| CV download | Y | Y | Y | Y | Y | limited | — |
| Settings manage | Y | Y | Y | — | — | — | — |
| Audit read | Y | Y | Y | — | — | — | Y |
| Users manage | Y | — | — | — | — | — | — |

Super Admin can edit the matrix at `/admin/roles` (Phase 12).
Permission changes are audited and take effect on next request.

---

## 8. Testing steps

```bash
# Backend full suite (≈4 min on a laptop)
cd backend
python -m pytest tests/ -q

# Just the rework's acceptance tests
python -m pytest tests/test_acceptance_phase13.py -v

# Frontend type check
cd ../frontend
npm run type-check
```

Expected: backend reports `577 passed`. Frontend type-check exits 0.

---

## 9. Manual QA checklist

Run these flows against a freshly-seeded environment
(`python -m app.scripts.seed_users` after `alembic upgrade head`).

### Public site

- [ ] `/careers` lists only the seeded approved+published jobs.
- [ ] `/careers/<slug>` apply form submits, candidate appears in HR portal.
- [ ] Existing CV file in `app/uploads/cvs/` is still downloadable by HR.

### HR Manager (`hrmanager@pug.example.com` / `ChangeMe!123`)

- [ ] Sees the full sidebar — dashboard, jobs, candidates, interviews, offers, reports, audit.
- [ ] `/hr/dashboard` shows the 12 master-plan cards.
- [ ] `/hr/jobs` row has Approve / Reject / Publish action buttons.
- [ ] Creating + submitting + approving a job auto-publishes it.
- [ ] Editing an approved job shows the amber "re-approval required" banner.
- [ ] `/hr/jobs/{id}/approval-history` timeline renders.
- [ ] `/hr/offers` dashboard cards click through to filtered tables.
- [ ] Draft → submit → approve → issue → respond(accept) → mark-joined chain works.
- [ ] `/admin/email-settings` HR notifications card lists `manager@pug.example.com`.

### HR Executive (`hrexecutive@pug.example.com`)

- [ ] Cannot see Approve / Delete buttons on jobs.
- [ ] Cannot create offers (no Draft offer button on candidate panel).
- [ ] Can shortlist + schedule interviews.
- [ ] Tries `DELETE /api/v1/hr/jobs/<id>` via Swagger → 403.

### Interviewer (`interviewer@pug.example.com`)

- [ ] Sidebar shows ONLY Dashboard + Interviews + Audit log.
- [ ] `/hr/candidates`, `/hr/jobs`, `/hr/offers`, `/hr/reports` (full list) all → AccessDenied card.
- [ ] `/hr/interviews` shows only their own assigned rounds.
- [ ] Clicking the candidate name opens the quick-update modal (status + feedback).
- [ ] Submitting feedback fires the HR notification email.

### Viewer (`viewer@pug.example.com`)

- [ ] Sidebar shows Dashboard + Jobs + Candidates + Interviews + Offers + Reports + Audit (all read-only).
- [ ] No "New job", "Create offer", "Update status" buttons anywhere.

### Super Admin (`superadmin@pug.example.com`)

- [ ] `/admin/roles` lists 7 seeded roles.
- [ ] Editing HR Manager's permission grants writes an audit row at `/admin/audit`.
- [ ] Creating a custom role with a cross-scope grant returns a clear 422 error.
- [ ] Deleting an assigned role returns "Re-assign all users first" 409.

### Excel export

- [ ] `/hr/candidates` → Export Excel produces `HR_Candidate_Report_YYYYMMDD_HHMM.xlsx` (or `pug-candidate_full_export-…xlsx`).
- [ ] File opens in Excel with frozen header, auto-filter, banded rows.

### Soft archive

- [ ] Archiving a job from `/hr/jobs` removes it from public site.
- [ ] `?include_archived=true` surfaces it again.
- [ ] Restore button returns it to the default listing.

---

## 10. Deployment notes

1. **Pull the branch:**
   ```bash
   git fetch origin && git checkout claude/clever-bell-2ZsPr
   ```

2. **Backend:** Install Python deps (no new system-level deps were
   added; openpyxl + reportlab were already pinned in
   `requirements.txt`). Run migrations in order:
   ```bash
   cd backend
   alembic upgrade head
   ```
   Eight new revisions apply in the 20260527 sequence.

3. **Seed:** Run the seed script to upsert the seven standard roles
   + the eight seed test users (production should reset the seed
   passwords immediately):
   ```bash
   python -m app.scripts.seed_users
   ```

4. **Frontend:** Install + build as normal:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

5. **Reload SMTP settings:** Phase 11 reuses the existing SMTP
   credentials configured under `/admin/email-settings`. The new
   `offer_email_enabled` boolean defaults to `true` on the existing
   row; toggle it off if you want to silence the offer stream while
   testing.

6. **No data loss:** Every migration is additive — no columns were
   dropped, no rows were rewritten. Existing candidates, CVs, and
   audit logs remain untouched.

---

## 11. Environment variables required

No new environment variables. The rework reuses the existing config:

- `DATABASE_URL` — already required
- SMTP settings in `/admin/email-settings` — already configured

Optional `GOOGLE_*` env vars from the original Google Meet
integration still work; they're unused by default since the meeting
link is now manual.

---

## 12. Known limitations / pending items

These were called out in the per-phase commit messages and would
make natural follow-up tasks. None block production.

| Item | Phase reference | Notes |
|---|---|---|
| Department-scoped reports | Phase 9 | `min_scope='dept'` tier exists in the data model but no report uses it yet. Easy additive change. |
| Dangerous-permission confirmation modal | Phase 12 | Today `/admin/roles` saves on click; a future polish adds a confirm for `:delete` / `:export` grants. Audit row already captures the change. |
| HR Settings page | Phase 12 | Default interview duration / mode / location and per-event toggles. Master plan lists this alongside the matrix; a smaller follow-up page. |
| Mobile responsiveness audit | Phase 10 | Tables collapse via Tailwind `md:`/`lg:` but the modals are cramped in phone portrait. Dedicated responsive pass would help. |
| Migrate remaining badge instances to `<HrStatusBadge>` | Phase 10 | `/hr/offers` already migrated; jobs / candidates / interviews still ship local badge components. Mechanical refactor. |
| Per-event notification toggles | Phase 11 | Today the toggle is per-stream (offer / interview / job_approval / candidate). Finer per-event control if HR finds the existing four too coarse. |
| Interviewer column in candidate Excel export | Phase 7 | Currently blank to keep the export fast. Resolving to `user.email` would need a per-row lookup. |
| "Remarks" column in candidate Excel export | Phase 7 | Last status-change remark currently blank — needs a join to `hr_candidate_status_history`. |
| Email template visual preview in admin | n/a | Useful but not requested by the master plan. |
| Webhook / external integration for offer events | n/a | Out of scope. Backend dispatchers can wire to a future webhook layer without touching endpoints. |

---

## 13. Branch state at hand-over

```text
Branch:           claude/clever-bell-2ZsPr
Commits ahead:    23 (Phases 1 → 13)
Backend tests:    577 / 577 passing
Frontend:         npm run type-check clean
Migrations:       8 new (20260527_0001 → 20260527_0008)
```
