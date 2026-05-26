# PUG HR — Operational Guide

End-to-end workflow guide for the advanced HR ATS module: who does what,
when each email fires, and how to enable the optional Microsoft Teams
integration. Companion document to
[`HR_ADVANCED_MODULE_CLAUDE_PROMPT.txt`](./HR_ADVANCED_MODULE_CLAUDE_PROMPT.txt)
(the build spec).

---

## Table of contents

1. [Roles](#roles)
2. [Job lifecycle](#job-lifecycle)
3. [Candidate lifecycle](#candidate-lifecycle)
4. [Auto-review rule setup](#auto-review-rule-setup-per-job)
5. [Interview workflow](#interview-workflow)
6. [Microsoft Teams setup](#microsoft-teams-setup)
7. [SMTP / branded email setup](#smtp--branded-email-setup)
8. [Troubleshooting](#troubleshooting)

---

## Roles

| Role | What they do | Tech check |
|------|--------------|------------|
| **HR Executive** | Creates job drafts, edits jobs, uploads candidates, schedules interviews, runs auto-review | Logs into `/hr/login`, has `scope=hr` |
| **HR Manager** | Approves/rejects jobs and revisions, signs off rejections, manages auto-review rules | Same login; for now the UI shows approval buttons to everyone with `scope=hr` (fine-grained `hr.jobs.approve` permission is a future tweak) |
| **System Admin** | Configures SMTP, HR notification emails, Microsoft Teams integration | `scope=system`, accesses `/admin/email-settings` |

---

## Job lifecycle

```
[HR Executive]                    [HR Manager]                        [Public site]
─────────────────                 ─────────────────                   ────────────────
 1. Create job
    POST /hr/jobs
    → approval_status=draft
    → publish_status=draft
    → invisible to public                                              ✗ not visible

 2. Submit for approval
    POST /hr/jobs/{id}/submit-approval
    → approval_status=pending_approval
    → email sent to HR notification list                              ✗ not visible

                                   3a. Approve
                                       POST /hr/jobs/{id}/approve
                                       → approval_status=approved
                                       → publish_status=published      ✓ live!
                                       → branded email to HR list

                                   3b. Reject (4+ char reason required)
                                       POST /hr/jobs/{id}/reject
                                       {"remarks": "Salary band too low"}
                                       → approval_status=rejected
                                       → email to HR list with reason

                                   3c. Request revision
                                       POST /hr/jobs/{id}/request-revision
                                       → approval_status=revision_required

 4. Edit rejected/revision job
    PATCH /hr/jobs/{id} {...}
    → applied directly (it's not live anyway)
    → go back to step 2

 5. Edit ALREADY APPROVED job
    PATCH /hr/jobs/{id} {"title":"New Title"}
    → creates JobRevision (status=pending)
    → public job UNCHANGED
    → has_pending_revision=true                                       ✓ still old title

                                   6. Approve revision
                                       POST /hr/jobs/{id}/approve
                                       → revision payload applied
                                       → revision.status=approved     ✓ new title live
```

**Manual visibility toggle** (job already approved):

- `POST /hr/jobs/{id}/unpublish` — hide from public without losing approval
- `POST /hr/jobs/{id}/publish` — re-publish

**Audit trail**: every transition writes to `hr_job_approval_history`.
View it via `GET /hr/jobs/{id}/approval-history`.

---

## Candidate lifecycle

```
[Public visitor]                  [HR Executive]                     [HR Manager]
────────────────                  ─────────────────                  ────────────────
 1. Visit /careers/{slug}
 2. Attach CV
    → POST /public/.../parse-preview
    → form auto-fills (name, email,
      mobile, nationality, location,
      experience, salary, notice)
 3. Review + submit
    → POST /public/candidate-applications
    → Candidate + Application created
       (status=cv_received)
    → branded "Application received" email

                                   4. Auto-review fires
                                      (manual or scheduled)
                                      POST /hr/candidates/{c}/applications/{a}/auto-review
                                      → CandidateAutoReview row
                                      → decision = auto_shortlisted
                                                 | hr_review_pending
                                                 | auto_rejected (only if rule
                                                                  has auto_reject_enabled)

                                   5. HR reviews + acts
                                      Per-row:
                                        POST .../status (single)
                                      Bulk (checkbox + modal):
                                        POST /hr/candidates/applications/bulk-status

                                                                      6. (For blacklist only —
                                                                          superuser required)

 7. Receives status email (if HR
    ticked "Send email" on the
    bulk-status modal)
```

### Valid status transitions

Enforced server-side, applied identically to single and bulk status changes:

| From | Allowed next |
|------|--------------|
| `cv_received` | `ai_reviewed` · `hr_review_pending` · `shortlisted` · `rejected` · `blacklisted` |
| `ai_reviewed` | `hr_review_pending` · `shortlisted` · `rejected` · `blacklisted` |
| `hr_review_pending` | `shortlisted` · `rejected` · `blacklisted` |
| `shortlisted` | `first_interview` · `rejected` · `blacklisted` |
| `first_interview` | `technical_interview` · `final_interview` · `selected` · `rejected` |
| `technical_interview` | `final_interview` · `selected` · `rejected` |
| `final_interview` | `selected` · `rejected` |
| `selected` | `offer_sent` · `rejected` |
| `offer_sent` | `joined` · `rejected` |
| `rejected` / `joined` / `blacklisted` | terminal — superuser can reopen |

**Rejection always needs a 4+ char reason.** Blacklist needs an approval
reason **and** superuser.

---

## Auto-review rule setup (per job)

Each job has at most one rule. Rules are inactive until you explicitly
flip `is_active`, so existing jobs aren't auto-classified silently.

```http
PUT /hr/jobs/{id}/auto-review-rule
Content-Type: application/json
Authorization: Bearer <hr-token>

{
  "is_active": true,
  "auto_shortlist_threshold": 80,    // score ≥ 80 → auto_shortlisted
  "auto_reject_threshold": 40,       // score < 40 → auto_rejected (only if next flag is true)
  "auto_reject_enabled": false,      // KEEP FALSE unless you trust the rule completely
  "required_skills": ["python", "fastapi", "postgresql"],
  "preferred_skills": ["aws"],
  "min_experience": 5.0,             // years
  "max_expected_salary": 25000,
  "visa_keywords": ["transferable", "qid"],
  "location_keywords": ["doha", "qatar"],
  "nationality_keywords": [],        // empty = no filter
  "notice_period_keywords": ["immediate", "1 month"]
}
```

Other endpoints:

```http
POST /hr/jobs/{id}/auto-review-run        # bulk-run on all applications
GET  /hr/jobs/{id}/auto-review-summary    # dashboard counts
GET  /hr/jobs/{id}/auto-review-rule       # fetch current rule
```

### Decision logic

Implemented in `services/candidate_auto_review.py`:

1. If `score + AI nudge ≥ shortlist_threshold` **AND** no risk flags
   **AND** has required skills → **`auto_shortlisted`**
2. Else if `score < reject_threshold` **AND** `auto_reject_enabled=true`
   → **`auto_rejected`**
3. Otherwise → **`hr_review_pending`** (HR confirms)

### AI nudge

If the candidate already has a `CandidateAIReview` row, its recommendation
shifts the score:

| AI recommendation | Score adjustment |
|-------------------|------------------|
| `highly_recommended` | +5 |
| `recommended` | +2 |
| `neutral` | 0 |
| `not_recommended` | −5 |

---

## Interview workflow

```http
POST /hr/interviews
Content-Type: application/json
Authorization: Bearer <hr-token>

{
  "application_id": 42,
  "round_name": "Technical Round",
  "round_number": 2,
  "scheduled_at": "2026-06-10T14:00:00+03:00",
  "duration_minutes": 60,
  "mode": "online",                              // or "in_person" / "phone"
  "interviewer_id": 7,
  "create_teams_meeting": true,                  // auto-creates Teams meeting link
  "send_email_now": true,                        // fires branded email
  "candidate_email_override": null,              // optional
  "additional_attendee_emails": ["tech-lead@pug.com"],
  "cc_emails": ["hr-manager@pug.com"],
  "bcc_emails": ["audit@pug.com"],
  "email_subject": null,                         // null = use template default
  "email_note": "Please bring portfolio samples."
}
```

### What happens behind the scenes

1. If `create_teams_meeting=true` **AND** `mode=online` **AND** Teams is
   configured → calls Microsoft Graph, gets a `joinUrl`, saves to
   `Interview.meeting_link` + `calendar_event_id` (provider = `teams`).
2. Interview row is created (status=`scheduled`).
3. If `send_email_now=true` → renders the `interview_scheduled` template,
   sends to candidate + attendees, CCs/BCCs, logs to `hr_email_logs`.
4. **Fails gracefully** — Graph outage doesn't break the create; email
   failure is logged but doesn't roll back.

### Manual triggers later

```http
POST /hr/interviews/{id}/create-meet           # add Teams link to existing online iv
POST /hr/interviews/{id}/send-email            # resend invitation
POST /hr/interviews/{id}/resend-invitation     # alias of send-email
```

---

## Microsoft Teams setup

The integration is **fully optional** — when env vars are missing, every
interview still saves; only the auto-Teams-meeting feature is skipped.

Architecture: backend calls Microsoft Graph
`POST /users/{organizer}/onlineMeetings` with client-credentials auth.
The resulting `joinUrl` is written onto the interview's `meeting_link`
field; the meeting id is stored on `calendar_event_id` so future
edits / cancels can find it.

### Step 1 — Register an app in Azure AD

1. Open <https://portal.azure.com/> → sign in as a tenant administrator.
2. **Microsoft Entra ID** → **App registrations** → **New registration**.
   - Name: `PUG HR Interviews`
   - Supported account types: **Accounts in this organizational
     directory only (single tenant)**
   - Redirect URI: leave blank (this is a daemon app, not user-interactive)
   - Click **Register**.
3. On the new app's overview page, copy two values you'll need later:
   - **Application (client) ID** → `MS_CLIENT_ID`
   - **Directory (tenant) ID** → `MS_TENANT_ID`

### Step 2 — Create a client secret

1. Left menu → **Certificates & secrets** → **Client secrets** tab →
   **New client secret**.
2. Description: `pug-hr-interviews` — expiry: pick the longest your
   tenant policy allows (12-24 months is typical).
3. Click **Add** → **immediately copy the `Value` column** — it's only
   shown once. This is `MS_CLIENT_SECRET`.

### Step 3 — Grant Graph API permissions

1. Left menu → **API permissions** → **Add a permission**.
2. **Microsoft Graph** → **Application permissions** (not Delegated).
3. Search for `OnlineMeetings.ReadWrite.All` → tick it → **Add permissions**.
4. Back on the API permissions page click **Grant admin consent for
   `<tenant name>`** → **Yes**. The status column for the permission
   must turn into a green "Granted for …".

### Step 4 — Grant the app access to the HR organizer mailbox

Application permission alone is not enough — Microsoft requires an
**Application Access Policy** that whitelists which user mailboxes your
app can create meetings on behalf of. This is a one-time PowerShell
command run by a tenant admin.

On a Windows machine (or any machine with PowerShell 7):

```powershell
# Install the Microsoft Teams module once
Install-Module MicrosoftTeams -Scope CurrentUser

# Sign in as a Global Admin / Teams Service Admin
Connect-MicrosoftTeams

# Create the policy (one-time)
New-CsApplicationAccessPolicy `
  -Identity "PugHrInterviewsPolicy" `
  -AppIds "<MS_CLIENT_ID from step 1>" `
  -Description "PUG HR interview bot"

# Grant it to the organizer mailbox — the user the meetings will be
# created 'on behalf of'. Most teams use a dedicated HR mailbox like
# hr@yourdomain.com.
Grant-CsApplicationAccessPolicy `
  -PolicyName "PugHrInterviewsPolicy" `
  -Identity "hr@yourdomain.com"
```

> Policy propagation can take 20-30 minutes after `Grant-CsApplicationAccessPolicy`.
> If the smoke test in Step 6 returns `403 Forbidden`, wait and retry.

### Step 5 — Add env vars

Edit `backend/.env` (local) or `/home/parisgroup/PugWebSite/backend/.env`
(production) and append:

```bash
# Microsoft Teams meeting integration
MS_TEAMS_ENABLED=true
MS_TENANT_ID=<Directory (tenant) ID from step 1>
MS_CLIENT_ID=<Application (client) ID from step 1>
MS_CLIENT_SECRET=<client secret value from step 2>
MS_TEAMS_ORGANIZER_USER_ID=hr@yourdomain.com
MS_TEAMS_TIMEZONE=Asia/Qatar
```

`MS_TEAMS_ORGANIZER_USER_ID` must match the user you granted in
Step 4 — either the UPN (`hr@yourdomain.com`) or the AAD object id.

> No new Python packages are required — the integration uses `httpx`,
> which is already in `requirements.txt`.

### Step 6 — Restart + smoke-test

```bash
# Local
python run.py

# Production
sudo systemctl restart pugweb-backend
sudo journalctl -u pugweb-backend -n 30 --no-pager
```

Smoke test via API (replace `<token>` with an HR-scope JWT):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/hr/interviews \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": 1,
    "round_name": "Test Round",
    "scheduled_at": "2026-12-01T10:00:00+03:00",
    "duration_minutes": 30,
    "mode": "online",
    "create_teams_meeting": true,
    "send_email_now": false
  }' | jq .

# Look for "meeting_link" with a real teams.microsoft.com URL,
# "calendar_event_id" populated, and "calendar_provider": "teams".
```

### How candidates experience it

1. Candidate gets a branded HTML email with the Teams link as a
   **"Join Microsoft Teams meeting"** button, date/time in your
   configured timezone (default `Asia/Qatar`), round name, interviewer,
   any HR note.
2. Clicking the link opens Teams in the browser or app — no Microsoft
   account required on the candidate's side, the meeting accepts
   external/guest joiners by default.
3. **No automatic calendar invite is sent** (unlike the previous Google
   integration which created a calendar event). Candidates add the
   time to their own calendar from the email; HR can forward an Outlook
   invite separately if that's part of their flow. A future phase can
   wire in `POST /users/{id}/events` to send a real Outlook invite — it
   needs the additional `Calendars.ReadWrite` permission.

### Disabling without uninstalling

Set `MS_TEAMS_ENABLED=false` (or just remove the env var) and restart
the backend. The interview create endpoint will skip Teams meeting
creation; HR keeps using the manual `location_or_link` field. The
existing `meeting_link` values on past interviews keep working — the
Teams URLs remain valid until the underlying meeting is deleted in
Teams admin.

---

## SMTP / branded email setup

Without SMTP, the interview row is still created and the Teams link is
still generated — but the candidate never gets the branded HTML email.

1. Log in to `/admin/email-settings` as the system admin.
2. Fill in:
   - **Email enabled**: ✅
   - **SMTP host / port / username / password** (e.g. Office 365:
     `smtp.office365.com` / `587`)
   - **From email** (e.g. `hr@parisunitedgroup.com`)
   - **From name**: `PUG HR`
   - **HR notification emails**:
     `["hr-manager@pug.com", "executive@pug.com"]`
   - **Interview email enabled**: ✅
   - **Candidate email enabled**: ✅
   - **Job approval email enabled**: ✅
   - **Brand logo URL**: full HTTPS URL to your logo PNG (shown in
     email header)
   - **Email footer text**: copyright / disclaimer line
3. Click **Send test email** to verify.

### Per-stream toggles

Every branded email is gated by one of three feature flags on
`email_settings`, so admins can mute a single stream without disabling
the whole SMTP transport:

| Toggle | Affects |
|--------|---------|
| `job_approval_email_enabled` | Job submitted / approved / rejected / revision-requested / published |
| `candidate_email_enabled` | Application received / shortlisted / rejected / selected |
| `interview_email_enabled` | Interview scheduled / rescheduled / cancelled |

Disabled streams still write a row to `hr_email_logs` with
`status="failed"` and `error_message="Disabled by '<flag>' setting"` so
the audit trail stays complete.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `meeting_link` is null but interview created | One of the `MS_*` env vars is unset/blank | Re-check `MS_TEAMS_ENABLED`, `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TEAMS_ORGANIZER_USER_ID` |
| Backend log shows `Token request failed (401)` | Wrong tenant id, client id or secret — or the secret expired | Re-issue the client secret in Azure → **App registrations** → **Certificates & secrets** and update `MS_CLIENT_SECRET` |
| Backend log shows `Graph POST … failed (403)` with `Forbidden` | Application Access Policy not granted to the organizer mailbox yet (or still propagating — takes up to 30 min) | Re-run `Grant-CsApplicationAccessPolicy` from step 4; wait, then retry |
| Backend log shows `Graph POST … failed (404)` with `Resource … not found` | `MS_TEAMS_ORGANIZER_USER_ID` doesn't match a real mailbox in the tenant | Use the UPN (e.g. `hr@yourdomain.com`) or the user's AAD object id |
| Teams link works but external candidates can't join | Tenant policy blocks anonymous join | Teams Admin Center → **Meetings** → **Meeting policies** — enable "Anonymous users can join a meeting" |
| Email logged as "failed" with "SMTP authentication failed" | Wrong username/password in `/admin/email-settings` | Re-enter the password (it's encrypted at rest, blank = "keep existing") |
| Test email button works but interview emails don't | One of the per-event toggles is off | Check `interview_email_enabled` in Admin Email Settings |
| Job stays at `draft` after `submit-approval` | Job lifecycle status is `closed` — submit was a no-op | Reopen the job first (`POST /hr/jobs/{id}/reopen`) |
| Public site still shows old title after editing approved job | This is by design — edit created a `JobRevision`; public stays unchanged until HR Manager approves | `POST /hr/jobs/{id}/approve` to publish the revision |
| Bulk-status modal greyed out for some candidates | They have no application yet (CV-only) | Move them off the candidate row — they need an application first |
| Auto-review never returns `auto_rejected` | `auto_reject_enabled` defaults to `false` on every rule | Toggle it on per-job if you want the engine to auto-reject |

---

## Known limitations (phase-10 follow-up)

These are intentional gaps in the current branch — captured here so the
next phase knows where to start.

### Permissions are still coarse

Every HR endpoint is gated by a single `hr` scope via
`Depends(require_hr_admin)`. A user with the **HR Manager** role can:

- read, create, update, and delete every candidate
- approve / reject / revise every job
- schedule, reschedule, or cancel every interview
- bulk-change candidate status
- run auto-review manually

The `Permission` model + `User.has_permission()` helper already exist
but are not consulted by any HR route. A future phase should:

1. Define fine-grained scope constants (e.g. `hr:candidates:read`,
   `hr:candidates:write`, `hr:jobs:approve`, `hr:interviews:schedule`).
2. Replace `Depends(require_hr_admin)` on each endpoint with the
   narrower scope it actually needs.
3. Seed default roles via Alembic so existing HR users keep working.
4. Update the role-management UI under `/admin/roles` to expose the new
   permission checkboxes.

Until that ships, every HR seat is effectively "HR admin".
