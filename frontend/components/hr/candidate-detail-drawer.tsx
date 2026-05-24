"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileText,
  Loader2,
  RefreshCw,
  Save,
  Sparkles,
  X,
} from "lucide-react";

import { CandidateScorePanel } from "@/components/hr/candidate-score-panel";
import { ScoreBadge } from "@/components/hr/score-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { env } from "@/lib/env";
import type {
  Candidate,
  CandidateExtractedData,
  CvReparseResult,
  ParsedCompanyEntry,
  ParsedEducationEntry,
} from "@/lib/hr/types";

interface CandidateDetailDrawerProps {
  candidateId: number | null;
  onClose: () => void;
  onSaved?: (candidate: Candidate) => void;
}

interface CandidateForm {
  full_name: string;
  email: string;
  mobile: string;
  nationality: string;
  current_location: string;
  current_designation: string;
  current_company: string;
  total_experience_years: string;
  gcc_experience_years: string;
  qatar_experience_years: string;
  expected_salary: string;
  notice_period: string;
  visa_status: string;
  availability: string;
}

interface ExtractedForm {
  skills: string;
  languages: string; // comma-separated
  certifications: string; // newline-separated
  education: ParsedEducationEntry[];
  previous_companies: ParsedCompanyEntry[];
  full_text: string;
}

const EMPTY_CANDIDATE_FORM: CandidateForm = {
  full_name: "",
  email: "",
  mobile: "",
  nationality: "",
  current_location: "",
  current_designation: "",
  current_company: "",
  total_experience_years: "",
  gcc_experience_years: "",
  qatar_experience_years: "",
  expected_salary: "",
  notice_period: "",
  visa_status: "",
  availability: "",
};

const EMPTY_EXTRACTED_FORM: ExtractedForm = {
  skills: "",
  languages: "",
  certifications: "",
  education: [],
  previous_companies: [],
  full_text: "",
};

export function CandidateDetailDrawer({
  candidateId,
  onClose,
  onSaved,
}: CandidateDetailDrawerProps) {
  const [loading, setLoading] = React.useState(false);
  const [candidate, setCandidate] = React.useState<Candidate | null>(null);
  const [form, setForm] = React.useState<CandidateForm>(EMPTY_CANDIDATE_FORM);
  const [extracted, setExtracted] = React.useState<ExtractedForm>(
    EMPTY_EXTRACTED_FORM
  );
  const [savingCandidate, setSavingCandidate] = React.useState(false);
  const [savingExtracted, setSavingExtracted] = React.useState(false);
  const [reparsing, setReparsing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  // Load candidate when the drawer opens for a new id.
  React.useEffect(() => {
    if (candidateId == null) {
      setCandidate(null);
      setError(null);
      return;
    }
    void load(candidateId);
  }, [candidateId]);

  async function load(id: number) {
    setLoading(true);
    setError(null);
    try {
      const data = await hrApi.get<Candidate>(`/hr/candidates/${id}`);
      hydrate(data);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setLoading(false);
    }
  }

  function hydrate(data: Candidate) {
    setCandidate(data);
    setForm({
      full_name: data.full_name ?? "",
      email: data.email ?? "",
      mobile: data.mobile ?? "",
      nationality: data.nationality ?? "",
      current_location: data.current_location ?? "",
      current_designation: data.current_designation ?? "",
      current_company: data.current_company ?? "",
      total_experience_years: numStr(data.total_experience_years),
      gcc_experience_years: numStr(data.gcc_experience_years),
      qatar_experience_years: numStr(data.qatar_experience_years),
      expected_salary: numStr(data.expected_salary),
      notice_period: data.notice_period ?? "",
      visa_status: data.visa_status ?? "",
      availability: data.availability ?? "",
    });
    const ex = data.extracted_data;
    setExtracted({
      skills: ex?.skills ?? "",
      languages: (ex?.languages ?? []).join(", "),
      certifications: (ex?.certifications ?? []).join("\n"),
      education: ex?.education ?? [],
      previous_companies: ex?.previous_companies ?? [],
      full_text: ex?.full_text ?? "",
    });
  }

  async function saveCandidate() {
    if (candidateId == null) return;
    setSavingCandidate(true);
    setError(null);
    try {
      const body = {
        full_name: form.full_name.trim() || null,
        email: form.email.trim() || null,
        mobile: form.mobile.trim() || null,
        nationality: form.nationality.trim() || null,
        current_location: form.current_location.trim() || null,
        current_designation: form.current_designation.trim() || null,
        current_company: form.current_company.trim() || null,
        total_experience_years: parseNum(form.total_experience_years),
        gcc_experience_years: parseNum(form.gcc_experience_years),
        qatar_experience_years: parseNum(form.qatar_experience_years),
        expected_salary: parseInt2(form.expected_salary),
        notice_period: form.notice_period.trim() || null,
        visa_status: form.visa_status.trim() || null,
        availability: form.availability.trim() || null,
      };
      const updated = await hrApi.patch<Candidate>(
        `/hr/candidates/${candidateId}`,
        body
      );
      hydrate(updated);
      onSaved?.(updated);
      setToast("Candidate details saved.");
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSavingCandidate(false);
    }
  }

  async function saveExtracted() {
    if (candidateId == null) return;
    setSavingExtracted(true);
    setError(null);
    try {
      const body = {
        skills: extracted.skills.trim() || null,
        languages: extracted.languages
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        certifications: extracted.certifications
          .split(/\r?\n/)
          .map((s) => s.trim())
          .filter(Boolean),
        education: extracted.education,
        previous_companies: extracted.previous_companies,
        full_text: extracted.full_text.trim() || null,
      };
      const data = await hrApi.patch<CandidateExtractedData>(
        `/hr/candidates/${candidateId}/extracted-data`,
        body
      );
      setExtracted({
        ...extracted,
        skills: data.skills ?? "",
        languages: (data.languages ?? []).join(", "),
        certifications: (data.certifications ?? []).join("\n"),
        education: data.education ?? [],
        previous_companies: data.previous_companies ?? [],
        full_text: data.full_text ?? "",
      });
      if (candidate) {
        setCandidate({ ...candidate, extracted_data: data });
      }
      setToast("Extracted data saved.");
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSavingExtracted(false);
    }
  }

  async function reparse() {
    if (candidateId == null) return;
    if (
      !confirm(
        "Re-run the CV parser on the primary document? Existing manual edits to candidate fields will be preserved — only empty fields are filled."
      )
    ) {
      return;
    }
    setReparsing(true);
    setError(null);
    try {
      const result = await hrApi.post<CvReparseResult>(
        `/hr/candidates/${candidateId}/parse-cv`
      );
      if (!result.parsed) {
        setError(result.detail ?? "Parser returned no data.");
      } else {
        hydrate(result.candidate);
        onSaved?.(result.candidate);
        setToast(`Re-parsed with ${result.parser_version}.`);
      }
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setReparsing(false);
    }
  }

  if (candidateId == null) return null;

  const cvDoc = candidate?.documents?.find((d) => d.is_primary) ?? candidate?.documents?.[0];
  const parserVersion = candidate?.extracted_data?.parser_version;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Candidate details"
      className="fixed inset-0 z-50 flex"
    >
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="flex w-full max-w-3xl flex-col bg-background shadow-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-border/60 px-5 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-base font-semibold">
                {candidate?.full_name ?? "Loading candidate…"}
              </h2>
              {candidate?.top_score != null && (
                <ScoreBadge total={candidate.top_score} compact />
              )}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {candidate?.source && (
                <Badge variant="muted" className="capitalize">
                  {candidate.source.replace("_", " ")}
                </Badge>
              )}
              {candidate?.current_designation && (
                <span className="truncate">
                  {candidate.current_designation}
                  {candidate?.current_company
                    ? ` · ${candidate.current_company}`
                    : ""}
                </span>
              )}
              {parserVersion && (
                <span className="inline-flex items-center gap-1">
                  <Sparkles className="h-3 w-3" />
                  Parsed by {parserVersion}
                </span>
              )}
            </div>
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={onClose}
            aria-label="Close candidate detail"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        {/* Quick-action toolbar */}
        <div className="flex flex-wrap items-center gap-2 border-b border-border/60 px-5 py-2">
          {cvDoc && (
            <Button asChild variant="outline" size="sm">
              <Link
                href={resolveCvUrl(cvDoc.file_path)}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FileText className="h-3.5 w-3.5" />
                Open CV
                <ExternalLink className="h-3 w-3" />
              </Link>
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={reparse}
            disabled={reparsing || !candidate?.documents?.length}
          >
            {reparsing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Re-parse CV
          </Button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
              <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
              Loading…
            </div>
          ) : !candidate ? (
            <div className="px-5 py-8 text-sm text-muted-foreground">
              {error ?? "No candidate selected."}
            </div>
          ) : (
            <div className="space-y-6 p-5">
              {error && (
                <div
                  role="alert"
                  className="inline-flex w-full items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
                >
                  <AlertTriangle className="h-4 w-4" />
                  {error}
                </div>
              )}

              <Toast message={toast} onClose={() => setToast(null)} />

              {/* --- Candidate identity + headline --- */}
              <section className="space-y-3 rounded-xl border border-border/60 bg-card p-5">
                <header className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">Candidate details</h3>
                    <p className="text-xs text-muted-foreground">
                      Override anything the parser missed. Fields are stored
                      on the candidate itself.
                    </p>
                  </div>
                  <Button size="sm" onClick={saveCandidate} disabled={savingCandidate}>
                    {savingCandidate ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Save className="h-3.5 w-3.5" />
                    )}
                    Save details
                  </Button>
                </header>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Full name">
                    <Input
                      value={form.full_name}
                      onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    />
                  </Field>
                  <Field label="Nationality">
                    <Input
                      value={form.nationality}
                      onChange={(e) => setForm({ ...form, nationality: e.target.value })}
                    />
                  </Field>
                  <Field label="Email">
                    <Input
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                    />
                  </Field>
                  <Field label="Mobile">
                    <Input
                      value={form.mobile}
                      onChange={(e) => setForm({ ...form, mobile: e.target.value })}
                    />
                  </Field>
                  <Field label="Current location">
                    <Input
                      value={form.current_location}
                      onChange={(e) =>
                        setForm({ ...form, current_location: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Visa status">
                    <Input
                      value={form.visa_status}
                      onChange={(e) => setForm({ ...form, visa_status: e.target.value })}
                    />
                  </Field>
                  <Field label="Current designation">
                    <Input
                      value={form.current_designation}
                      onChange={(e) =>
                        setForm({ ...form, current_designation: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Current company">
                    <Input
                      value={form.current_company}
                      onChange={(e) =>
                        setForm({ ...form, current_company: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Total experience (years)">
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      max="70"
                      value={form.total_experience_years}
                      onChange={(e) =>
                        setForm({ ...form, total_experience_years: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="GCC experience (years)">
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      max="70"
                      value={form.gcc_experience_years}
                      onChange={(e) =>
                        setForm({ ...form, gcc_experience_years: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Qatar experience (years)">
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      max="70"
                      value={form.qatar_experience_years}
                      onChange={(e) =>
                        setForm({ ...form, qatar_experience_years: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Expected salary (monthly)">
                    <Input
                      type="number"
                      min="0"
                      value={form.expected_salary}
                      onChange={(e) =>
                        setForm({ ...form, expected_salary: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Notice period">
                    <Input
                      value={form.notice_period}
                      onChange={(e) =>
                        setForm({ ...form, notice_period: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Availability">
                    <Input
                      value={form.availability}
                      onChange={(e) =>
                        setForm({ ...form, availability: e.target.value })
                      }
                    />
                  </Field>
                </div>
              </section>

              {/* --- Scoring --- */}
              <CandidateScorePanel
                candidateId={candidate.id}
                applications={candidate.applications}
                onChanged={() => void load(candidate.id)}
              />

              {/* --- Extracted data --- */}
              <section className="space-y-3 rounded-xl border border-border/60 bg-card p-5">
                <header className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">Extracted CV data</h3>
                    <p className="text-xs text-muted-foreground">
                      Auto-populated from the uploaded CV. Edit anything the
                      parser got wrong — your changes are stored separately
                      so the parser version stays auditable.
                    </p>
                  </div>
                  <Button size="sm" onClick={saveExtracted} disabled={savingExtracted}>
                    {savingExtracted ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Save className="h-3.5 w-3.5" />
                    )}
                    Save extracted data
                  </Button>
                </header>

                <Field label="Skills" hint="Comma-separated.">
                  <Textarea
                    rows={3}
                    value={extracted.skills}
                    onChange={(e) =>
                      setExtracted({ ...extracted, skills: e.target.value })
                    }
                  />
                </Field>

                <Field label="Languages" hint="Comma-separated.">
                  <Input
                    value={extracted.languages}
                    onChange={(e) =>
                      setExtracted({ ...extracted, languages: e.target.value })
                    }
                  />
                </Field>

                <Field label="Certifications" hint="One per line.">
                  <Textarea
                    rows={3}
                    value={extracted.certifications}
                    onChange={(e) =>
                      setExtracted({ ...extracted, certifications: e.target.value })
                    }
                  />
                </Field>

                {extracted.education.length > 0 && (
                  <div className="space-y-2">
                    <Label>Education</Label>
                    <ul className="space-y-2">
                      {extracted.education.map((edu, idx) => (
                        <li
                          key={idx}
                          className="rounded-md border border-border/60 bg-background/40 p-3 text-xs"
                        >
                          <p className="font-medium text-foreground">{edu.raw}</p>
                          <p className="mt-1 text-muted-foreground">
                            {[edu.degree, edu.institution, edu.year]
                              .filter(Boolean)
                              .join(" · ") || "—"}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {extracted.previous_companies.length > 0 && (
                  <div className="space-y-2">
                    <Label>Previous companies</Label>
                    <ul className="space-y-2">
                      {extracted.previous_companies.map((co, idx) => (
                        <li
                          key={idx}
                          className="rounded-md border border-border/60 bg-background/40 p-3 text-xs"
                        >
                          <p className="font-medium text-foreground">{co.name}</p>
                          <p className="mt-1 text-muted-foreground">
                            {[co.title, co.duration].filter(Boolean).join(" · ") || "—"}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {extracted.full_text && (
                  <details className="rounded-md border border-border/60 bg-background/40 p-3 text-xs">
                    <summary className="cursor-pointer font-medium">
                      Full extracted text ({extracted.full_text.length} chars)
                    </summary>
                    <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words text-[11px] text-muted-foreground">
                      {extracted.full_text}
                    </pre>
                  </details>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Toast({
  message,
  onClose,
}: {
  message: string | null;
  onClose: () => void;
}) {
  React.useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div
      role="status"
      className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-200"
    >
      <CheckCircle2 className="h-4 w-4" />
      {message}
    </div>
  );
}

function numStr(value: number | null | undefined): string {
  if (value == null) return "";
  return String(value);
}

function parseNum(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : null;
}

function parseInt2(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const n = parseInt(trimmed, 10);
  return Number.isFinite(n) ? n : null;
}

function resolveCvUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith("/api/")) {
    try {
      return `${new URL(env.apiBaseUrl).origin}${path}`;
    } catch {
      return path;
    }
  }
  return path;
}
