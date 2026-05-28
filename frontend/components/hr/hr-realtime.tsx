"use client";

/**
 * Mounts the HR WebSocket listener (Phase C-2).
 *
 * Separate client component so the HR layout can stay a server
 * component. The hook handles connection, reconnection, and toast
 * dispatch; this wrapper just gets it into the tree.
 */
import { useHrNotifications } from "@/lib/hr/notifications";

export function HrRealtimeListener() {
  useHrNotifications();
  return null;
}
