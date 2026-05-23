"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Activity, CheckCircle2, Loader2, XCircle } from "lucide-react";

import { getBackendHealth, type HealthResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

export function BackendHealthCard() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    getBackendHealth()
      .then((data) => {
        if (!cancelled) setState({ kind: "ok", data });
      })
      .catch((error: Error) => {
        if (!cancelled) setState({ kind: "error", message: error.message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="glass-card p-6 sm:p-8"
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "rounded-full p-2",
            state.kind === "ok" && "bg-emerald-500/15 text-emerald-500",
            state.kind === "error" && "bg-rose-500/15 text-rose-500",
            state.kind === "loading" && "bg-sky-500/15 text-sky-500"
          )}
        >
          {state.kind === "loading" && (
            <Loader2 className="h-5 w-5 animate-spin" />
          )}
          {state.kind === "ok" && <CheckCircle2 className="h-5 w-5" />}
          {state.kind === "error" && <XCircle className="h-5 w-5" />}
        </div>
        <div>
          <h2 className="text-base font-semibold sm:text-lg">
            Backend health check
          </h2>
          <p className="text-xs text-muted-foreground sm:text-sm">
            GET /api/v1/health
          </p>
        </div>
        <Activity className="ml-auto h-5 w-5 text-muted-foreground" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        {state.kind === "loading" && (
          <p className="text-muted-foreground">Contacting backend…</p>
        )}

        {state.kind === "error" && (
          <p className="text-rose-500 sm:col-span-2 break-words">
            {state.message}
          </p>
        )}

        {state.kind === "ok" && (
          <>
            <Field label="Service" value={state.data.service} />
            <Field label="Version" value={state.data.version} />
            <Field label="Environment" value={state.data.environment} />
            <Field label="Database" value={state.data.database} />
            <Field
              label="Timestamp"
              value={new Date(state.data.timestamp).toLocaleString()}
              full
            />
          </>
        )}
      </div>
    </motion.div>
  );
}

function Field({
  label,
  value,
  full = false,
}: {
  label: string;
  value: string;
  full?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border/60 bg-background/40 px-3 py-2",
        full && "sm:col-span-2"
      )}
    >
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 font-medium break-words">{value}</p>
    </div>
  );
}
