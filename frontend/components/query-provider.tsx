"use client";

/**
 * QueryClientProvider wrapper used by the admin + HR layouts
 * (Phase B-4).
 *
 * The client is constructed once via ``useState`` so React 18
 * Strict Mode's double-effect doesn't tear down an in-flight
 * cache between mounts. One client per browser tab is fine —
 * admin / HR sessions don't share data with each other or with
 * public pages, so we don't try to hoist this any higher.
 */
import * as React from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { makeQueryClient } from "@/lib/query-client";

export function QueryProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [client] = React.useState(() => makeQueryClient());
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
