# Privacy and Data-Retention Policy

This document describes what personal data the Paris United Group
Holding application collects, why, how long it is retained, and the
operator's responsibilities under GDPR and equivalent regimes. It is
deliberately concise so it can be embedded in the public site's
"Privacy Policy" page with minimal rewording.

Last reviewed: **2026-05**.

---

## 1 · Data we collect

| # | Data category                | Origin / endpoint                                  | Storage location                                  |
|---|------------------------------|----------------------------------------------------|---------------------------------------------------|
| 1 | Contact-form submissions     | `POST /api/v1/contact`                             | `contact_messages` table                          |
| 2 | Newsletter subscriptions     | `POST /api/v1/newsletter`                          | `newsletter_subscribers` table                    |
| 3 | Candidate applications + CVs | `POST /api/v1/candidate-applications`              | `candidates` / `applications` tables + `UPLOAD_DIR/cv/` filesystem |
| 4 | Public AI assistant queries  | `POST /api/v1/ai-assistant/ask`                    | `public_ai_queries` table                         |
| 5 | Admin / HR user accounts     | Internal staff only — created by admin            | `users`, `roles`, `permissions` tables            |
| 6 | Audit log                    | Every authenticated mutation + the four public POSTs | `audit_logs` table                             |
| 7 | Web-server access logs       | Nginx                                              | `/var/log/nginx/pug-access.log`                   |
| 8 | Database backups             | `pg_dump` via the daily cron                        | `/var/backups/pug/` (and optional S3)             |

We **do not** use third-party tracking cookies, analytics pixels, or
remarketing tags on the public site. The only cookies served are the
short-lived session cookies Next.js sets for routing — no PII.

---

## 2 · Why we collect each category (lawful basis)

| # | Category                | Purpose                                            | Lawful basis (GDPR Art. 6) |
|---|-------------------------|----------------------------------------------------|----------------------------|
| 1 | Contact-form submissions | Reply to the inquiry; route to the right team.    | Legitimate interest        |
| 2 | Newsletter subscriptions | Send the newsletter the subscriber opted into.    | Consent                    |
| 3 | Candidate applications  | Evaluate the candidate for the role they applied to. | Pre-contractual measures (Art. 6(1)(b)) |
| 4 | Public AI assistant     | Improve the assistant and detect abuse.           | Legitimate interest        |
| 5 | Admin / HR users        | Operate the HR system.                            | Contractual (employment)   |
| 6 | Audit log               | Security, forensic investigation, GDPR Art. 30.   | Legal obligation + legitimate interest |
| 7 | Access logs             | Operational reliability and security.             | Legitimate interest        |
| 8 | Backups                 | Disaster recovery.                                | Legitimate interest        |

---

## 3 · Retention schedule

Retention should be enforced by a periodic purge job (not yet
automated — see §6). Until that job exists, retention is enforced by
the database administrator following the schedule below.

| Category                      | Retention period | Trigger for deletion                       |
|-------------------------------|------------------|--------------------------------------------|
| Contact-form submissions      | **24 months**    | Time since `created_at`                    |
| Newsletter subscriptions      | Until unsubscribed, then 30 days | `is_active=false` for 30 days |
| Candidate applications + CVs  | **36 months** from last activity | Latest of: application `created_at`, last status change, last interview |
| Hired-candidate records       | Moved to HR personnel system; ATS record kept 36 months | Hire event |
| Public AI assistant queries   | **90 days**      | Time since `created_at`                    |
| Admin / HR user accounts      | Until employment ends + 12 months | `disabled_at` + 12 months |
| Audit log                     | **24 months**    | Time since `created_at`                    |
| Web-server access logs        | 14 days          | Daily logrotate                            |
| Database backups              | 14 days local; if S3, 90 days | Backup script retention sweep |

We will hold data longer than the periods above only when (a) a
specific legal hold applies (litigation, regulator request) or (b) the
data subject has explicitly extended their consent (e.g. a candidate
asking us to keep their CV on file for future roles).

---

## 4 · Data subject rights

GDPR (and equivalent regimes) grant the data subject the right to:

- **Access** — receive a copy of all data we hold about them.
- **Rectification** — correct inaccurate data.
- **Erasure** ("right to be forgotten") — delete their data, subject
  to the legal-obligation exceptions in §3.
- **Restriction** — pause processing while a dispute is resolved.
- **Portability** — receive their data in a structured, machine-readable form.
- **Object** — opt out of legitimate-interest processing.
- **Withdraw consent** — for newsletter and any consent-based purpose.

### How to handle a request

1. Verify the requester's identity (email round-trip is the minimum).
2. Locate every record using the lookup script (`scripts/dsr_lookup.py`
   — to be added; see §6).
3. Choose a fulfillment action:
   - **Access / portability**: export the matching rows as JSON and
     send via a secure channel (encrypted attachment, expiring link).
   - **Erasure**: hard-delete the rows in the same transaction; remove
     the CV file from `UPLOAD_DIR/cv/`; write a `data_subject.erasure`
     audit entry that records *what kind* of data was erased but not
     the data itself.
   - **Rectification**: edit in place, audit the change.
4. Respond within **30 days** of the verified request.

The newsletter unsubscribe link (when implemented in a later phase)
must perform a soft-delete + scheduled hard-delete within the
30-day window above.

---

## 5 · Operator responsibilities

The Paris United Group Holding operator (the company running this
deployment) commits to:

- **Encryption in transit.** Cloudflare terminates TLS at the edge;
  Nginx terminates TLS at the origin using the Cloudflare Origin
  Certificate. No plaintext HTTP is served from the origin.
- **Encryption at rest.** Database backups and `UPLOAD_DIR/cv/`
  must reside on encrypted volumes (EBS encrypted, S3 SSE).
- **Least-privilege access.** Production access uses individual
  named accounts; `pug_user` (DB role) and `pug` (system user)
  are service accounts not used by humans for ad-hoc queries.
- **Audit logging.** Every authenticated mutation and every public
  POST writes an `audit_logs` row including the request IP and user
  agent. The audit log is admin-only (`/admin/audit`).
- **Breach notification.** If a breach is detected, the operator
  will notify affected individuals and the relevant supervisory
  authority within **72 hours** of becoming aware.
- **Vendor list.** The only sub-processor in the default deployment
  is **Cloudflare** (DNS + CDN + DDoS) and, if enabled,
  **Microsoft Azure OpenAI** (AI assistant + HR AI review). Both
  receive data via TLS-protected calls; neither receives candidate
  CVs or contact-form messages by default — only the AI assistant's
  question text and the HR AI review's redacted candidate summary.

---

## 6 · Implementation gaps to close

These items are tracked but not yet automated:

- [ ] **Scheduled purge job.** A nightly script that deletes rows
      whose retention window has elapsed (see §3). Until this lands,
      retention is enforced manually.
- [ ] **DSR lookup script.** A CLI under `app/scripts/` that takes an
      email and emits every row touching that subject across the
      schema, plus matching files under `UPLOAD_DIR/`.
- [ ] **Public privacy page.** A Next.js route that reads this file
      via the CMS pages model so the legal copy can be edited from
      the admin UI without redeploying.
- [ ] **Unsubscribe link.** The contact email's unsubscribe footer is
      not yet wired to a one-click endpoint.
- [ ] **Cookie banner.** Required by ePrivacy in the EU even though we
      don't currently set non-essential cookies. The banner should
      surface a link to this policy.

Each of these is a small, isolated piece of work that can be picked up
in a follow-up phase without changing the data model.

---

## 7 · Change log

| Date       | Change                                                  |
|------------|---------------------------------------------------------|
| 2026-05    | Initial Phase 19 publication.                           |
