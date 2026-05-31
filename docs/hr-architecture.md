# HR Admin — Information Architecture, State Machine & Badge Taxonomy

This document is the source of truth for how the HR recruitment console is
organised so future contributors don't have to reverse-engineer it. It
covers three things:

1. The **navigation / page tree** (IA).
2. The **application + offer state machines**.
3. The **status badge taxonomy** rendered by the shared `<StatusBadge>`.

All `/hr/*` pages are English-only client components (the locale provider is
intentionally not applied — see `CLAUDE.md`). Status pills everywhere under
`/hr/*` render through the single `components/hr/status-badge.tsx`
component; `StatusChip` and `HrStatusBadge` were removed.

---

## 1. Information architecture (page tree)

```
/hr
├── (Dashboard)                     app/hr/page.tsx
│     • Clickable KPI cards (<KpiCard href>) → pre-filtered lists
│     • "Needs attention today" rail (interviews today, offers awaiting
│       approval, candidates awaiting HR review)
│     • Funnel + monthly trend + group-by tables
│     • Powered by GET /hr/dashboard + GET /hr/dashboard/stage-counts
├── /pipeline                       app/hr/pipeline/page.tsx
│     • Kanban: Sourced · Screening · Interview · Selected · Offer · Joined
│     • Drag (framer-motion) or "Move…" → status-transition endpoint
├── /candidates                     app/hr/candidates/page.tsx
│     • Table + full-taxonomy status filter chips
│     • Inline row actions (see §below) + 360° drawer
│     • URL-synced shared filters (?status=…&job=…&department=…)
├── /jobs                           app/hr/jobs
├── /interviews                     app/hr/interviews
├── /assessments                    app/hr/assessments/page.tsx (templates)
│     └── /assessments/submissions  app/hr/assessments/submissions/page.tsx
│           • Cross-template list (template, job, status, date, score range)
│           • Row → submission review drawer
├── /offers                         app/hr/offers/page.tsx
│     • Table ⇄ Board segmented control (board mirrors the offer machine)
├── /onboarding                     app/hr/onboarding/page.tsx
│     • Accepted → joined / no-show, Mark Joined / Mark Not Joined
│     • KPI strip: awaiting join · joined this month · no-show rate (90d)
├── /reports                        app/hr/reports/page.tsx
│     • Shared filter taxonomy + "Open in Candidates / Offers" deep links
├── /analytics · /scheduled-reports · /talent-pool
└── /users · /scorecard-templates · /audit
```

### Candidate inline row actions

Rendered by `components/hr/candidate-row-actions.tsx`, reused on the
Candidates table and (icon) on Pipeline cards:

```
[ Update Status ▾ ] [ Schedule Interview ] [ Send Assessment ]
[ Issue Offer ] [ Open 360° ]
```

Enablement is derived from the current status (`candidateActionEnablement`):

| Action             | Enabled when                                              |
|--------------------|-----------------------------------------------------------|
| Update Status ▾    | `ALLOWED_TRANSITIONS[status]` is non-empty (lists those)  |
| Schedule Interview | status is non-final                                       |
| Send Assessment    | status is non-final                                       |
| Issue Offer        | status ∈ { `recommended_for_offer`, `selected` }          |
| Open 360°          | always                                                    |

### Candidate 360° drawer tabs

`components/hr/candidate-detail-drawer.tsx` — exactly five tabs:
**Overview** (profile + extracted CV + collapsible Scoring & AI Review) ·
**Workflow** (status transitions) · **Interviews** · **Assessments** ·
**Activity** (unified timeline).

---

## 2. Application state machine

Canonical source: `backend/app/services/candidate_workflow.py`
(`ALLOWED_TRANSITIONS`). Read as "from {row} you may move to {targets}".
`rejected` and `blacklisted` are reachable from every non-final state
(blacklist is superuser-only and needs an approval reason; rejection needs
a reason). `joined` / `not_joined` / `rejected` / `blacklisted` are final.

```
cv_received          → ai_reviewed, hr_review_pending, shortlisted
ai_reviewed          → hr_review_pending, shortlisted
hr_review_pending    → shortlisted, first_interview
shortlisted          → first_interview
first_interview      → technical_interview, final_interview, waiting_list,
                       recommended_for_offer, selected
technical_interview  → final_interview, waiting_list,
                       recommended_for_offer, selected
final_interview      → waiting_list, recommended_for_offer, selected
waiting_list         → recommended_for_offer, selected
recommended_for_offer→ selected
selected             → offer_sent
offer_sent           → joined, not_joined
joined | not_joined | rejected | blacklisted → (final)
```

### Pipeline lanes (kanban)

`components/hr/pipeline-board.tsx` maps statuses to six lanes. Dropping a
card sets the lane's **entry status** via the status endpoint; the backend
rejects illegal transitions. Side-lane statuses are omitted from the board.

| Lane      | Statuses                                              | Drop target          |
|-----------|-------------------------------------------------------|----------------------|
| Sourced   | cv_received, ai_reviewed                              | cv_received          |
| Screening | hr_review_pending, shortlisted                       | shortlisted          |
| Interview | first_interview, technical_interview, final_interview| first_interview      |
| Selected  | recommended_for_offer, selected                      | selected             |
| Offer     | offer_sent                                           | offer_sent           |
| Joined    | joined                                               | joined               |

Side lanes (not shown): `waiting_list`, `rejected`, `blacklisted`,
`not_joined`.

## Offer state machine

Canonical source: `OFFER_STATUSES` in `backend/app/models/hr_ats.py`,
enforced by `backend/app/services/offers.py`.

```
draft → pending_approval → approved → sent (issued) → accepted → joined
                                                              └→ not_joined
(declined / withdrawn are terminal side states)
```

Post-acceptance joining is tracked by `joining_status`
(`pending` → `joined` | `not_joined`), surfaced on `/hr/onboarding`.

---

## 3. Status badge taxonomy

`STATUS_TAXONOMY[kind][status] = { label, tone, className }` in
`components/hr/status-badge.tsx`. Tones express the funnel as a colour
journey: neutral → info (sky) → progress (indigo) → ready (violet) →
success (emerald); amber = needs attention, rose = lost.

### kind = `application`

| status                  | label                  | tone     |
|-------------------------|------------------------|----------|
| cv_received             | CV received            | neutral  |
| ai_reviewed             | AI reviewed            | info     |
| hr_review_pending       | HR review pending      | warning  |
| shortlisted             | Shortlisted            | info     |
| first_interview         | First interview        | progress |
| technical_interview     | Technical interview    | progress |
| final_interview         | Final interview        | progress |
| waiting_list            | Waiting list           | warning  |
| recommended_for_offer   | Recommended for offer  | ready    |
| selected                | Selected               | ready    |
| offer_sent              | Offer sent             | info     |
| joined                  | Joined                 | success  |
| not_joined              | Not joined             | danger   |
| rejected                | Rejected               | danger   |
| blacklisted             | Blacklisted            | danger   |

### kind = `offer`

| status           | label            | tone    |
|------------------|------------------|---------|
| draft            | Draft            | neutral |
| pending_approval | Pending approval | warning |
| approved         | Approved         | info    |
| sent             | Issued           | info    |
| accepted         | Accepted         | success |
| declined         | Declined         | danger  |
| withdrawn        | Withdrawn        | neutral |
| joined           | Joined           | success |
| not_joined       | Not joined       | danger  |

### kind = `interview`

| status      | label       | tone    |
|-------------|-------------|---------|
| scheduled   | Scheduled   | info    |
| completed   | Completed   | success |
| cancelled   | Cancelled   | danger  |
| rescheduled | Rescheduled | warning |
| no_show     | No-show     | warning |

### kind = `job`

| status  | label   | tone    |
|---------|---------|---------|
| open    | Open    | success |
| on_hold | On hold | warning |
| closed  | Closed  | neutral |

> Job **approval** + **publish** sub-states keep their dedicated
> `job-approval-badge.tsx` (a separate workflow), and are intentionally not
> part of `<StatusBadge>`'s four kinds.

---

## 4. Shared filter taxonomy

`hooks/use-hr-filters.ts` defines the dimensions shared by Candidates,
Offers, Onboarding and Reports — `status`, `job`, `department`, `company`,
`source`, `dateFrom`, `dateTo` — encoded to the query string
(`status`, `job`, `department`, `company`, `source`, `date_from`,
`date_to`). Deep links minted on one page (clickable dashboard KPIs,
report "Open in …" links) land on another with the same filters applied.
