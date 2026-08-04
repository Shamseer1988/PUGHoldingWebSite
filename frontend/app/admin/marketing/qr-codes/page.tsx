"use client";

/**
 * Marketing → QR Codes.
 *
 * Divisions (branches) own permanent QR codes. The code's slug — and
 * therefore its printed artwork — never changes; only the target link
 * does. The UI leans hard on that distinction: the permanent URL is
 * presented as fixed and copyable, while "Update link" is the loud,
 * always-available action.
 */

import * as React from "react";
import {
  Building2,
  CheckCircle2,
  ChevronDown,
  Copy,
  Download,
  ExternalLink,
  Eye,
  EyeOff,
  History,
  Loader2,
  Pencil,
  Plus,
  QrCode,
  Trash2,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import { qrUrlDisplay, qrUrlFor } from "@/lib/marketing/qr-url";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types — mirror app/schemas/marketing_qr.py
// ---------------------------------------------------------------------------

type TargetKind =
  | "catalogue"
  | "campaign"
  | "youtube"
  | "instagram"
  | "facebook"
  | "tiktok"
  | "website"
  | "other";

interface QrCodeRead {
  id: number;
  division_id: number;
  slug: string;
  label: string;
  target_url: string | null;
  target_kind: TargetKind;
  fallback_url: string | null;
  is_active: boolean;
  sort_order: number;
  scan_count: number;
  last_scan_at: string | null;
  target_updated_at: string | null;
  created_at: string;
  updated_at: string;
}

interface DivisionRead {
  id: number;
  slug: string;
  name: string;
  city: string | null;
  description: string | null;
  logo_url: string | null;
  fallback_url: string | null;
  is_active: boolean;
  is_public: boolean;
  sort_order: number;
  hero_image_url: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  whatsapp: string | null;
  opening_hours: string | null;
  maps_url: string | null;
  facebook_url: string | null;
  instagram_url: string | null;
  tiktok_url: string | null;
  youtube_url: string | null;
  snapchat_url: string | null;
  x_url: string | null;
  created_at: string;
  updated_at: string;
  qr_codes: QrCodeRead[];
}

interface DivisionListResponse {
  items: DivisionRead[];
  total: number;
}

interface QrTargetHistoryEntry {
  changed_at: string;
  actor_email: string | null;
  from_url: string | null;
  to_url: string | null;
}

interface QrCodeAnalytics {
  qr_code_id: number;
  total_scans: number;
  scans_last_30_days: number;
  last_scan_at: string | null;
  daily: { day: string; scans: number }[];
  devices: { device: string; scans: number }[];
  target_history: QrTargetHistoryEntry[];
}

const DIVISIONS = "/admin/marketing/divisions";
const QR_CODES = "/admin/marketing/qr-codes";

const TARGET_KINDS: { value: TargetKind; label: string }[] = [
  { value: "catalogue", label: "Catalogue" },
  { value: "campaign", label: "Offer campaign" },
  { value: "youtube", label: "YouTube video" },
  { value: "instagram", label: "Instagram post" },
  { value: "facebook", label: "Facebook post" },
  { value: "tiktok", label: "TikTok" },
  { value: "website", label: "Website page" },
  { value: "other", label: "Other" },
];

/** Print sizes offered for download. 2048 ≈ 6.8" at 300 DPI. */
const QR_SIZES = [512, 1024, 2048];

function kindLabel(kind: TargetKind): string {
  return TARGET_KINDS.find((k) => k.value === kind)?.label ?? "Other";
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function QrCodesPage() {
  const [divisions, setDivisions] = React.useState<DivisionRead[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [creatingDivision, setCreatingDivision] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setError(null);
    try {
      const data = await adminApi.get<DivisionListResponse>(DIVISIONS);
      setDivisions(data.items);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <AdminShell
      title="QR Codes"
      description="One permanent QR code per branch. The printed code never changes — update where it points any time and every existing scan follows the new link."
      actions={
        <Button size="sm" onClick={() => setCreatingDivision(true)}>
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New division</span>
        </Button>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {creatingDivision && (
        <DivisionForm
          onCancel={() => setCreatingDivision(false)}
          onSaved={async (name) => {
            setCreatingDivision(false);
            setToast(`Created ${name}`);
            await refresh();
          }}
          onError={setError}
        />
      )}

      {divisions === null && (
        <div className="py-16 text-center text-sm text-muted-foreground">
          <Loader2 className="mx-auto h-5 w-5 animate-spin" />
        </div>
      )}

      {divisions?.length === 0 && (
        <div className="rounded-2xl border border-dashed border-border/60 bg-card/50 p-10 text-center">
          <Building2 className="mx-auto h-8 w-8 text-muted-foreground/60" />
          <h2 className="mt-3 text-base font-semibold">No divisions yet</h2>
          <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
            Create one per branch — Al Atiyah, Al Khor, Al Wakra, Umm Salal.
            Each gets its own permanent QR code you can print once and re-point
            whenever the offer changes.
          </p>
          <Button className="mt-4" size="sm" onClick={() => setCreatingDivision(true)}>
            <Plus className="h-4 w-4" />
            New division
          </Button>
        </div>
      )}

      <div className="space-y-4">
        {divisions?.map((division) => (
          <DivisionCard
            key={division.id}
            division={division}
            onChanged={refresh}
            onToast={setToast}
            onError={setError}
          />
        ))}
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Division card
// ---------------------------------------------------------------------------

function DivisionCard({
  division,
  onChanged,
  onToast,
  onError,
}: {
  division: DivisionRead;
  onChanged: () => Promise<void>;
  onToast: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [open, setOpen] = React.useState(true);
  const [editing, setEditing] = React.useState(false);
  const [addingQr, setAddingQr] = React.useState(false);

  async function toggleActive() {
    try {
      await adminApi.patch(`${DIVISIONS}/${division.id}`, {
        is_active: !division.is_active,
      });
      onToast(
        division.is_active
          ? `${division.name} deactivated — its codes now use the fallback link`
          : `${division.name} reactivated`,
      );
      await onChanged();
    } catch (err) {
      onError((err as AdminApiError).message);
    }
  }

  async function remove() {
    if (
      !confirm(
        `Delete ${division.name} and its ${division.qr_codes.length} QR code(s)?\n\n` +
          `Any printed code for this division will stop working immediately — ` +
          `there will be no row left to read a fallback link from.\n\n` +
          `Deactivating instead keeps printed codes alive and pointing at the fallback.`,
      )
    ) {
      return;
    }
    try {
      await adminApi.delete(`${DIVISIONS}/${division.id}`);
      onToast(`Deleted ${division.name}`);
      await onChanged();
    } catch (err) {
      onError((err as AdminApiError).message);
    }
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-border/60 bg-card">
      <header className="flex flex-wrap items-center gap-3 border-b border-border/60 bg-background/40 px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          aria-expanded={open}
        >
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
              !open && "-rotate-90",
            )}
          />
          <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0">
            <span
              className={cn(
                "block truncate font-semibold",
                !division.is_active && "text-muted-foreground line-through",
              )}
            >
              {division.name}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              {division.city ? `${division.city} · ` : ""}
              {division.qr_codes.length} QR code
              {division.qr_codes.length === 1 ? "" : "s"}
            </span>
          </span>
        </button>

        {!division.is_active && (
          <Badge variant="warning">Inactive</Badge>
        )}

        <div className="flex items-center gap-1">
          <Button size="sm" variant="ghost" onClick={() => setAddingQr(true)} title="Add QR code">
            <Plus className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setEditing(true)}
            title="Edit branch details (not the QR links)"
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void toggleActive()}
            title={division.is_active ? "Deactivate" : "Reactivate"}
          >
            {division.is_active ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void remove()}
            title="Delete division"
            className="text-rose-600 hover:text-rose-700 dark:text-rose-300"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {editing && (
        <div className="border-b border-border/60 p-4">
          <DivisionForm
            division={division}
            onCancel={() => setEditing(false)}
            onSaved={async (name) => {
              setEditing(false);
              onToast(`Updated ${name}`);
              await onChanged();
            }}
            onError={onError}
          />
        </div>
      )}

      {addingQr && (
        <div className="border-b border-border/60 p-4">
          <QrCreateForm
            divisionId={division.id}
            onCancel={() => setAddingQr(false)}
            onSaved={async (label) => {
              setAddingQr(false);
              onToast(`Added "${label}"`);
              await onChanged();
            }}
            onError={onError}
          />
        </div>
      )}

      {open && (
        <div className="divide-y divide-border/60">
          {division.qr_codes.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">
              No QR codes in this division yet.
            </p>
          )}
          {division.qr_codes.map((qr) => (
            <QrRow
              key={qr.id}
              qr={qr}
              divisionActive={division.is_active}
              onChanged={onChanged}
              onToast={onToast}
              onError={onError}
            />
          ))}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// QR row
// ---------------------------------------------------------------------------

function QrRow({
  qr,
  divisionActive,
  onChanged,
  onToast,
  onError,
}: {
  qr: QrCodeRead;
  divisionActive: boolean;
  onChanged: () => Promise<void>;
  onToast: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [editing, setEditing] = React.useState(false);
  const [showHistory, setShowHistory] = React.useState(false);
  const [size, setSize] = React.useState(1024);

  const permanentUrl = qrUrlFor(qr.slug);
  // A code is only actually resolving to its target when both it and
  // its division are active — surface that, so an operator isn't
  // puzzled by a code that looks enabled but serves the fallback.
  const live = qr.is_active && divisionActive && Boolean(qr.target_url);

  async function copy() {
    try {
      await navigator.clipboard.writeText(permanentUrl);
      onToast(`Copied ${permanentUrl}`);
    } catch {
      onToast("Could not access the clipboard — copy the URL by hand.");
    }
  }

  async function download() {
    try {
      await adminApi.downloadFile(
        `${QR_CODES}/${qr.id}/qr-code.png?size=${size}&download=true`,
        `qr-${qr.slug}-${size}.png`,
        "GET",
      );
    } catch (err) {
      onError((err as AdminApiError).message);
    }
  }

  async function toggleActive() {
    try {
      await adminApi.patch(`${QR_CODES}/${qr.id}`, { is_active: !qr.is_active });
      onToast(qr.is_active ? `Disabled "${qr.label}"` : `Enabled "${qr.label}"`);
      await onChanged();
    } catch (err) {
      onError((err as AdminApiError).message);
    }
  }

  async function remove() {
    if (
      !confirm(
        `Delete the "${qr.label}" QR code?\n\n` +
          `Every printed copy of this code stops working immediately and cannot ` +
          `be recovered — the slug "${qr.slug}" is released.\n\n` +
          `Disabling it instead keeps printed codes working via the fallback link.`,
      )
    ) {
      return;
    }
    try {
      await adminApi.delete(`${QR_CODES}/${qr.id}`);
      onToast(`Deleted "${qr.label}"`);
      await onChanged();
    } catch (err) {
      onError((err as AdminApiError).message);
    }
  }

  return (
    <div
      className={cn(
        "p-4 transition-colors",
        // Highlight the row whose editor is open. With several codes
        // stacked under one division, an unanchored form panel leaves
        // "which code am I editing?" ambiguous.
        editing && "bg-primary/[0.04] ring-1 ring-inset ring-primary/30",
      )}
    >
      <div className="flex flex-wrap items-start gap-4">
        <QrPreview qrId={qr.id} slug={qr.slug} />

        <div className="min-w-[16rem] flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{qr.label}</h3>
            <Badge variant={live ? "success" : "muted"}>
              {live ? "Live" : qr.target_url ? "Fallback" : "No link set"}
            </Badge>
            <Badge variant="outline">{kindLabel(qr.target_kind)}</Badge>
          </div>

          {/* Permanent URL — presented as immutable, because it is. */}
          <div className="flex items-center gap-2">
            <code className="truncate rounded-md bg-muted px-2 py-1 font-mono text-xs">
              {qrUrlDisplay(qr.slug)}
            </code>
            <Button size="sm" variant="ghost" onClick={() => void copy()} title="Copy permanent link">
              <Copy className="h-3.5 w-3.5" />
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Permanent — printed artwork keeps working when you change the link below.
          </p>

          <div className="text-sm">
            <span className="text-muted-foreground">Currently points to: </span>
            {qr.target_url ? (
              <a
                href={qr.target_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex max-w-full items-center gap-1 break-all text-primary hover:underline"
              >
                {qr.target_url}
                <ExternalLink className="h-3 w-3 shrink-0" />
              </a>
            ) : (
              <span className="italic text-muted-foreground">nothing yet</span>
            )}
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>
              <strong className="tabular-nums text-foreground">
                {qr.scan_count.toLocaleString()}
              </strong>{" "}
              scan{qr.scan_count === 1 ? "" : "s"}
            </span>
            {qr.last_scan_at && (
              <span>Last scan {new Date(qr.last_scan_at).toLocaleDateString()}</span>
            )}
            {qr.target_updated_at && (
              <span>Link updated {new Date(qr.target_updated_at).toLocaleDateString()}</span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-stretch gap-2">
          <Button
            size="sm"
            variant={editing ? "outline" : "default"}
            onClick={() => setEditing((v) => !v)}
            title={`Edit "${qr.label}" — link, type, label and fallback`}
          >
            <Pencil className="h-3.5 w-3.5" />
            {editing ? "Close editor" : "Update link"}
          </Button>
          <div className="flex items-center gap-1">
            <Select
              value={String(size)}
              onChange={(e) => setSize(Number(e.target.value))}
              className="h-8 w-[7.5rem] text-xs"
              aria-label="QR download size"
            >
              {QR_SIZES.map((s) => (
                <option key={s} value={s}>
                  {s} × {s} px
                </option>
              ))}
            </Select>
            <Button size="sm" variant="outline" onClick={() => void download()} title="Download PNG">
              <Download className="h-3.5 w-3.5" />
            </Button>
          </div>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="flex-1"
              onClick={() => setShowHistory((v) => !v)}
              title="Scan analytics and link history"
            >
              <History className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => void toggleActive()}
              title={qr.is_active ? "Disable" : "Enable"}
            >
              {qr.is_active ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => void remove()}
              title="Delete"
              className="text-rose-600 hover:text-rose-700 dark:text-rose-300"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>

      {editing && (
        <div className="mt-4">
          <QrEditForm
            qr={qr}
            onCancel={() => setEditing(false)}
            onSaved={async () => {
              setEditing(false);
              onToast(`Updated "${qr.label}"`);
              await onChanged();
            }}
            onError={onError}
          />
        </div>
      )}

      {showHistory && <QrAnalyticsPanel qrId={qr.id} onError={onError} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// QR preview — authenticated image fetch
// ---------------------------------------------------------------------------

function QrPreview({ qrId, slug }: { qrId: number; slug: string }) {
  const [src, setSrc] = React.useState<string | null>(null);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    void (async () => {
      try {
        const url = await adminApi.fetchObjectUrl(
          `${QR_CODES}/${qrId}/qr-code.png?size=512`,
        );
        if (cancelled) {
          // Unmounted mid-flight — revoke immediately so the blob
          // doesn't outlive the component.
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [qrId]);

  return (
    <div className="flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-background">
      {src ? (
        // ``src`` is a blob: URL from an authenticated fetch — next/image
        // can't send the Bearer header the endpoint requires, and has
        // nothing to optimise on an already-in-memory blob.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={`QR code for ${slug}`} className="h-full w-full object-contain" />
      ) : failed ? (
        <QrCode className="h-8 w-8 text-muted-foreground/40" />
      ) : (
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Analytics panel
// ---------------------------------------------------------------------------

function QrAnalyticsPanel({
  qrId,
  onError,
}: {
  qrId: number;
  onError: (msg: string) => void;
}) {
  const [data, setData] = React.useState<QrCodeAnalytics | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const body = await adminApi.get<QrCodeAnalytics>(
          `${QR_CODES}/${qrId}/analytics?days=30`,
        );
        if (!cancelled) setData(body);
      } catch (err) {
        if (!cancelled) onError((err as AdminApiError).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [qrId, onError]);

  if (!data) {
    return (
      <div className="mt-4 rounded-xl border border-border/60 bg-background/50 p-4 text-center">
        <Loader2 className="mx-auto h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const peak = Math.max(1, ...data.daily.map((d) => d.scans));

  return (
    <div className="mt-4 grid gap-4 rounded-xl border border-border/60 bg-background/50 p-4 lg:grid-cols-2">
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Scans — last 30 days
        </h4>
        <p className="mt-1 text-2xl font-semibold tabular-nums">
          {data.scans_last_30_days.toLocaleString()}
        </p>

        {/* Bare CSS bar chart — 30 points with no interaction doesn't
            justify pulling in a charting library. */}
        <div className="mt-3 flex h-16 items-end gap-[2px]" aria-hidden="true">
          {data.daily.map((d) => (
            <div
              key={d.day}
              className="flex-1 rounded-sm bg-primary/25"
              style={{ height: `${Math.max(2, (d.scans / peak) * 100)}%` }}
              title={`${d.day}: ${d.scans}`}
            />
          ))}
        </div>
        <p className="sr-only">
          {data.daily.map((d) => `${d.day}: ${d.scans} scans`).join(", ")}
        </p>

        {data.devices.length > 0 && (
          <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {data.devices.map((d) => (
              <div key={d.device} className="flex gap-1">
                <dt className="capitalize text-muted-foreground">{d.device}:</dt>
                <dd className="font-medium tabular-nums">{d.scans}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Link history
        </h4>
        {data.target_history.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            This code&apos;s link hasn&apos;t been changed yet.
          </p>
        ) : (
          <ol className="mt-2 space-y-2">
            {data.target_history.map((h, i) => (
              <li key={`${h.changed_at}-${i}`} className="text-xs">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-medium">
                    {new Date(h.changed_at).toLocaleString()}
                  </span>
                  {h.actor_email && (
                    <span className="text-muted-foreground">{h.actor_email}</span>
                  )}
                </div>
                <p className="break-all text-muted-foreground">
                  {h.from_url ? (
                    <>
                      {h.from_url} <span aria-hidden="true">→</span>{" "}
                    </>
                  ) : (
                    "Set to "
                  )}
                  <span className="text-foreground">{h.to_url}</span>
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Forms
// ---------------------------------------------------------------------------

function DivisionForm({
  division,
  onCancel,
  onSaved,
  onError,
}: {
  division?: DivisionRead;
  onCancel: () => void;
  onSaved: (name: string) => void | Promise<void>;
  onError: (msg: string) => void;
}) {
  const isEdit = Boolean(division);
  const [name, setName] = React.useState(division?.name ?? "");
  const [city, setCity] = React.useState(division?.city ?? "");
  const [logoUrl, setLogoUrl] = React.useState(division?.logo_url ?? "");
  const [heroUrl, setHeroUrl] = React.useState(division?.hero_image_url ?? "");
  const [fallbackUrl, setFallbackUrl] = React.useState(division?.fallback_url ?? "");
  const [isPublic, setIsPublic] = React.useState(division?.is_public ?? true);

  const [address, setAddress] = React.useState(division?.address ?? "");
  const [phone, setPhone] = React.useState(division?.phone ?? "");
  const [email, setEmail] = React.useState(division?.email ?? "");
  const [whatsapp, setWhatsapp] = React.useState(division?.whatsapp ?? "");
  const [hours, setHours] = React.useState(division?.opening_hours ?? "");
  const [mapsUrl, setMapsUrl] = React.useState(division?.maps_url ?? "");

  const [facebook, setFacebook] = React.useState(division?.facebook_url ?? "");
  const [instagram, setInstagram] = React.useState(division?.instagram_url ?? "");
  const [tiktok, setTiktok] = React.useState(division?.tiktok_url ?? "");
  const [youtube, setYoutube] = React.useState(division?.youtube_url ?? "");
  const [snapchat, setSnapchat] = React.useState(division?.snapchat_url ?? "");
  const [x, setX] = React.useState(division?.x_url ?? "");

  const [busy, setBusy] = React.useState(false);
  const [tab, setTab] = React.useState<"branch" | "storefront">("branch");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      // Blank inputs are sent as null, not "". The operator clearing a
      // field means "remove this", and the public page decides what to
      // render by null-checking each value.
      const clean = (v: string) => v.trim() || null;
      const body: Record<string, unknown> = {
        name: name.trim(),
        city: clean(city),
        logo_url: clean(logoUrl),
        hero_image_url: clean(heroUrl),
        fallback_url: clean(fallbackUrl),
        is_public: isPublic,
        address: clean(address),
        phone: clean(phone),
        email: clean(email),
        whatsapp: clean(whatsapp),
        opening_hours: clean(hours),
        maps_url: clean(mapsUrl),
        facebook_url: clean(facebook),
        instagram_url: clean(instagram),
        tiktok_url: clean(tiktok),
        youtube_url: clean(youtube),
        snapchat_url: clean(snapchat),
        x_url: clean(x),
      };
      if (isEdit) {
        await adminApi.patch(`${DIVISIONS}/${division!.id}`, body);
      } else {
        await adminApi.post(DIVISIONS, { ...body, create_primary_qr: true });
      }
      await onSaved(name.trim());
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  const branchSlug = division?.slug;

  return (
    <form
      onSubmit={submit}
      className="mb-4 rounded-xl border border-primary/30 bg-primary/[0.04] p-4"
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">
            {isEdit ? `Edit ${division!.name}` : "New division"}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {isEdit
              ? "Branch details only — renaming never changes its QR codes, so printed artwork stays valid. To change where a code points, use Update link on that code below."
              : "A permanent \"Primary\" QR code is created automatically. You can point it at a link now or later."}
          </p>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Two tabs so the required identity fields aren't buried under a
          long contact/social block the operator can fill in later. */}
      <div className="mb-3 flex gap-1 border-b border-border/60">
        {(
          [
            ["branch", "Branch"],
            ["storefront", "Public page"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cn(
              "-mb-px border-b-2 px-3 py-1.5 text-xs font-medium transition-colors",
              tab === key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "branch" && (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="division-name">Branch name</Label>
            <Input
              id="division-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Paris Hyper Market Al Attiya"
              required
              minLength={2}
              disabled={busy}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="division-city">City / area</Label>
            <Input
              id="division-city"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Industrial Area"
              disabled={busy}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="division-logo">Logo URL</Label>
            <Input
              id="division-logo"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="Stamped into the QR centre + page header"
              disabled={busy}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="division-fallback">Fallback link</Label>
            <Input
              id="division-fallback"
              type="url"
              value={fallbackUrl}
              onChange={(e) => setFallbackUrl(e.target.value)}
              placeholder="Leave blank to use this branch's offers page"
              disabled={busy}
            />
            <p className="text-[11px] text-muted-foreground">
              Where scans go if a code here is disabled or has no link. Left
              blank, they land on this branch&apos;s own offers page
              {branchSlug ? ` (/offers/${branchSlug})` : ""} — which is
              usually what you want.
            </p>
          </div>
        </div>
      )}

      {tab === "storefront" && (
        <div className="space-y-4">
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-ring"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              disabled={busy}
            />
            <span>
              Publish this branch&apos;s offers page
              {branchSlug && (
                <code className="ml-1 font-mono text-xs text-muted-foreground">
                  /offers/{branchSlug}
                </code>
              )}
              <span className="block text-[11px] text-muted-foreground">
                Turn off for a branch that exists only for QR routing. Its
                codes then fall through to the group offers page instead.
              </span>
            </span>
          </label>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="division-hero">Hero image URL</Label>
              <Input
                id="division-hero"
                value={heroUrl}
                onChange={(e) => setHeroUrl(e.target.value)}
                placeholder="Wide banner across the top of the branch page"
                disabled={busy}
              />
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="division-address">Address</Label>
              <Input
                id="division-address"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Street 12, Industrial Area, Doha, Qatar"
                disabled={busy}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="division-phone">Phone</Label>
              <Input
                id="division-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+974 4000 0000"
                disabled={busy}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="division-whatsapp">WhatsApp</Label>
              <Input
                id="division-whatsapp"
                value={whatsapp}
                onChange={(e) => setWhatsapp(e.target.value)}
                placeholder="+974 5000 0000"
                disabled={busy}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="division-email">Email</Label>
              <Input
                id="division-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="alattiya@parisunitedgroup.com"
                disabled={busy}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="division-maps">Google Maps link</Label>
              <Input
                id="division-maps"
                type="url"
                value={mapsUrl}
                onChange={(e) => setMapsUrl(e.target.value)}
                placeholder="https://maps.app.goo.gl/…"
                disabled={busy}
              />
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="division-hours">Opening hours</Label>
              <Input
                id="division-hours"
                value={hours}
                onChange={(e) => setHours(e.target.value)}
                placeholder="Sat–Thu 8:00–24:00 · Fri 8:00–11:30, 13:00–24:00"
                disabled={busy}
              />
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Social links
            </h3>
            <div className="grid gap-3 md:grid-cols-2">
              {(
                [
                  ["Instagram", instagram, setInstagram, "https://instagram.com/…"],
                  ["Facebook", facebook, setFacebook, "https://facebook.com/…"],
                  ["TikTok", tiktok, setTiktok, "https://tiktok.com/@…"],
                  ["YouTube", youtube, setYoutube, "https://youtube.com/@…"],
                  ["Snapchat", snapchat, setSnapchat, "https://snapchat.com/add/…"],
                  ["X (Twitter)", x, setX, "https://x.com/…"],
                ] as const
              ).map(([label, value, setter, placeholder]) => (
                <div key={label} className="space-y-1.5">
                  <Label htmlFor={`division-${label}`}>{label}</Label>
                  <Input
                    id={`division-${label}`}
                    type="url"
                    value={value}
                    onChange={(e) => setter(e.target.value)}
                    placeholder={placeholder}
                    disabled={busy}
                  />
                </div>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-muted-foreground">
              Only the links you fill in appear in the page footer.
            </p>
          </div>
        </div>
      )}

      <div className="mt-4 flex justify-end">
        <Button type="submit" disabled={busy || name.trim().length < 2}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Building2 className="h-4 w-4" />}
          {isEdit ? "Save changes" : "Create division"}
        </Button>
      </div>
    </form>
  );
}

function QrCreateForm({
  divisionId,
  onCancel,
  onSaved,
  onError,
}: {
  divisionId: number;
  onCancel: () => void;
  onSaved: (label: string) => void | Promise<void>;
  onError: (msg: string) => void;
}) {
  const [label, setLabel] = React.useState("");
  const [targetUrl, setTargetUrl] = React.useState("");
  const [kind, setKind] = React.useState<TargetKind>("catalogue");
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await adminApi.post(`${DIVISIONS}/${divisionId}/qr-codes`, {
        label: label.trim(),
        target_url: targetUrl.trim() || null,
        target_kind: kind,
      });
      await onSaved(label.trim());
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-primary/30 bg-primary/[0.04] p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">New QR code</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            A second code for the same branch — e.g. one on the flyer, one on
            the shelf-talker. Its permanent URL is generated from the label.
          </p>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr_1fr_180px]">
        <div className="space-y-1.5">
          <Label htmlFor="qr-label">Label</Label>
          <Input
            id="qr-label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Shelf talker"
            required
            disabled={busy}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="qr-target">Link (optional)</Label>
          <Input
            id="qr-target"
            type="url"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            placeholder="https://pug.qa/offers/ramadan"
            disabled={busy}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="qr-kind">Link type</Label>
          <Select
            id="qr-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as TargetKind)}
            disabled={busy}
          >
            {TARGET_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="mt-3 flex justify-end">
        <Button type="submit" disabled={busy || !label.trim()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <QrCode className="h-4 w-4" />}
          Create QR code
        </Button>
      </div>
    </form>
  );
}

function QrEditForm({
  qr,
  onCancel,
  onSaved,
  onError,
}: {
  qr: QrCodeRead;
  onCancel: () => void;
  onSaved: () => void | Promise<void>;
  onError: (msg: string) => void;
}) {
  const [label, setLabel] = React.useState(qr.label);
  const [targetUrl, setTargetUrl] = React.useState(qr.target_url ?? "");
  const [kind, setKind] = React.useState<TargetKind>(qr.target_kind);
  const [fallbackUrl, setFallbackUrl] = React.useState(qr.fallback_url ?? "");
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      // Note the absence of ``slug`` — the backend rejects it outright
      // (422), and the printed artwork depends on it never moving.
      await adminApi.patch(`${QR_CODES}/${qr.id}`, {
        label: label.trim(),
        target_url: targetUrl.trim() || null,
        target_kind: kind,
        fallback_url: fallbackUrl.trim() || null,
      });
      await onSaved();
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-primary/30 bg-primary/[0.04] p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          {/* Name the code being edited. Several codes stack under one
              division, so a bare "Update link" heading leaves the
              operator guessing which one this panel belongs to. */}
          <h4 className="text-sm font-semibold">
            Editing <span className="text-primary">{qr.label}</span>
          </h4>
          <p className="mt-0.5 text-xs text-muted-foreground">
            The QR image and its URL{" "}
            <code className="font-mono">{qrUrlDisplay(qr.slug)}</code> stay
            exactly the same — no need to reprint anything.
          </p>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr_180px]">
        <div className="space-y-1.5">
          <Label htmlFor={`edit-target-${qr.id}`}>New link</Label>
          <Input
            id={`edit-target-${qr.id}`}
            type="url"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            placeholder="https://pug.qa/offers/ramadan"
            disabled={busy}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`edit-kind-${qr.id}`}>Link type</Label>
          <Select
            id={`edit-kind-${qr.id}`}
            value={kind}
            onChange={(e) => setKind(e.target.value as TargetKind)}
            disabled={busy}
          >
            {TARGET_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`edit-label-${qr.id}`}>Label</Label>
          <Input
            id={`edit-label-${qr.id}`}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            required
            disabled={busy}
          />
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor={`edit-fallback-${qr.id}`}>Fallback link (optional)</Label>
          <Input
            id={`edit-fallback-${qr.id}`}
            type="url"
            value={fallbackUrl}
            onChange={(e) => setFallbackUrl(e.target.value)}
            placeholder="https://pug.qa/offers"
            disabled={busy}
          />
          <p className="text-[11px] text-muted-foreground">
            Used when this code is disabled or has no link set.
          </p>
        </div>
      </div>

      <div className="mt-3 flex justify-end">
        <Button type="submit" disabled={busy || !label.trim()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
          Save
        </Button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

function Toast({ message, onClose }: { message: string | null; onClose: () => void }) {
  React.useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div
      role="status"
      className="mb-4 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-200"
    >
      <CheckCircle2 className="h-4 w-4" />
      {message}
    </div>
  );
}
