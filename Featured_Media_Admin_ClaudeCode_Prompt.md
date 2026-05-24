# Featured Media admin module — Claude Code Implementation Prompt

> Copy the section under **PROMPT TO PASTE INTO CLAUDE CODE** into a fresh Claude Code session that has this repo open. Self-contained — covers the model, schema, migration, endpoints, types, admin page, public page rewire, dummy-data removal, tests, and acceptance criteria.

---

## Context for the human

The public `/media` page currently has two sections: "Recent uploads" (admin-managed via `/admin/media`, reads real `MediaAsset` rows from `cms_media_assets`) and "Around the group" (a curated showcase with category filters — but the 12 tiles are hardcoded placeholder data in `frontend/lib/dummy-data/media.ts`, with no admin editor).

This prompt builds the missing piece: a proper **Featured Media** admin module that lets marketing curate the "Around the group" grid by picking from already-uploaded `MediaAsset` rows, ordering them by drag-and-drop, overriding the displayed title and category, scheduling publish/unpublish windows, and pinning items to the top — then rewires the public page to consume the new endpoint and deletes the dummy data file.

The same `FeaturedMedia` primitive is reusable for other curated zones across the site later (homepage news, store-of-the-month, careers highlights). Designed as one curation engine for many surfaces.

---

## PROMPT TO PASTE INTO CLAUDE CODE

````
You are working in the Paris United Group monorepo. Read CLAUDE.md, the docs/ folder, and the files I list below before touching code. Print a numbered file-by-file plan and wait for confirmation before editing.

# Goal

Replace the hardcoded "Around the group" placeholder data on the public /media page with a curated, admin-managed module that pulls from already-uploaded MediaAsset rows. Marketing should be able to pick, order, retitle, recategorise, schedule, and pin featured items. Ship the change end-to-end and delete the dummy data stub.

# Current state to reproduce mentally before editing

- Backend model: `MediaAsset` (table `cms_media_assets`) — already exists, created in migration `20260524_0005_media_pages.py`. Has `id, kind, filename, url, mime_type, file_size, file_hash, width, height, duration_seconds, title, alt_text, tags, uploaded_by_id, created_at, updated_at`.
- Backend admin CRUD lives in `app/api/endpoints/admin_cms.py` — follow the HeroSlide pattern (search the file for "hero-slides" to see the shape: list / create / patch / delete + audit log).
- Backend public reads live in `app/api/endpoints/public.py`.
- Frontend admin pages live in `frontend/app/admin/<resource>/page.tsx` — pattern is set by `app/admin/hero-slides/page.tsx` and `app/admin/media/page.tsx`.
- Frontend types mirror Pydantic in `frontend/lib/admin/types.ts`.
- Public page to rewire: `frontend/app/(public)/media/page.tsx` — the "Around the group" Section currently consumes `getMedia()` from `lib/dummy-data/media.ts`.
- Component to keep but feed real data: `frontend/components/site/media-gallery.tsx`.
- Latest Alembic migration: `20260524_0006_leadership_homepage.py`. New migration must use `down_revision = "20260524_0006"`.

# Backend — model

Add to `backend/app/models/cms.py`:

```python
class FeaturedMedia(Base, TimestampMixin):
    __tablename__ = "cms_featured_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_asset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cms_media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Curated overrides (null = fall back to the underlying MediaAsset field)
    display_title: Mapped[Optional[str]] = mapped_column(String(255))
    display_description: Mapped[Optional[str]] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="stores"
    )  # 'events' | 'stores' | 'campaigns' | 'team'
    # Layout hints for the masonry grid
    tile_size: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="square"
    )  # 'square' | 'wide' | 'tall'
    accent_gradient: Mapped[Optional[str]] = mapped_column(String(255))
    # Curation controls
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", index=True
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    publish_from: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    publish_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    # Optional deep link (news article slug, company slug, external URL)
    link_href: Mapped[Optional[str]] = mapped_column(String(500))
    link_label: Mapped[Optional[str]] = mapped_column(String(120))

    # Relationship for convenient eager loading
    media_asset: Mapped["MediaAsset"] = relationship(
        "MediaAsset", lazy="joined"
    )
```

Add `FeaturedMedia` to `app/models/__init__.py` exports.

# Backend — schemas

Add to `backend/app/schemas/cms.py`:

```python
FeaturedMediaCategory = Literal["events", "stores", "campaigns", "team"]
FeaturedMediaTileSize = Literal["square", "wide", "tall"]


class FeaturedMediaBase(BaseModel):
    media_asset_id: int
    display_title: Optional[str] = Field(default=None, max_length=255)
    display_description: Optional[str] = Field(default=None, max_length=500)
    category: FeaturedMediaCategory = "stores"
    tile_size: FeaturedMediaTileSize = "square"
    accent_gradient: Optional[str] = Field(default=None, max_length=255)
    display_order: int = 0
    is_pinned: bool = False
    is_active: bool = True
    publish_from: Optional[datetime] = None
    publish_until: Optional[datetime] = None
    link_href: Optional[str] = Field(default=None, max_length=500)
    link_label: Optional[str] = Field(default=None, max_length=120)


class FeaturedMediaCreate(FeaturedMediaBase):
    pass


class FeaturedMediaUpdate(BaseModel):
    display_title: Optional[str] = None
    display_description: Optional[str] = None
    category: Optional[FeaturedMediaCategory] = None
    tile_size: Optional[FeaturedMediaTileSize] = None
    accent_gradient: Optional[str] = None
    display_order: Optional[int] = None
    is_pinned: Optional[bool] = None
    is_active: Optional[bool] = None
    publish_from: Optional[datetime] = None
    publish_until: Optional[datetime] = None
    link_href: Optional[str] = None
    link_label: Optional[str] = None


class FeaturedMediaReorderItem(BaseModel):
    id: int
    display_order: int


class FeaturedMediaReorderRequest(BaseModel):
    items: List[FeaturedMediaReorderItem]


class FeaturedMediaRead(FeaturedMediaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    # Inline the resolved asset so the frontend doesn't need a second call
    media_asset: MediaAssetRead
```

# Backend — migration

Create `backend/migrations/versions/20260524_0007_featured_media.py`:

- `revision = "20260524_0007"`, `down_revision = "20260524_0006"`
- `upgrade()` creates the `cms_featured_media` table with all columns above plus the FK to `cms_media_assets(id) ON DELETE CASCADE`, plus indexes on `media_asset_id` and `display_order`
- `downgrade()` drops the table

# Backend — admin CRUD endpoints

Add to `backend/app/api/endpoints/admin_cms.py` — follow the HeroSlide pattern (audit log on every mutation):

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/admin/cms/featured-media` | `List[FeaturedMediaRead]` | order by `is_pinned DESC, display_order ASC, id ASC` |
| POST | `/admin/cms/featured-media` | `FeaturedMediaRead` 201 | validate `media_asset_id` exists |
| PATCH | `/admin/cms/featured-media/{id}` | `FeaturedMediaRead` | |
| DELETE | `/admin/cms/featured-media/{id}` | 204 | |
| POST | `/admin/cms/featured-media/reorder` | `List[FeaturedMediaRead]` | accept `FeaturedMediaReorderRequest`, persist all `display_order` values in one transaction |

Audit actions: `cms.featured_media.create`, `.update`, `.delete`, `.reorder`.

# Backend — public read endpoint

Add to `backend/app/api/endpoints/public.py`:

```
GET /api/v1/featured-media
```

Returns `List[FeaturedMediaRead]` filtered to `is_active=True` and within the publish window (`publish_from <= now <= publish_until`, treating nulls as open-ended). Order by `is_pinned DESC, display_order ASC`. Optional query param `category` to filter, optional `limit` (default 50, max 200).

# Frontend — types

Add to `frontend/lib/admin/types.ts`:

```ts
export type FeaturedMediaCategory = "events" | "stores" | "campaigns" | "team";
export type FeaturedMediaTileSize = "square" | "wide" | "tall";

export interface FeaturedMediaItem {
  id: number;
  media_asset_id: number;
  display_title: string | null;
  display_description: string | null;
  category: FeaturedMediaCategory;
  tile_size: FeaturedMediaTileSize;
  accent_gradient: string | null;
  display_order: number;
  is_pinned: boolean;
  is_active: boolean;
  publish_from: string | null;
  publish_until: string | null;
  link_href: string | null;
  link_label: string | null;
  created_at: string;
  updated_at: string;
  media_asset: MediaAsset;
}

export interface FeaturedMediaReorderPayload {
  items: { id: number; display_order: number }[];
}
```

# Frontend — public API client

In `frontend/lib/public-api.ts` add:

```ts
export async function getFeaturedMedia(opts?: {
  category?: FeaturedMediaCategory;
  limit?: number;
}): Promise<FeaturedMediaItem[]>
```

Same fetch pattern as `getMediaGallery()`. 60-second `next: { revalidate: 60 }`.

# Frontend — admin page

Create `frontend/app/admin/featured-media/page.tsx` modeled on `app/admin/media/page.tsx`. Layout:

- Top of page: section header "Featured media (Around the group)" with description "Curate the homepage and /media page showcase. Drag tiles to reorder. Items only appear publicly when active and within their publish window."
- Right side of header: a "+ Add featured item" button that opens a media picker modal — the modal lists every MediaAsset (paginated, searchable by title/filename/tags) and on click, POSTs a new FeaturedMedia row with sensible defaults (category='stores', tile_size='square', display_order = max + 10)
- Main area: vertical list of cards (NOT the masonry grid — admin needs to see all items in linear order). Each card shows:
  - Drag handle on the left
  - Thumbnail (image preview or video poster)
  - Display title (editable inline) with fallback to media asset original_name
  - Category select dropdown (Events / Stores / Campaigns / Team)
  - Tile size select (Square / Wide / Tall)
  - Pin toggle, Active toggle
  - Publish window date inputs (publish_from, publish_until)
  - Link href + label inputs
  - Delete button
- Drag-and-drop: use `@dnd-kit/sortable` (it's already in package.json — check first; if not, add it). On drop, compute new `display_order` values (step 10) and POST `/admin/cms/featured-media/reorder` with the full new order
- Show pinned items first with a small "PINNED" badge — they sort independently above the unpinned ones
- Filter chips at top: All / Events / Stores / Campaigns / Team — purely a view filter for the admin, doesn't change persisted data
- Toast on every successful save / reorder, error toast on failure

Add a sidebar entry in `components/admin/sidebar.tsx`: link to `/admin/featured-media`, label "Featured media", group with the existing Media gallery link.

# Frontend — rewire the public page

Edit `frontend/app/(public)/media/page.tsx`:

- Remove the import of `getMedia` from `@/lib/dummy-data/media`
- Add `getFeaturedMedia` to the existing `getMediaGallery` Promise.all
- Pass the featured items to `<MediaGallery items={featured} />` after transforming them into the shape `MediaGallery` expects (likely needs a small adapter — keep the adapter inline at the top of the file, do not modify `MediaGallery` itself unless the shape change is trivial)
- If the existing `MediaGallery` component depends on `MediaItem` from the dummy data, refactor it to take a more flexible interface (URL, kind, title, description, category, tile_size, accent gradient) — define this interface in `lib/types/media-gallery.ts` so both the dummy adapter and the new featured adapter conform

# Frontend — delete the stub

Delete `frontend/lib/dummy-data/media.ts` entirely. Grep for any other importers — there should be none after the rewire. If grep finds any, surface them in the plan before deleting.

# Seed data

Update `backend/app/scripts/seed_cms.py` to insert ~6 sample FeaturedMedia rows after the MediaAsset seed runs. Each row should reference an existing media_asset_id from the seeded uploads. Mix of categories and tile sizes so the public grid demonstrates the layout.

Seed must be idempotent: skip insert if a FeaturedMedia already exists for that media_asset_id.

# Tests

Backend (pytest, in `backend/tests/`):
- `test_featured_media_crud`: create, list, patch, delete round-trip
- `test_featured_media_reorder`: send 5 items in a new order, confirm display_order persists and list returns in correct order
- `test_featured_media_publish_window`: row with `publish_until` in the past should be excluded from the public endpoint
- `test_featured_media_pinned_first`: pinned items appear before unpinned regardless of display_order
- `test_featured_media_cascade_delete`: deleting a MediaAsset cascades to its FeaturedMedia row
- `test_alembic_upgrade_downgrade`: upgrade then downgrade leaves no residual table

Frontend (RTL or smoke):
- Snapshot for the admin page rendering an empty state and a 3-item state
- Adapter test: a FeaturedMediaItem with `display_title=null` falls back to `media_asset.original_name`

# Acceptance criteria

- Public /media page "Around the group" section shows the seeded featured items — NOT the deleted dummy data
- Admin /admin/featured-media page can add, reorder by drag, edit, pin, schedule, and delete items, and changes appear on the public page within 60 s (the revalidate window)
- Category filter chips on the public page filter the featured items correctly
- `frontend/lib/dummy-data/media.ts` no longer exists
- No console errors, no hydration warnings, no broken imports
- All new endpoints have audit log entries
- All tests pass; `pytest` and `npm test` clean
- `npm run build` completes without new warnings

# Out of scope for this PR

- Drag-and-drop on the public page (admin only)
- Bulk import / CSV upload for featured items
- Multiple curated zones (homepage news, store-of-the-month) — `FeaturedMedia` is designed to be extensible to a `zone` column later but this PR keeps it focused on the /media "Around the group" zone only
- Image cropping or focal point per featured item
- Translations / i18n on the display_title / display_description fields
- Public-facing analytics on which featured items get clicked

# Working agreement

- Plan first. Print a numbered file-by-file plan and wait for me to confirm before editing
- Make atomic commits per logical change (model, schema, migration, admin endpoints, public endpoint, types, admin page, public rewire, dummy deletion, tests, seed). Conventional commit prefixes
- Run `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` to verify the migration is reversible
- Run `pytest` and `npm test` and `npm run build` before declaring done. Paste the final output of each
- If anything in this spec conflicts with code you find in the repo, surface it before changing — don't guess
````

---

## Notes on using this prompt

Paste the entire fenced block above (everything between the triple backticks under `## PROMPT TO PASTE INTO CLAUDE CODE`) into a fresh Claude Code session. Claude Code will read the relevant files, print a plan, and wait for your confirmation before editing.

The `FeaturedMedia` table is deliberately separate from `MediaAsset` — your raw media library stays a flat list of every upload, and the curation layer is a thin overlay that references it. Deleting a `MediaAsset` cascades to its `FeaturedMedia` row (we don't want orphaned references on the public page), but deleting a `FeaturedMedia` row never touches the underlying upload.

The schema includes a `tile_size` field with three values (square / wide / tall) so your masonry grid keeps the visual variety the current dummy data has — without it, every tile would default to the same aspect ratio and the showcase would lose its rhythm.

The `publish_from` / `publish_until` fields mean campaigns like "Back to School 2026" can be scheduled to appear in August and disappear in October without anyone needing to remember to remove them — a small detail that pays back many times.

If you later want to reuse this primitive for other curated zones (homepage news, store-of-the-month, leadership highlights on the about page), add a single `zone` column to `cms_featured_media` and one `zone` query param to the public endpoint. The admin page can grow a zone selector at the top. That's a follow-up PR — out of scope here on purpose.
