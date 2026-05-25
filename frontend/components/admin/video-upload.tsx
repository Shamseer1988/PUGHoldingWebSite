"use client";

import * as React from "react";
import { FilmIcon, Loader2, Play, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

interface VideoUploadProps {
  /** Current persisted URL (relative or absolute). */
  value: string | null | undefined;
  onChange: (url: string | null) => void;
  /** Inline label above the picker. */
  label?: string;
  /** Helper text below the picker. */
  helperText?: string;
  /** Show a manual URL input alongside the file picker. */
  allowManualUrl?: boolean;
  disabled?: boolean;
  className?: string;
  /** Max bytes accepted client-side. Server-side max is 50 MB. */
  maxBytes?: number;
  /** Warn (don't reject) when duration exceeds this many seconds. */
  warnDurationSeconds?: number;
}

interface VideoMeta {
  duration: number | null;
  width: number | null;
  height: number | null;
  size: number | null;
}

/**
 * Video sibling of `ImageUpload` — wraps the existing
 * `/admin/cms/media/upload` endpoint (which already accepts mp4 / webm
 * / mov / ogg up to 50 MB and emits a public URL). Adds client-side
 * duration + resolution probing so the admin gets clear feedback
 * before the upload begins.
 *
 * Designed for the Companies admin form where it sits *next to* the
 * existing `ImageUpload` — the image stays mandatory (it doubles as
 * the poster + mobile fallback), the video is purely additive.
 */
export function VideoUpload({
  value,
  onChange,
  label,
  helperText,
  allowManualUrl = true,
  disabled,
  className,
  maxBytes = 10 * 1024 * 1024,
  warnDurationSeconds = 15,
}: VideoUploadProps) {
  const inputId = React.useId();
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [warning, setWarning] = React.useState<string | null>(null);
  const [meta, setMeta] = React.useState<VideoMeta | null>(null);

  const previewSrc = resolveAssetUrl(value ?? null);

  async function probeMetadata(file: File): Promise<VideoMeta> {
    return new Promise((resolve) => {
      const video = document.createElement("video");
      video.preload = "metadata";
      video.muted = true;
      const objectUrl = URL.createObjectURL(file);
      const cleanup = () => URL.revokeObjectURL(objectUrl);
      video.onloadedmetadata = () => {
        const out: VideoMeta = {
          duration: Number.isFinite(video.duration) ? video.duration : null,
          width: video.videoWidth || null,
          height: video.videoHeight || null,
          size: file.size,
        };
        cleanup();
        resolve(out);
      };
      video.onerror = () => {
        cleanup();
        resolve({ duration: null, width: null, height: null, size: file.size });
      };
      video.src = objectUrl;
    });
  }

  async function handleFile(file: File) {
    setError(null);
    setWarning(null);

    if (file.size > maxBytes) {
      setError(
        `File too large — ${(file.size / 1024 / 1024).toFixed(1)} MB. ` +
          `Max ${(maxBytes / 1024 / 1024).toFixed(0)} MB.`
      );
      return;
    }

    const probed = await probeMetadata(file);
    setMeta(probed);

    if (probed.height !== null && probed.height < 720) {
      setError(
        `Resolution too low — ${probed.width}×${probed.height}. ` +
          "Minimum 720p (1280×720) required."
      );
      return;
    }
    if (probed.duration !== null && probed.duration > warnDurationSeconds) {
      setWarning(
        `Video is ${probed.duration.toFixed(1)} s — recommended 5–8 s ` +
          "for the Group Companies loop. Long videos will still play but " +
          "may distract from the surrounding content."
      );
    }

    setUploading(true);
    try {
      const uploaded = await adminApi.uploadMedia<{ url: string }>(file);
      onChange(uploaded.url);
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setUploading(false);
    }
  }

  function onSelect(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void handleFile(file);
    event.target.value = "";
  }

  return (
    <div className={cn("space-y-2", className)}>
      {label && (
        <label className="text-sm font-medium" htmlFor={inputId}>
          {label}
        </label>
      )}

      <div className="grid gap-3 sm:grid-cols-[10rem_1fr] sm:items-start">
        {/* Preview */}
        <div
          className={cn(
            "relative h-32 w-full overflow-hidden rounded-lg border border-border/60 bg-black/80 sm:w-40",
            !previewSrc && "border-dashed bg-muted/40"
          )}
        >
          {previewSrc ? (
            // Native <video> with controls so the admin can scrub the
            // uploaded clip. `key` forces a reload when the URL changes.
            <video
              key={previewSrc}
              src={previewSrc}
              controls
              muted
              playsInline
              preload="metadata"
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
              <Play className="h-5 w-5 opacity-60" />
              No video
            </div>
          )}
          {value && !uploading && !disabled && (
            <button
              type="button"
              onClick={() => {
                onChange(null);
                setMeta(null);
                setWarning(null);
              }}
              aria-label="Remove video"
              className="absolute right-1 top-1 inline-flex h-7 w-7 items-center justify-center rounded-full bg-background/85 text-rose-600 backdrop-blur hover:bg-background"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Picker + URL field */}
        <div className="space-y-2">
          <label
            htmlFor={inputId}
            className={cn(
              "flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-input bg-background/40 px-3 py-3 text-sm transition-colors",
              (disabled || uploading) && "cursor-not-allowed opacity-60"
            )}
          >
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300">
              {uploading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FilmIcon className="h-4 w-4" />
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-medium text-foreground">
                {uploading ? "Uploading…" : "Click to choose a video"}
              </span>
              <span className="block text-xs text-muted-foreground">
                MP4, WebM, MOV · ≥ 720p · max{" "}
                {(maxBytes / 1024 / 1024).toFixed(0)}&nbsp;MB · 5–8 s loop
              </span>
            </span>
          </label>
          <input
            id={inputId}
            type="file"
            accept="video/mp4,video/webm,video/ogg,video/quicktime"
            className="hidden"
            onChange={onSelect}
            disabled={disabled || uploading}
          />

          {allowManualUrl && (
            <div className="flex gap-2">
              <Input
                placeholder="Or paste a video URL"
                value={value ?? ""}
                onChange={(e) => onChange(e.target.value || null)}
                disabled={disabled || uploading}
                className="flex-1"
              />
              {value && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    onChange(null);
                    setMeta(null);
                    setWarning(null);
                  }}
                  disabled={disabled || uploading}
                >
                  Clear
                </Button>
              )}
            </div>
          )}

          {meta && (meta.duration || meta.width) && (
            <p className="text-[11px] text-muted-foreground">
              {meta.width && meta.height && (
                <span>
                  {meta.width}×{meta.height}
                </span>
              )}
              {meta.width && meta.duration && <span> · </span>}
              {meta.duration && <span>{meta.duration.toFixed(1)} s</span>}
              {meta.size && (
                <span> · {(meta.size / 1024 / 1024).toFixed(2)} MB</span>
              )}
            </p>
          )}

          {warning && (
            <p
              role="alert"
              className="text-xs text-amber-700 dark:text-amber-300"
            >
              {warning}
            </p>
          )}

          {error && (
            <p role="alert" className="text-xs text-rose-600 dark:text-rose-300">
              {error}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
