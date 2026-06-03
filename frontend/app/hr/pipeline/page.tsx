"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { HrShell } from "@/components/hr/hr-shell";
import { PipelineBoard, type PipelineCard } from "@/components/hr/pipeline-board";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { useHrDataSync } from "@/lib/hr/data-sync";
import type { CandidateListItem } from "@/lib/hr/types";

export default function HrPipelinePage() {
  const [cards, setCards] = React.useState<PipelineCard[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    try {
      const items = await hrApi.get<CandidateListItem[]>("/hr/candidates");
      setCards(
        items
          .filter((c) => c.latest_application_id != null && c.latest_status)
          .map((c) => ({
            candidateId: c.id,
            applicationId: c.latest_application_id as number,
            name: c.full_name,
            subtitle: c.current_designation,
            status: c.latest_status as string,
            score: c.top_score,
          })),
      );
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  // Refresh the board when a status changes anywhere (drawer, bulk, or
  // another operator via realtime).
  useHrDataSync(() => void refresh());

  return (
    <HrShell
      title="Pipeline"
      description="Drag candidates across the recruitment stages — Sourced through Joined."
    >
      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {cards === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
          Loading pipeline…
        </p>
      ) : (
        <PipelineBoard
          cards={cards}
          onMoved={() => void refresh()}
          onError={setError}
        />
      )}
    </HrShell>
  );
}
