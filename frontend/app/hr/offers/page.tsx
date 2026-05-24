import { Handshake } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";

export default function HrOffersPage() {
  return (
    <HrShell
      title="Offers"
      description="Track draft, sent, accepted, declined, and joined offers."
    >
      <HrEmptyState
        icon={Handshake}
        title="Offer tracking"
        description="Phase 14 wires offer creation as part of the workflow pipeline. Backend table (hr_offer_tracking) is in place from Phase 7 — the dashboard above lists pending offers."
      />
    </HrShell>
  );
}
