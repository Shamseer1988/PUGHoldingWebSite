"use client";

/**
 * Top-level error boundary (Phase A-8).
 *
 * Catches React render errors that bubble out of every route
 * group's own ``error.tsx`` (or that fire before such a boundary
 * has a chance to mount — e.g. errors during the root layout
 * render). Without this, the browser shows Next.js's generic
 * "Application error" screen and Sentry never sees the trace.
 *
 * Must include its own ``<html>`` + ``<body>`` because the root
 * layout's tree was the thing that errored.
 *
 * Marked as a client component (``"use client"`` at the top) so
 * the ``useEffect`` that reports to Sentry runs in the browser
 * where the SDK's transport lives.
 */
import { useEffect } from "react";
import NextError from "next/error";
import * as Sentry from "@sentry/nextjs";


export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html>
      <body>
        {/* ``next/error`` renders the same minimal "Application
            error" screen as Next.js does itself, so the
            visitor-facing experience is unchanged from before
            this file existed. */}
        <NextError statusCode={0} />
      </body>
    </html>
  );
}
