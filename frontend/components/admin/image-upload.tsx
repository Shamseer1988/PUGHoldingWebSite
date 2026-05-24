"use client";

import * as React from "react";
import Image from "next/image";
import { ImagePlus, Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

interface ImageUploadProps {
  /** Current persisted URL (relative or absolute). */
  value: string | null | undefined;
  onChange: (url: string | null) => void;
  /** Inline label rendered above the control. */
  label?: string;
  /** Show a manual URL input alongside the file picker. */
  allowManualUrl?: boolean;
  disabled?: boolean;
  className?: string;
}

/**
 * Drop-anywhere image picker used by the CMS forms.
 *
 * - Click or drag-and-drop a PNG / JPG / WEBP / GIF / SVG (≤ 5 MB).
 * - Posts to /api/v1/admin/cms/uploads/image, stores the returned
 *   URL via onChange.
 * - Optionally accepts a manual URL paste (useful for external CDNs).
 */
export function ImageUpload({
  value,
  onChange,
  label,
  allowManualUrl = true,
  disabled,
  className,
}: ImageUploadProps) {
  const inputId = React.useId();
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [dragOver, setDragOver] = React.useState(false);

  const previewSrc = resolveAssetUrl(value ?? null);

  async function handleFile(file: File) {
    setError(null);
    setUploading(true);
    try {
      const uploaded = await adminApi.uploadImage(file);
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
    // Reset the input so selecting the same file twice still fires onChange.
    event.target.value = "";
  }

  function onDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragOver(false);
    if (disabled || uploading) return;
    const file = event.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  }

  return (
    <div className={cn("space-y-2", className)}>
      {label && (
        <label className="text-sm font-medium" htmlFor={inputId}>
          {label}
        </label>
      )}

      <div className="grid gap-3 sm:grid-cols-[8rem_1fr] sm:items-start">
        {/* Preview */}
        <div
          className={cn(
            "relative h-32 w-full overflow-hidden rounded-lg border border-border/60 bg-muted/40 sm:w-32",
            !previewSrc && "border-dashed"
          )}
        >
          {previewSrc ? (
            <Image
              src={previewSrc}
              alt="Preview"
              fill
              className="object-cover"
              sizes="128px"
              unoptimized
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
              No image
            </div>
          )}
          {value && !uploading && !disabled && (
            <button
              type="button"
              onClick={() => onChange(null)}
              aria-label="Remove image"
              className="absolute right-1 top-1 inline-flex h-7 w-7 items-center justify-center rounded-full bg-background/80 text-rose-600 backdrop-blur hover:bg-background"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Picker + URL field */}
        <div className="space-y-2">
          <label
            htmlFor={inputId}
            onDragOver={(e) => {
              e.preventDefault();
              if (!disabled && !uploading) setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={cn(
              "flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-input bg-background/40 px-3 py-3 text-sm transition-colors",
              dragOver && "border-primary bg-primary/5",
              (disabled || uploading) && "cursor-not-allowed opacity-60"
            )}
          >
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary">
              {uploading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ImagePlus className="h-4 w-4" />
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-medium text-foreground">
                {uploading
                  ? "Uploading…"
                  : "Click to choose or drop an image"}
              </span>
              <span className="block text-xs text-muted-foreground">
                PNG, JPG, WEBP, GIF or SVG · max 5&nbsp;MB
              </span>
            </span>
          </label>
          <input
            id={inputId}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
            className="hidden"
            onChange={onSelect}
            disabled={disabled || uploading}
          />

          {allowManualUrl && (
            <div className="flex gap-2">
              <Input
                placeholder="Or paste an image URL"
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
                  onClick={() => onChange(null)}
                  disabled={disabled || uploading}
                >
                  Clear
                </Button>
              )}
            </div>
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
