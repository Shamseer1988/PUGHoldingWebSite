"use client";

import * as React from "react";
import {
  ArrowLeft,
  BadgeDollarSign,
  Briefcase,
  CalendarClock,
  Download,
  FileBarChart,
  FileSpreadsheet,
  FileText,
  ListChecks,
  Loader2,
  Play,
  Sparkles,
  UserCheck,
  UserX,
  type LucideIcon,
} from "lucide-react";

import {
  CandidateFilterPanel,
  filtersToQueryParams,
} from "@/components/hr/candidate-filter-panel";
import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { env } from "@/lib/env";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { loadSession } from "@/lib/auth";
import type {
  CandidateAdvancedFilters,
  ReportResponse,
  ReportType,
} from "@/lib/hr/types";


const ICONS: Record<string, LucideIcon> = {
  ListChecks,
  Briefcase,
  CalendarClock,
  UserCheck,
  UserX,
  BadgeDollarSign,
  Sparkles,
};


export default function HrReportsPage() {
  const [types, setTypes] = React.useState<ReportType[] | null>(null);
  const [activeKey, setActiveKey] = React.useState<string | null>(null);

  React.useEffect(() => {
    hrApi
      .get<ReportType[]>("/hr/reports/types")
      .then(setTypes)
      .catch(() => setTypes([]));
  }, []);

  if (activeKey) {
    const active = types?.find((t) => t.key === activeKey) ?? null;
    if (!active) {
      // Race: bad key. Just go back to the picker.
      setActiveKey(null);
      return null;
    }
    return (
      <ReportRunner
        report={active}
        onBack={() => setActiveKey(null)}
      />
    );
  }

  return (
    <HrShell
      title="Reports & export"
      description="Run a report against the current pipeline and export to CSV, Excel, or PDF."
    >
      {types === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : types.length === 0 ? (
        <HrEmptyState
          icon={FileBarChart}
          title="No reports available"
          description="Check your network or refresh — the reports service is reachable from /hr/reports/types."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {types.map((t) => {
            const Icon = ICONS[t.icon] ?? FileBarChart;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setActiveKey(t.key)}
                className="group flex h-full flex-col gap-3 rounded-2xl border border-border/60 bg-card p-5 text-left transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-pug-gold-500/25 bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="text-base font-semibold tracking-tight">
                  {t.title}
                </h3>
                <p className="flex-1 text-sm text-muted-foreground">
                  {t.description}
                </p>
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary">
                  Open report
                  <Play className="h-3 w-3" />
                </span>
              </button>
            );
          })}
        </div>
      )}
    </HrShell>
  );
}


// ---------------------------------------------------------------------------
// Single-report runner — filter panel + preview table + export buttons
// ---------------------------------------------------------------------------


function ReportRunner({
  report,
  onBack,
}: {
  report: ReportType;
  onBack: () => void;
}) {
  const [filters, setFilters] = React.useState<CandidateAdvancedFilters>({});
  const [data, setData] = React.useState<ReportResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [exporting, setExporting] = React.useState<string | null>(null);

  const runReport = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = filtersToQueryParams(filters);
      const url = `/hr/reports/${report.key}${
        params.toString() ? `?${params}` : ""
      }`;
      const result = await hrApi.get<ReportResponse>(url);
      setData(result);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setLoading(false);
    }
  }, [filters, report.key]);

  // Auto-run on mount so users see the unfiltered baseline immediately.
  React.useEffect(() => {
    void runReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function exportFile(format: "csv" | "xlsx" | "pdf") {
    setExporting(format);
    setError(null);
    try {
      const params = filtersToQueryParams(filters);
      params.set("format", format);
      const session = loadSession("hr");
      if (!session) throw new Error("Sign in expired. Please log in again.");
      const response = await fetch(
        `${env.apiBaseUrl}/hr/reports/${report.key}/export?${params}`,
        {
          headers: { Authorization: `Bearer ${session.accessToken}` },
        }
      );
      if (!response.ok) {
        let detail = `Export failed (${response.status})`;
        try {
          const body = await response.json();
          if (typeof body?.detail === "string") detail = body.detail;
        } catch {
          /* swallow */
        }
        throw new Error(detail);
      }
      const blob = await response.blob();
      const filename =
        response.headers
          .get("Content-Disposition")
          ?.match(/filename="?([^";]+)"?/)?.[1] ??
        `${report.key}.${format}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setExporting(null);
    }
  }

  return (
    <HrShell
      title={report.title}
      description={report.description}
      actions={
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-3.5 w-3.5" />
          All reports
        </Button>
      }
    >
      <div className="space-y-4">
        <CandidateFilterPanel
          value={filters}
          onChange={setFilters}
          onApply={runReport}
          onReset={() => {
            setFilters({});
            // Re-run with empty filters once state settles.
            setTimeout(() => void runReport(), 0);
          }}
        />

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/60 bg-card px-4 py-3">
          <div className="text-sm">
            {loading ? (
              <span className="text-muted-foreground">
                <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
                Running report…
              </span>
            ) : data ? (
              <span className="font-medium">
                {data.rows.length} row{data.rows.length === 1 ? "" : "s"}
                <span className="ml-2 text-muted-foreground">
                  · generated{" "}
                  {new Date(data.generated_at).toLocaleString()}
                </span>
              </span>
            ) : (
              <span className="text-muted-foreground">No data yet.</span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ExportButton
              icon={FileText}
              label="CSV"
              onClick={() => exportFile("csv")}
              busy={exporting === "csv"}
              disabled={!data || data.rows.length === 0}
            />
            <ExportButton
              icon={FileSpreadsheet}
              label="Excel"
              onClick={() => exportFile("xlsx")}
              busy={exporting === "xlsx"}
              disabled={!data || data.rows.length === 0}
            />
            <ExportButton
              icon={Download}
              label="PDF"
              onClick={() => exportFile("pdf")}
              busy={exporting === "pdf"}
              disabled={!data || data.rows.length === 0}
            />
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
          >
            {error}
          </div>
        )}

        {data && data.rows.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
            <div className="max-h-[60vh] overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {data.columns.map((col) => (
                      <TableHead key={col}>{col}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.rows.map((row, i) => (
                    <TableRow key={i}>
                      {row.map((cell, j) => (
                        <TableCell key={j} className="align-top">
                          {cell === null || cell === "" ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            String(cell)
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        {data && data.rows.length === 0 && !loading && (
          <HrEmptyState
            icon={FileBarChart}
            title="No matching rows"
            description="Loosen the filters and try again."
          />
        )}
      </div>
    </HrShell>
  );
}


function ExportButton({
  icon: Icon,
  label,
  onClick,
  busy,
  disabled,
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  busy: boolean;
  disabled?: boolean;
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onClick}
      disabled={busy || disabled}
    >
      {busy ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Icon className="h-3.5 w-3.5" />
      )}
      {label}
    </Button>
  );
}
