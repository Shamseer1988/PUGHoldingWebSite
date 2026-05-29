# Phase A-5 — Cloudflare R2 Setup

This is the operations-side companion to Phase A-6 (`backend/app/services/storage.py` — the R2 backend code). Once R2 is configured below and the four `R2_*` environment variables are populated, the backend automatically routes uploaded media (CMS images, catalogue PDFs, candidate CVs) to R2 instead of writing to local disk. Unconfigured installs (dev, CI, any environment where the four variables are empty) keep using the local-disk fallback unchanged.

---

## Why R2

| | Local disk | Cloudflare R2 |
|---|---|---|
| Egress fees | N/A | **Zero** |
| CDN-fronted reads | Behind your origin | Edge-served via Cloudflare |
| Survives a pod restart | No | Yes |
| Multi-instance safe | No (each replica has its own disk) | Yes |
| Cost at 100 GB | Disk-only | ~$1.50/month + zero egress |

R2 gives us S3 semantics with no egress bill and a CDN attached. Storage costs are billed at $0.015/GB/month — cheap enough that we can hold every uploaded CV indefinitely without budget concerns.

---

## Prerequisites

* A Cloudflare account (any tier — the Free plan supports R2).
* A domain you can manage DNS on, if you want to point a custom subdomain like `media.your-domain.com` at the bucket (recommended for production).
* `awscli` or `s3cmd` installed locally if you want to test the credentials before pasting them into `.env`.

---

## Step 1 — Enable R2 on the Cloudflare account

1. Sign in at https://dash.cloudflare.com.
2. In the left sidebar, click **R2 Object Storage**.
3. If this is your first time, Cloudflare asks you to subscribe to the R2 service. Click **Subscribe to R2** and accept the terms. There is no upfront cost — billing is metered per GB stored + per million operations.
4. Once subscribed, you land on the **R2 Overview** page.

---

## Step 2 — Create the bucket

1. From **R2 Overview**, click **Create bucket**.
2. **Bucket name**: `pug-holding-media` (or any value — make sure `R2_BUCKET_NAME` in `.env` matches).
3. **Location hint**: pick the closest region (Asia-Pacific for a Qatar-hosted ops team, EU for Europe, etc.). This only affects where the object is initially placed; reads from elsewhere still go through the Cloudflare edge.
4. **Default storage class**: leave on **Standard**. Infrequent-access pricing is for archival data; CMS images and CVs are hot data.
5. Click **Create bucket**.

After creation you land on the bucket detail page. Note the **S3 API URL** — it looks like `https://<account-id>.r2.cloudflarestorage.com/pug-holding-media`. The endpoint portion (`https://<account-id>.r2.cloudflarestorage.com`) is what goes into `R2_ENDPOINT_URL`.

---

## Step 3 — Generate the API token

R2 uses scoped API tokens that map to S3 access-key pairs.

1. From the bucket page, click the **Settings** tab (or go to **R2 Overview → Manage R2 API tokens**).
2. Click **Create API token**.
3. **Token name**: `pug-holding-api` (anything memorable — this shows up in audit logs).
4. **Permissions**: select **Object Read & Write**. The backend never needs admin access (creating / deleting buckets) — only the data plane.
5. **Specify bucket**: scope it to the single bucket you just created (`pug-holding-media`). Don't grant account-wide access — least-privilege wins if a key ever leaks.
6. **TTL**: leave on the default (forever). You can rotate manually whenever you choose.
7. Click **Create API token**.

Cloudflare shows the credentials **once**:

| Field | Cloudflare label | Maps to `.env` |
|---|---|---|
| Access Key ID | Access Key ID | `R2_ACCESS_KEY_ID` |
| Secret Access Key | Secret Access Key | `R2_SECRET_ACCESS_KEY` |
| Endpoint | "Use jurisdiction-specific endpoints" / S3 API | `R2_ENDPOINT_URL` |

Copy them somewhere safe immediately — Cloudflare will not show the secret again, and "rotate the token" is the only recovery path.

> ⚠️ **Never commit these to git.** They go into the environment (`.env` locally, secrets manager in production). The `.env` file is already gitignored.

---

## Step 4 — (Optional but recommended) Wire a custom domain

By default the public URL of an object looks like:

```
https://<account-id>.r2.cloudflarestorage.com/pug-holding-media/cms/hero/foo.jpg
```

You probably want `https://media.your-domain.com/cms/hero/foo.jpg` instead — both for branding and to bypass Cloudflare-internal CDN warm-up.

1. From the bucket page, click the **Settings** tab.
2. Scroll to **Public access** → **Custom Domains** → **Connect domain**.
3. Enter the subdomain you want (e.g. `media.your-domain.com`).
4. Cloudflare prompts you to add a CNAME or proxy the subdomain through Cloudflare. If the domain is already on Cloudflare, the DNS record is created automatically; otherwise add the CNAME at your registrar pointing at the value Cloudflare shows.
5. Once verified (usually 1-2 minutes), the custom domain shows as **Active**.

Set `R2_PUBLIC_BASE_URL=https://media.your-domain.com` in `.env`. The backend builds public URLs against this base when set, and falls back to the long `<account-id>.r2.cloudflarestorage.com` form when unset.

For frontend image rendering (Next.js `<Image>` / R2 CDN paths), also set `NEXT_PUBLIC_MEDIA_BASE_URL=https://media.your-domain.com` in `frontend/.env.local` — Phase A-7's `normaliseMediaUrl` reads it.

---

## Step 5 — Paste the values into `backend/.env`

```ini
# --- Phase A-6: Cloudflare R2 object storage ---
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<your access key id>
R2_SECRET_ACCESS_KEY=<your secret access key>
R2_BUCKET_NAME=pug-holding-media
R2_PUBLIC_BASE_URL=https://media.your-domain.com   # leave empty if no custom domain
```

Restart the backend (`uvicorn` or the Docker container). The boto3 client is constructed once at startup; env-var changes don't propagate to a running process.

---

## Step 6 — Verify the connection

Two ways to confirm R2 is wired up correctly.

### Via the admin health endpoint

After logging in as an admin user, hit:

```http
GET /api/v1/admin/storage/health
Authorization: Bearer <admin token>
```

It performs an **end-to-end round-trip** — upload a tiny test object, read it back, delete it — and returns a structured report:

```json
{
  "backend": "r2",
  "configured": true,
  "bucket": "pug-holding-media",
  "endpoint_url": "https://<account-id>.r2.cloudflarestorage.com",
  "public_base_url": "https://media.your-domain.com",
  "roundtrip": {
    "ok": true,
    "upload_key": "_healthcheck/2026-05-29T12-34-56.txt",
    "elapsed_ms": 312
  }
}
```

`roundtrip.ok: false` means the credentials don't match the bucket (or the bucket doesn't exist). The `error` field carries the underlying message.

### Via the CLI script

From the backend container or any host with the venv activated:

```bash
python -m app.scripts.r2_smoke_test
```

Same round-trip logic, but driven from the command line — handy for ops without a live admin session.

Both checks delete the test object after reading it, so nothing pollutes the bucket.

---

## Step 7 — (Optional) Backfill existing local-disk files

If you're flipping an existing install from local-disk to R2, anything already uploaded lives at `backend/app/uploads/` and is invisible to R2. A small migration script is in scope for a follow-up phase; today the recommended path is manual:

1. `cd backend/app/uploads`
2. Sync the tree using `awscli` configured with the R2 credentials:
   ```bash
   aws s3 sync . s3://pug-holding-media/ \
     --endpoint-url "$R2_ENDPOINT_URL" \
     --no-progress
   ```
3. Verify a representative URL from the admin CMS UI — it should now resolve through `R2_PUBLIC_BASE_URL`.

New uploads from this point on land in R2 directly without any further intervention.

---

## Cost guardrails (FYI)

R2 bills three things:

| Metric | Price (May 2026) | Practical impact |
|---|---|---|
| Storage | $0.015/GB/month | 100 GB ≈ $1.50/mo |
| Class A operations (PUT, LIST) | $4.50 per million | 10k uploads/month ≈ $0.05 |
| Class B operations (GET, HEAD) | $0.36 per million | Reads served by the CDN, not metered by R2 — these are the cache misses only |
| Egress | **Zero** | The big win vs. S3 |

A typical SMB-sized PUG install (a few thousand candidates, low-thousand CMS images) costs <$5/month all-in. Hard ceilings can be set in the Cloudflare dashboard if you want a spend cap.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `403 InvalidAccessKeyId` on first upload | Token scope is wrong (account-wide instead of bucket-scoped, or wrong bucket name) | Recreate the token with Object Read & Write **on this bucket only**. |
| `403 SignatureDoesNotMatch` | Endpoint URL is missing the protocol (`r2.cloudflarestorage.com` instead of `https://...`) | Always include `https://`. |
| Custom domain serves a 525 error | Cloudflare Universal SSL not yet provisioned (typically <5 min after CNAME add) | Wait 5 minutes; check the **Custom Domains** panel for the SSL status. |
| Upload succeeds but public URL 404s | Public access not enabled on the bucket | **Settings → Public access → Allow Access** (only for buckets serving public content like CMS hero images). Private buckets should stay private; the backend signs URLs in that case. |
| Health endpoint returns `"backend": "local"` even though `R2_*` is set | One of the four required values is empty | Check `settings.r2_configured` in the backend logs at startup — it logs which check failed. |
