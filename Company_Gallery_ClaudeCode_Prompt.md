# Company Gallery — Claude Code Implementation Prompt

> Copy the section under **PROMPT TO PASTE INTO CLAUDE CODE** into a fresh Claude Code session. Self-contained — covers the junction table, migration, admin CRUD, picker modal, drag-and-drop ordering, public endpoint, page rewire, empty state, tests, and acceptance criteria.

---

## Context for the human

The public Company detail page (`/companies/[slug]`) currently shows 6 fake gradient tiles in its "Gallery" section, with a developer note: *"Gallery placeholders — media uploads land in the Phase 5 follow-up CMS module."* The original PUG website prompt scoped this feature (it lists `company_gallery` as a database table and "Add gallery images" as an admin action), but it was never implemented — there's no schema, no API, no admin section.

This prompt fills that gap with a **many-to-many junction table** (`cms_company_media`) that links the existing `companies` table to the existing `cms_media_assets` library. Marketing picks from the central media library, assigns photos and videos to one or more companies' galleries, drags to reorder, and writes a per-company caption. The same photo can appear in multiple companies (group photo featuring Paris Packing + Paris Hyper + leadership), with a different caption per context.

The architecture mirrors the `FeaturedMedia` module from the earlier prompt — same pattern (junction table referencing the central library), same admin UX style (picker modal + drag-and-drop list + inline editing) — so the codebase stays consistent.

---

## PROMPT TO PASTE INTO CLAUDE CODE

````
You are working in the Paris United Group monorepo. Read CLAUDE.md, the docs/ folder, and the files I list below before touching code. Print a numbered file-by-file plan and wait for confirmation before editing.

# Goal

Replace the placeholder gradient tiles on the public Company detail page with a real, admin-curated gallery powered by a many-to-many junction table linking companies to the existing cms_media_assets library. Marketing should be able to assign existing media to any company's gallery, drag to reorder, write per-company captions, and toggle each entry active. End-to-end: backend model + migration + admin CRUD + public endpoint + admin UI + public page rewire + placeholder removal.

# Current state to reproduce mentally before editing

- Backend model `Company` lives in `backend/app/models/cms.py` line 72. Has `services` relationship (one-to-many) — use that as the relationship pattern reference
- Backend model `MediaAsset` (table `cms_media_assets`) exists; standard fields are `id, kind, url, title, alt_text, tags, mime_type, width, height` and more
- Backend admin CRUD pattern lives in `backend/app/api/endpoints/admin_cms.py` — HeroSlide is the template (list/create/patch/delete + audit log)
- The earlier `FeaturedMedia` module (if already shipped from `Featured_Media_Admin_ClaudeCode_Prompt.md`) is the closest analog — reuse that pattern wherever possible
- Frontend admin pages live in `frontend/app/admin/<resource>/page.tsx`. Companies admin: `app/admin/companies/page.tsx` — this is where the new Gallery tab will live
- Public page to rewire: `frontend/app/(public)/companies/[slug]/page.tsx` lines 107-123. Currently renders 6 gradient `<span aria-hidden>` elements + the placeholder text
- Frontend types mirror Pydantic in `frontend/lib/admin/types.ts`
- Latest Alembic migration: identify by reading `backend/migrations/versions/` — newest revision becomes this PR's `down_revision`

# Backend — model

Add to `backend/app/models/cms.py`:

```python
class CompanyMedia(Base, TimestampMixin):
    __tablename__ = "cms_company_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_asset_id: Mapped[int] = mapped_column(
        ForeignKey("cms_media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Per-company override of the media asset's caption — null = fall back
    # to media_asset.title or media_asset.alt_text
    caption: Mapped[Optional[str]] = mapped_column(String(500))
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    company: Mapped[Company] = relationship(
        "Company", back_populates="gallery"
    )
    media_asset: Mapped["MediaAsset"] = relationship(
        "MediaAsset", lazy="joined"
    )

    __table_args__ = (
        UniqueConstraint("company_id", "media_asset_id", name="uq_company_media_pair"),
    )
```

Add the reverse relationship on `Company`:

```python
gallery: Mapped[List["CompanyMedia"]] = relationship(
    "CompanyMedia",
    back_populates="company",
    cascade="all, delete-orphan",
    lazy="selectin",
    order_by="CompanyMedia.display_order",
)
```

Add `CompanyMedia` to `app/models/__init__.py` exports.

The UniqueConstraint prevents adding the same photo twice to one company — drag-reorder is the way to change position. If marketing wants the same photo twice in a row, that's a UX smell, not a feature.

# Backend — schemas

Add to `backend/app/schemas/cms.py`:

```python
class CompanyMediaBase(BaseModel):
    media_asset_id: int
    caption: Optional[str] = Field(default=None, max_length=500)
    display_order: int = 0
    is_active: bool = True


class CompanyMediaCreate(CompanyMediaBase):
    pass


class CompanyMediaUpdate(BaseModel):
    caption: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class CompanyMediaReorderItem(BaseModel):
    id: int
    display_order: int


class CompanyMediaReorderRequest(BaseModel):
    items: List[CompanyMediaReorderItem]


class CompanyMediaRead(CompanyMediaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime
    media_asset: MediaAssetRead
```

# Backend — migration

Create `backend/migrations/versions/20260524_00XX_company_media.py` (use the next available revision number after the current head):

- `upgrade()` creates `cms_company_media` table with all columns above, both FKs with `ondelete="CASCADE"`, both indexes (`company_id`, `media_asset_id`, `display_order`), and the unique constraint on `(company_id, media_asset_id)`
- `downgrade()` drops the table

Verify reversibility with `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.

# Backend — admin CRUD endpoints

Add to `backend/app/api/endpoints/admin_cms.py` (audit log on every mutation, follow HeroSlide pattern):

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/admin/cms/companies/{company_id}/media` | `List[CompanyMediaRead]` | order by `display_order ASC, id ASC` |
| POST | `/admin/cms/companies/{company_id}/media` | `CompanyMediaRead` 201 | body is `CompanyMediaCreate`; validate `media_asset_id` exists; on UniqueConstraint violation return 409 with a useful message |
| PATCH | `/admin/cms/company-media/{id}` | `CompanyMediaRead` | partial update |
| DELETE | `/admin/cms/company-media/{id}` | 204 | |
| POST | `/admin/cms/companies/{company_id}/media/reorder` | `List[CompanyMediaRead]` | accept `CompanyMediaReorderRequest`, persist all `display_order` values in one transaction |

Audit actions: `cms.company_media.create`, `.update`, `.delete`, `.reorder`. Audit `target_type="company_media"`, `target_id` = the row id.

# Backend — public read endpoint

Extend the existing company detail public endpoint in `backend/app/api/endpoints/public.py` so the company response includes its gallery — OR add a separate endpoint, your call. Pick the cleaner option:

**Option A (preferred)** — embed gallery in the existing `CompanyRead` schema:

```python
class CompanyRead(CompanyBase):
    # ... existing fields ...
    gallery: List[CompanyMediaRead] = []
```

Backend filters to `is_active=True` only. Eager-loads via `selectinload(Company.gallery).selectinload(CompanyMedia.media_asset)`.

**Option B** — separate endpoint `GET /companies/{slug}/media`. Add it if A balloons the response too much for list pages.

Default to A. If the gallery payload becomes large (>20 items × 6 KB each), revisit later — flag in the PR description.

# Frontend — types

Add to `frontend/lib/admin/types.ts`:

```ts
export interface CompanyMediaItem {
  id: number;
  company_id: number;
  media_asset_id: number;
  caption: string | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  media_asset: MediaAsset;
}
```

Extend the existing `Company` interface to add:

```ts
gallery?: CompanyMediaItem[];
```

Make it optional so list endpoints that don't include the gallery still typecheck.

# Frontend — public API client

In `frontend/lib/public-api.ts`, the `getCompanyBySlug()` (or equivalent) function should now include `gallery` in the response automatically once the backend embeds it. No client code change needed unless the function currently strips fields.

If using Option B (separate endpoint), add:

```ts
export async function getCompanyMedia(companyId: number): Promise<CompanyMediaItem[]>
```

# Frontend — admin page extensions

Edit `frontend/app/admin/companies/page.tsx`. Two changes:

1. **In the companies table**, add a small badge or column showing the gallery count per company (e.g. "5 in gallery" with a folder icon). Click navigates to the gallery panel for that company.

2. **In the company edit dialog**, add a new "Gallery" tab/section below the existing fields. Structure:

```
[Existing company fields: name, category, description, services, etc.]

────────────── Gallery ──────────────

[+ Add from media library]                        N items · M active

┌────────────────────────────────────────────────────────────────────┐
│ ⋮⋮  [thumb]  Caption: "Inside the Lusail packing line"   [Active] │
│      Original: lusail-line.jpg · Image · 2.3 MB              [✕]  │
├────────────────────────────────────────────────────────────────────┤
│ ⋮⋮  [thumb]  Caption: "Team photo, 2026"                 [Active] │
│      Original: team-2026.jpg · Image · 1.8 MB                [✕]  │
└────────────────────────────────────────────────────────────────────┘
```

- Drag handle (`⋮⋮`) on the left for reordering using `@dnd-kit/sortable` (check if it's already a dep from the FeaturedMedia work; if not, add it)
- Thumbnail (image preview or video poster fallback) at ~64×48 px
- Inline editable caption (textarea, autosaves on blur via PATCH)
- Active toggle (PATCH on click)
- Delete button (DELETE — confirm via inline dialog)
- "+ Add from media library" opens a picker modal (see below)
- After a drag-end event, POST the new order to `/admin/cms/companies/{id}/media/reorder`
- Pinned-first ordering is NOT in this PR; pure display_order ascending

3. **Media picker modal** (reusable component, lives at `frontend/components/admin/media-picker.tsx` — extract for reuse by the Featured Media admin too if it's not already extracted):

```
┌─────────────────── Add from library ───────────────────┐
│ [Search] [Filter: Images / Videos / All]               │
│                                                         │
│ ┌────┬────┬────┬────┬────┐                             │
│ │ ☐  │ ✓  │ ☐  │ ☐  │ ✓  │  ← thumbnails, select boxes │
│ └────┴────┴────┴────┴────┘                             │
│ [Showing 20 of 247 · Load more]                        │
│                                                         │
│ 2 selected                          [Cancel] [Add 2]    │
└─────────────────────────────────────────────────────────┘
```

- Multi-select; on "Add" sends N POSTs in parallel (or use a bulk endpoint if you add one — not required for v1)
- Items already in the current company's gallery are visually marked (greyed out + "Already added" label) and unselectable
- Search field hits the existing `/admin/cms/media?q=...&kind=...` endpoint

# Frontend — rewire the public page

Edit `frontend/app/(public)/companies/[slug]/page.tsx` lines 107-123:

Replace the 6-gradient placeholder loop with the real gallery:

```tsx
{company.gallery && company.gallery.length > 0 ? (
  <>
    <h3 className="mt-8 text-base font-semibold">Gallery</h3>
    <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
      {company.gallery
        .filter((item) => item.is_active)
        .map((item) => (
          <CompanyGalleryTile key={item.id} item={item} />
        ))}
    </div>
  </>
) : (
  <EmptyGalleryState companyName={company.name} />
)}
```

Create two new components:

- `frontend/components/site/company-gallery-tile.tsx` — renders an image OR video tile, click opens a lightbox (use the existing image-viewer if one exists; otherwise just open in new tab — full lightbox is out of scope)
- `frontend/components/site/empty-gallery-state.tsx` — renders a muted message like *"Photos coming soon — we're putting together the visuals for [Company Name]."* with a small `ImageOff` icon. NO gradient placeholders, NO "Phase 5 follow-up" text

DELETE the placeholder text from line 120-123 entirely. The empty state replaces it.

# Frontend — Gallery section type-safe import

Make sure `cn` and other imports stay valid after the rewrite. The `company.accent` no longer drives the gallery — it stays in use elsewhere on the page (the page header icon, for example), don't remove it from the data model.

# Seed data

Update `backend/app/scripts/seed_cms.py`:

- After companies and media assets are seeded, insert ~3 sample CompanyMedia rows per company (or whatever's reasonable — at least one company should have a populated gallery so the empty state vs. populated state can both be tested on the public site without manual admin work)
- Seed must be idempotent: skip insert if a CompanyMedia already exists for that `(company_id, media_asset_id)` pair (UniqueConstraint will catch it but check first to avoid noisy errors)

# Tests

Backend (pytest, in `backend/tests/`):
- `test_company_media_crud`: create, list, patch, delete round-trip
- `test_company_media_unique_pair`: adding the same media_asset to the same company twice returns 409
- `test_company_media_reorder`: send 5 items in a new order, confirm display_order persists and list returns in correct order
- `test_company_media_cascade_company`: deleting a Company cascades to its CompanyMedia rows
- `test_company_media_cascade_media`: deleting a MediaAsset cascades to its CompanyMedia rows
- `test_company_read_includes_gallery`: GET /companies/{slug} returns gallery array, ordered by display_order, filtered to is_active=True
- `test_alembic_upgrade_downgrade`: clean rollback

Frontend (RTL or smoke):
- Snapshot for the public CompanyGalleryTile (image + video variants)
- Snapshot for the EmptyGalleryState
- Admin picker modal disables already-added items
- Drag-end fires the reorder POST with the correct payload

# Acceptance criteria

- Public /companies/[slug] page shows the assigned gallery items (NOT gradient placeholders, NOT the "Phase 5 follow-up" text)
- Companies with no gallery show the friendly empty state — never raw placeholders, never an error
- Admin → Companies → Edit a company → Gallery section can: add from library, reorder via drag, edit captions inline, toggle active, delete
- The same media asset can be added to two different companies independently (with different captions and ordering)
- Adding the same asset twice to one company returns a clear 409 with message "Already in this company's gallery"
- Deleting a company removes its gallery rows; deleting a media asset removes it from all companies' galleries (cascade verified by test)
- Marketing can drag-reorder and changes appear on the public page within the revalidate window (~60 s)
- All audit log entries appear correctly
- All tests pass; `pytest`, `npm test`, `npm run build` clean
- Lighthouse accessibility = 100 on a populated company page
- No console warnings, no hydration mismatch

# Out of scope for this PR

- Lightbox / image viewer for the public gallery — clicking a tile can open in new tab for now
- Per-company hero photo (the existing `featured_image_url` already handles this — don't fold it into the gallery)
- Per-gallery-item alt text override (uses `media_asset.alt_text`; if marketing needs per-context alt text later, add an `alt_text_override` column then)
- Image cropping or focal point per gallery item
- Bulk reorder via JSON import
- Pinning items to the top — pure display_order in this PR; pinning is a follow-up if marketing asks for it
- Replacing the existing /admin/media gallery with the picker modal — the picker is opened from a company context only; the standalone /admin/media page stays for upload and library management
- Translations / RTL on captions

# Working agreement

- Plan first. Print a numbered file-by-file plan and wait for me to confirm before editing
- Atomic commits: (1) backend model + relationship + schemas, (2) Alembic migration, (3) admin CRUD endpoints + audit, (4) public endpoint extension, (5) frontend types, (6) MediaPicker component, (7) Company admin Gallery section, (8) public page rewire + new components + placeholder deletion, (9) seed updates, (10) tests
- Run `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
- Run `pytest && npm test && npm run build` before declaring done. Paste output of each
- If any spec here conflicts with code you find in the repo, surface it before changing
````

---

## Notes on using this prompt

Paste the entire fenced block above (everything between the triple backticks under `## PROMPT TO PASTE INTO CLAUDE CODE`) into a fresh Claude Code session. Claude Code will read the relevant files, print a plan, and wait for your confirmation before editing.

The architectural decision here is the **many-to-many junction table**, which means one photo lives once in the central media library but can appear in multiple companies' galleries with a different caption each time. The alternative (a `company_id` FK directly on `cms_media_assets`) was rejected because group photos genuinely span multiple PUG brands — forcing them to be uploaded once per company would waste storage, duplicate edits, and break the "single source of truth" principle the central media library exists to enforce.

The picker modal (`components/admin/media-picker.tsx`) is deliberately extracted as a reusable primitive — if the `FeaturedMedia` admin from the earlier prompt has already been shipped, it should adopt the same picker rather than each module building its own. If `FeaturedMedia` hasn't shipped yet, this PR introduces the primitive and `FeaturedMedia` adopts it in a follow-up.

The `featured_image_url` field on `Company` stays separate and unchanged — that's the hero photo for the company card on the listing page and the top of the detail page. The gallery is a separate concept (multiple photos shown lower on the detail page). Mixing them would cause confusion ("is this photo the hero or a gallery item?") so they're kept apart by design.

The UniqueConstraint on `(company_id, media_asset_id)` prevents accidental duplicates. If marketing has a genuine need to show the same photo twice in one gallery (extremely unusual), that's a UX conversation, not a schema change.

The empty state ("Photos coming soon — we're putting together the visuals for [Company Name]") is friendly and on-brand rather than a placeholder grid that lies about what's available. This matters because most companies will start with empty galleries before marketing gets around to assigning photos.

---

*Generated as a planning document for the Paris United Group company gallery rebuild. No source code in the project was modified.*
