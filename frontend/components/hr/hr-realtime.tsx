"use client";

/**
 * Mounts the HR WebSocket listener (Phase C-2).
 *
 * Separate client component so the HR layout can stay a server
 * component. The hook handles connection, reconnection, and toast
 * dispatch; this wrapper just gets it into the tree.
 */
import { useHrDataBump } from "@/lib/hr/data-sync";
import { useHrNotifications } from "@/lib/hr/notifications";

export function HrRealtimeListener() {
  // Turn every "data changed" realtime event into a data-sync bump so all
  // open HR screens refetch — multi-operator freshness.
  const bump = useHrDataBump();
  useHrNotifications(bump);
  return null;
}
