"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowDown,
  CheckCircle2,
  Download,
  FileArchive,
  FileUp,
  Loader2,
  Upload,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { AdminApiError } from "@/lib/admin/api";
import { loadSession } from "@/lib/auth";
import { env } from "@/lib/env";
import { cn } from "@/lib/utils";


type Preset = "high" | "balanced" | "aggressive";


interface CompressedResult {
  blobUrl: string;
  filename: string;
  originalSize: number;
  compressedSize: number;
  reductionPct: number;
  pageCount: number;
  preset: string;
}


export default function PdfCompressorPage() {
  const [file, setFile] = React.useState<File | null>(null);
  const [preset, setPreset] = React.useState<Preset>("balanced");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<CompressedResult | null>(null);

  // Revoke the previous blob URL when a new result lands or the page
  // unmounts — otherwise the browser holds the bytes in memory forever.
  React.useEffect(() => {
    return () => {
      if (result?.blobUrl) URL.revokeObjectURL(result.blobUrl);
    };
  }, [result]);

  function onPick(picked: File | null) {
    setFile(picked);
    setError(null);
    setResult(null);
  }

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("preset", preset);

      // The endpoint returns binary, not JSON — go through fetch
      // directly so we can read the X-* diagnostic headers AND the
      // blob in one shot.
      const session = loadSession("admin");
      if (!session) {
        throw new AdminApiError("Not authenticated", 401);
      }
      const url = `${env.apiBaseUrl}/admin/marketing/pdf-compressor`;
      const response = await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.accessToken}` },
        body: fd,
        cache: "no-store",
      });

      if (!response.ok) {
        let detail = `Compression failed (${response.status})`;
        try {
          const body = await response.json();
          if (typeof body?.detail === "string") detail = body.detail;
        } catch {
          /* swallow */
        }
        throw new AdminApiError(detail, response.status);
      }

      const blob = await response.blob();
      const filename =
        parseContentDispositionFilename(
          response.headers.get("content-disposition")
        ) || `${file.name.replace(/\.pdf$/i, "")}_compressed.pdf`;

      setResult({
        blobUrl: URL.createObjectURL(blob),
        filename,
        originalSize: Number(response.headers.get("X-Original-Size") ?? 0),
        compressedSize: Number(
          response.headers.get("X-Compressed-Size") ?? blob.size
        ),
        reductionPct: Number(response.headers.get("X-Reduction-Pct") ?? 0),
        pageCount: Number(response.headers.get("X-Page-Count") ?? 0),
        preset: response.headers.get("X-Preset") ?? preset,
      });
    } catch (err) {
      setError(
        err instanceof AdminApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Unexpected error during compression."
      );
    } finally {
      setBusy(false);
    }
  }

  const sizeMb = file ? (file.size / (1024 * 1024)).toFixed(1) : null;

  return (
    <AdminShell
      title="PDF Compressor"
      description="Shrink an oversized PDF before uploading it as a catalogue. Best-quality images at a fraction of the file size."
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Main column — upload + result */}
        <section className="space-y-6">
          {/* Upload card */}
          <div className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm">
            <header className="mb-4 flex items-start gap-3">
              <div className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 text-primary">
                <FileArchive className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-semibold">1 · Pick a PDF</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Drop the source flyer here. The original never leaves
                  this tab — the file is sent to the server only when
                  you click Compress.
                </p>
              </div>
            </header>

            <label
              htmlFor="pdf-input"
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-md border border-dashed px-3 py-5 text-sm transition-colors",
                file
                  ? "border-emerald-500/40 bg-emerald-500/5 text-foreground"
                  : "border-input bg-background/40 text-muted-foreground hover:border-primary/40"
              )}
            >
              <FileUp className="h-4 w-4 text-primary" />
              <span className="truncate">
                {file
                  ? `${file.name} — ${sizeMb} MB`
                  : "Click to choose a PDF (up to 200 MB)"}
              </span>
            </label>
            <input
              id="pdf-input"
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => onPick(e.target.files?.[0] ?? null)}
              disabled={busy}
            />
          </div>

          {/* Compression preset */}
          <div className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm">
            <header className="mb-4 flex items-start gap-3">
              <div className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-pug-gold-500/15 text-pug-gold-700 dark:text-pug-gold-300">
                <ArrowDown className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-semibold">2 · Quality preset</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Higher quality = larger file. Balanced is the sweet
                  spot for screen viewing.
                </p>
              </div>
            </header>

            <div className="grid gap-2 sm:grid-cols-3">
              <PresetCard
                value="high"
                title="High quality"
                resolution="180 DPI · q=92"
                hint="Print-ready. Modest savings (≈ 20–40%)."
                checked={preset === "high"}
                onChange={() => setPreset("high")}
                disabled={busy}
              />
              <PresetCard
                value="balanced"
                title="Balanced"
                resolution="120 DPI · q=85"
                hint="Recommended. Smooth on screen (≈ 50–75% smaller)."
                checked={preset === "balanced"}
                onChange={() => setPreset("balanced")}
                disabled={busy}
                recommended
              />
              <PresetCard
                value="aggressive"
                title="Aggressive"
                resolution="100 DPI · q=75"
                hint="For very large originals (≈ 70–90% smaller)."
                checked={preset === "aggressive"}
                onChange={() => setPreset("aggressive")}
                disabled={busy}
              />
            </div>
          </div>

          {/* Compress action + result */}
          <div className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm">
            <header className="mb-4 flex items-start gap-3">
              <div className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
                <Upload className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-semibold">3 · Compress</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Rendering each page to JPEG at the chosen quality, then
                  rebuilding a small PDF. Takes 5–20 seconds for a
                  typical 50-page flyer.
                </p>
              </div>
            </header>

            <Button
              type="button"
              onClick={submit}
              disabled={!file || busy}
              className="w-full sm:w-auto"
            >
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Compressing…
                </>
              ) : (
                <>
                  <FileArchive className="h-4 w-4" />
                  Compress PDF
                </>
              )}
            </Button>

            {error && (
              <div
                role="alert"
                className="mt-4 flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {result && (
              <ResultCard result={result} originalName={file?.name ?? ""} />
            )}
          </div>
        </section>

        {/* Side column — workflow hint */}
        <aside className="space-y-4">
          <div className="rounded-2xl border border-border/60 bg-pug-gold-500/[0.05] p-5">
            <h3 className="text-sm font-semibold">How to use this</h3>
            <ol className="mt-3 space-y-2 text-xs text-muted-foreground">
              <li>
                <strong className="text-foreground">1.</strong> Upload an
                oversized flyer above and pick a preset.
              </li>
              <li>
                <strong className="text-foreground">2.</strong> Click
                Compress and wait for the download.
              </li>
              <li>
                <strong className="text-foreground">3.</strong> Save the
                compressed file to your local PC.
              </li>
              <li>
                <strong className="text-foreground">4.</strong> Hop over
                to{" "}
                <Link
                  className="font-medium text-primary hover:underline"
                  href="/admin/marketing/catalogues"
                >
                  Catalogues → Upload catalogue
                </Link>{" "}
                and use the compressed file.
              </li>
            </ol>
          </div>
          <div className="rounded-2xl border border-border/60 bg-background/40 p-5 text-xs text-muted-foreground">
            <p className="font-semibold text-foreground">When to use which?</p>
            <ul className="mt-3 space-y-2">
              <li>
                <strong>High</strong> — when the source is going on a
                physical printer too.
              </li>
              <li>
                <strong>Balanced</strong> — default. Looks great on
                phones + desktops, loads fast.
              </li>
              <li>
                <strong>Aggressive</strong> — only when the source is
                already 100 MB+ and you need to ship it to a slow
                mobile network.
              </li>
            </ul>
            <p className="mt-3">
              Compression is lossy — text layers are flattened to images,
              so use this for image-heavy flyers, not contracts.
            </p>
          </div>
        </aside>
      </div>
    </AdminShell>
  );
}


// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PresetCard({
  value,
  title,
  resolution,
  hint,
  checked,
  onChange,
  disabled,
  recommended,
}: {
  value: Preset;
  title: string;
  resolution: string;
  hint: string;
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  recommended?: boolean;
}) {
  return (
    <label
      className={cn(
        "relative flex cursor-pointer flex-col gap-1 rounded-xl border p-4 text-sm transition-colors",
        checked
          ? "border-primary/60 bg-primary/[0.06]"
          : "border-border/60 hover:border-primary/30",
        disabled && "cursor-not-allowed opacity-60"
      )}
    >
      <input
        type="radio"
        name="preset"
        value={value}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="sr-only"
      />
      <span className="flex items-center justify-between">
        <span className="font-semibold leading-tight">{title}</span>
        {recommended && (
          <span className="rounded-full bg-pug-gold-500/20 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-pug-gold-700 dark:text-pug-gold-300">
            Recommended
          </span>
        )}
      </span>
      <span className="font-mono text-[11px] text-muted-foreground">
        {resolution}
      </span>
      <span className="text-[11px] text-muted-foreground">{hint}</span>
    </label>
  );
}


function ResultCard({
  result,
  originalName,
}: {
  result: CompressedResult;
  originalName: string;
}) {
  const orig = formatBytes(result.originalSize);
  const compressed = formatBytes(result.compressedSize);
  return (
    <div className="mt-5 overflow-hidden rounded-xl border border-emerald-500/30 bg-emerald-500/[0.06]">
      <div className="border-b border-emerald-500/20 px-4 py-3">
        <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-700 dark:text-emerald-200">
          <CheckCircle2 className="h-4 w-4" />
          Compressed successfully
        </p>
        <p className="mt-0.5 text-[11px] text-emerald-700/80 dark:text-emerald-200/80">
          {result.pageCount} page{result.pageCount === 1 ? "" : "s"} ·{" "}
          {result.preset} preset
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 border-b border-emerald-500/20 p-4">
        <Stat label="Original" value={orig} />
        <Stat label="Compressed" value={compressed} highlight />
        <Stat
          label="Saved"
          value={`${result.reductionPct}%`}
          highlight
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <p className="text-xs text-muted-foreground">
          Save the file, then open{" "}
          <Link
            href="/admin/marketing/catalogues"
            className="font-medium text-primary hover:underline"
          >
            Catalogues
          </Link>{" "}
          to attach it to a campaign.
        </p>
        <Button asChild size="sm">
          <a href={result.blobUrl} download={result.filename}>
            <Download className="h-4 w-4" />
            Download {result.filename}
          </a>
        </Button>
      </div>
    </div>
  );
}


function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "mt-0.5 text-lg font-semibold",
          highlight && "text-emerald-700 dark:text-emerald-300"
        )}
      >
        {value}
      </p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let v = bytes;
  let unit = 0;
  while (v >= 1024 && unit < units.length - 1) {
    v /= 1024;
    unit++;
  }
  return `${v.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}


function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) return null;
  const m = /filename="?([^";]+)"?/i.exec(header);
  return m?.[1] || null;
}
