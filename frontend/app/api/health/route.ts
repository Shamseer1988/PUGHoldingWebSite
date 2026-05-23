import { NextResponse } from "next/server";

import { env } from "@/lib/env";

/**
 * Frontend-side health proxy.
 * Lets the browser hit a same-origin endpoint while the actual check
 * runs server-side against the FastAPI backend (useful behind Cloudflare).
 */
export async function GET() {
  try {
    const response = await fetch(`${env.apiBaseUrl}/health`, {
      cache: "no-store",
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        message:
          error instanceof Error ? error.message : "Unknown backend error",
      },
      { status: 502 }
    );
  }
}
