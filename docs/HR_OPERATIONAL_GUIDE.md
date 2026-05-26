# PUG HR — Operational Guide

End-to-end workflow guide for the advanced HR ATS module: who does what,
when each email fires, and how to enable the optional Google Calendar /
Meet integration. Companion document to
[`HR_ADVANCED_MODULE_CLAUDE_PROMPT.txt`](./HR_ADVANCED_MODULE_CLAUDE_PROMPT.txt)
(the build spec).

---

## Table of contents

1. [Roles](#roles)
2. [Job lifecycle](#job-lifecycle)
3. [Candidate lifecycle](#candidate-lifecycle)
4. [Auto-review rule setup](#auto-review-rule-setup-per-job)
5. [Interview workflow](#interview-workflow)
6. [Google Calendar / Meet setup](#google-calendar--meet-setup)
7. [SMTP / branded email setup](#smtp--branded-email-setup)
8. [Troubleshooting](#troubleshooting)

---

## Roles

| Role | What they do | Tech check |
|------|--------------|------------|
| **HR Executive** | Creates job drafts, edits jobs, uploads candidates, schedules interviews, runs auto-review | Logs into `/hr/login`, has `scope=hr` |
| **HR Manager** | Approves/rejects jobs and revisions, signs off rejections, manages auto-review rules | Same login; for now the UI shows approval buttons to everyone with `scope=hr` (fine-grained `hr.jobs.approve` permission is a future tweak) |
| **System Admin** | Configures SMTP, HR notification emails, Google Meet integration | `scope=system`, accesses `/admin/email-settings` |

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
  "create_google_meet": true,                    // auto-creates Meet link
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

1. If `create_google_meet=true` **AND** `mode=online` **AND** Google is
   configured → creates a Calendar event, gets a Meet link, saves to
   `Interview.meeting_link` + `calendar_event_id`.
2. Interview row is created (status=`scheduled`).
3. If `send_email_now=true` → renders the `interview_scheduled` template,
   sends to candidate + attendees, CCs/BCCs, logs to `hr_email_logs`.
4. **Fails gracefully** — Google outage doesn't break the create; email
   failure is logged but doesn't roll back.

### Manual triggers later

```http
POST /hr/interviews/{id}/create-meet           # add Meet to existing online iv
POST /hr/interviews/{id}/send-email            # resend invitation
POST /hr/interviews/{id}/resend-invitation     # alias of send-email
```

---

## Google Calendar / Meet setup

The integration is **fully optional** — when env vars are missing, every
interview still saves; only the auto-Meet feature is skipped.

### Step 1 — Create a Google Cloud project

1. Go to <https://console.cloud.google.com/>
2. **New Project** → name it "PUG HR Calendar"
3. Note the project ID

### Step 2 — Enable Calendar API

1. **APIs & Services** → **Library**
2. Search **"Google Calendar API"** → **Enable**

### Step 3 — Create a service account

1. **IAM & Admin** → **Service Accounts** → **Create Service Account**
   - Name: `pug-hr-calendar`
   - Role: leave blank (we grant calendar access at the calendar level,
     not the project level — least privilege)
2. Open the new service account → **Keys** tab → **Add Key** → **JSON**
3. Save the downloaded file as `pug-google-service-account.json` —
   **treat it as a password**, never commit it to git.
4. **Copy the service account email** — it looks like
   `pug-hr-calendar@<project-id>.iam.gserviceaccount.com`

### Step 4 — Create the HR calendar + share with the service account

1. Sign in to <https://calendar.google.com/> as the **HR mailbox**
   (e.g. `hr@pug.example.com`).
2. **Left sidebar** → "Other calendars" → **+** → **Create new calendar**
   - Name: "PUG HR Interviews"
   - Time zone: Asia/Qatar (or your local)
3. Open the new calendar's settings → **Share with specific people or
   groups**.
4. **Add people** → paste the service-account email → permission **"Make
   changes to events"**.
5. Scroll down to **Integrate calendar** → copy the **Calendar ID**
   (looks like `abc123@group.calendar.google.com`).

### Step 5 — Place the credentials file on the server

```bash
# As parisgroup user on the EC2 box
mkdir -p /home/parisgroup/PugWebSite/backend/secrets
chmod 700 /home/parisgroup/PugWebSite/backend/secrets

# Upload the JSON (from your laptop)
scp pug-google-service-account.json ubuntu@<EC2>:/tmp/
ssh ubuntu@<EC2> "sudo mv /tmp/pug-google-service-account.json \
                    /home/parisgroup/PugWebSite/backend/secrets/ && \
                  sudo chown parisgroup:parisgroup \
                    /home/parisgroup/PugWebSite/backend/secrets/pug-google-service-account.json && \
                  sudo chmod 600 \
                    /home/parisgroup/PugWebSite/backend/secrets/pug-google-service-account.json"
```

### Step 6 — Add env vars

Edit `/home/parisgroup/PugWebSite/backend/.env` and append:

```bash
# Google Calendar / Meet integration
GOOGLE_CALENDAR_ENABLED=true
GOOGLE_CALENDAR_ID=abc123@group.calendar.google.com
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/home/parisgroup/PugWebSite/backend/secrets/pug-google-service-account.json
GOOGLE_CALENDAR_TIMEZONE=Asia/Qatar
```

### Step 7 — Install the Google client library

The backend **lazy-imports** the client, so it's not a hard dependency.
Install it once:

```bash
sudo -u parisgroup bash -c '
  cd /home/parisgroup/PugWebSite/backend
  source .venv/bin/activate
  pip install google-api-python-client google-auth
  deactivate
'
```

Then pin the versions in `backend/requirements.txt` so future deploys
keep them:

```
google-api-python-client==2.149.0
google-auth==2.35.0
```

### Step 8 — Restart + smoke-test

```bash
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
    "create_google_meet": true,
    "send_email_now": false
  }' | jq .

# Look for "meeting_link" with a real meet.google.com URL
# and "calendar_event_id" populated.
```

### How candidates experience it

1. Candidate gets an HTML email with PUG branding, the Meet link as a
   button, date/time in `Asia/Qatar`, round name, interviewer, any HR
   note.
2. **Calendar invite arrives separately from Google** (because we set
   `sendUpdates="all"` when creating the event) — so candidate +
   interviewer + attendees see it on their own calendars.
3. If candidate emails HR back to reschedule, HR uses `PATCH
   /hr/interviews/{id}` to update — and either clicks "Send email" again
   or relies on the rescheduled-email template (manual call to
   `notify_interview_rescheduled` from the API).

### Disabling without uninstalling

Set `GOOGLE_CALENDAR_ENABLED=false` (or just remove the env var) and
restart the backend. The interview create endpoint will skip Meet
creation; HR keeps using the manual `location_or_link` field.

---

## SMTP / branded email setup

Without SMTP, the interview row is still created and the Meet link is
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
| `meeting_link` is null but interview created | Google client lib not installed | `pip install google-api-python-client google-auth` in the venv |
| `meeting_link` null + log shows "Service account JSON not found" | Wrong path or wrong permissions | Check `GOOGLE_SERVICE_ACCOUNT_JSON_PATH`; `chmod 600` + correct owner |
| `calendarNotFound` in log | Calendar ID typo OR service account not shared on it | Re-check Calendar Settings → Integrate calendar; re-share with the service-account email |
| Meet link created but no calendar invite emails to attendees | Calendar isn't a Google Workspace calendar (free accounts can't invite externals via API) | Use a Workspace calendar |
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
