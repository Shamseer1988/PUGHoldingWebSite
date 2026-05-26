"use client";

import * as React from "react";
import { CheckCircle2, FileUp, Info, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  parseCvPreview,
  PublicApiError,
  submitCandidateApplication,
} from "@/lib/public-api-client";

interface ApplyFormProps {
  jobTitle: string;
  jobSlug: string;
}

export function ApplyForm({ jobTitle, jobSlug }: ApplyFormProps) {
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [nationality, setNationality] = React.useState("");
  const [location, setLocation] = React.useState("");
  const [experience, setExperience] = React.useState("");
  const [salary, setSalary] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [cover, setCover] = React.useState("");
  const [cvFile, setCvFile] = React.useState<File | null>(null);
  const [consent, setConsent] = React.useState(false);
  const [state, setState] = React.useState<
    "idle" | "submitting" | "success" | "duplicate" | "error"
  >("idle");
  const [error, setError] = React.useState<string | null>(null);
  const [wasExisting, setWasExisting] = React.useState(false);

  // Auto-fill state — populated when the candidate attaches a CV.
  const [parsing, setParsing] = React.useState(false);
  const [parseWarning, setParseWarning] = React.useState<string | null>(null);
  const [autoFilled, setAutoFilled] = React.useState<Set<string>>(new Set());

  /** Set state only when the form field is still empty — never clobber
   * a value the candidate just typed manually. */
  function setIfEmpty(
    field: string,
    setter: (v: string) => void,
    current: string,
    value: string | null | undefined,
  ) {
    if (!value) return;
    if (current.trim().length > 0) return;
    setter(value);
    setAutoFilled((prev) => new Set(prev).add(field));
  }

  async function onCvAttach(file: File) {
    setCvFile(file);
    setParseWarning(null);
    setAutoFilled(new Set());
    setParsing(true);
    try {
      const preview = await parseCvPreview(file);
      if (!preview.parsed) {
        setParseWarning(
          preview.warnings[0] ||
            "Could not auto-fill from this CV — please complete the form manually.",
        );
        return;
      }
      setIfEmpty("full_name", setName, name, preview.full_name);
      setIfEmpty("email", setEmail, email, preview.email);
      setIfEmpty("mobile", setPhone, phone, preview.mobile);
      setIfEmpty("nationality", setNationality, nationality, preview.nationality);
      setIfEmpty(
        "current_location",
        setLocation,
        location,
        preview.current_location,
      );
      if (preview.total_experience_years != null) {
        setIfEmpty(
          "total_experience_years",
          setExperience,
          experience,
          String(preview.total_experience_years),
        );
      }
      if (preview.expected_salary != null) {
        setIfEmpty(
          "expected_salary",
          setSalary,
          salary,
          String(preview.expected_salary),
        );
      }
      setIfEmpty("notice_period", setNotice, notice, preview.notice_period);
    } catch (err) {
      setParseWarning(
        err instanceof PublicApiError
          ? err.message
          : "We couldn't read your CV automatically — please fill the form manually.",
      );
    } finally {
      setParsing(false);
    }
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!consent) {
      setError("Please confirm consent before submitting.");
      return;
    }
    if (!cvFile) {
      setError("Please attach your CV (PDF, DOC, or DOCX).");
      return;
    }

    setState("submitting");
    try {
      const result = await submitCandidateApplication({
        full_name: name.trim(),
        email: email.trim(),
        mobile: phone.trim(),
        nationality: nationality.trim() || undefined,
        current_location: location.trim() || undefined,
        total_experience_years: experience ? Number(experience) : undefined,
        expected_salary: salary ? Number(salary) : undefined,
        notice_period: notice.trim() || undefined,
        cover_letter: cover.trim() || undefined,
        job_slug: jobSlug,
        consent: true,
        cv: cvFile,
      });
      setWasExisting(result.was_existing_candidate);
      setState("success");
    } catch (err) {
      if (err instanceof PublicApiError && err.status === 409) {
        setState("duplicate");
        setError(err.message);
      } else {
        setState("error");
        setError(
          err instanceof PublicApiError
            ? err.message
            : err instanceof Error
            ? err.message
            : "Unable to submit your application. Please try again."
        );
      }
    }
  }

  if (state === "success") {
    return (
      <div
        role="status"
        className="flex items-start gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-200"
      >
        <CheckCircle2 className="mt-0.5 h-5 w-5" />
        <div>
          <p className="font-medium">
            Application received for {jobTitle}.
          </p>
          <p className="mt-1">
            HR will review your CV and reach out if there's a match.
          </p>
          {wasExisting && (
            <p className="mt-2 text-xs opacity-80">
              We recognised your details — your new CV has been attached to
              your existing profile.
            </p>
          )}
        </div>
      </div>
    );
  }

  if (state === "duplicate") {
    return (
      <div
        role="status"
        className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-200"
      >
        <Info className="mt-0.5 h-5 w-5" />
        <div>
          <p className="font-medium">You've already applied to this role.</p>
          <p className="mt-1">
            {error ??
              "We've already received your application for this position. We'll get back to you on the existing one."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" id={`apply-${jobSlug}`}>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Full name" required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={state === "submitting"}
          />
        </FormField>
        <FormField label="Email" required>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={state === "submitting"}
          />
        </FormField>
        <FormField label="Phone" required>
          <Input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            required
            disabled={state === "submitting"}
          />
        </FormField>
        <FormField label="Nationality">
          <Input
            value={nationality}
            onChange={(e) => setNationality(e.target.value)}
            disabled={state === "submitting"}
          />
        </FormField>
        <FormField label="Current location">
          <Input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            disabled={state === "submitting"}
          />
        </FormField>
        <FormField label="Years of experience">
          <Input
            type="number"
            min={0}
            max={60}
            value={experience}
            onChange={(e) => setExperience(e.target.value)}
            disabled={state === "submitting"}
          />
        </FormField>
        <FormField label="Expected salary (QAR / month)">
          <Input
            type="number"
            min={0}
            value={salary}
            onChange={(e) => setSalary(e.target.value)}
            disabled={state === "submitting"}
          />
        </FormField>
        <FormField label="Notice period">
          <Input
            value={notice}
            onChange={(e) => setNotice(e.target.value)}
            disabled={state === "submitting"}
            placeholder="e.g. Immediate / 1 month"
          />
        </FormField>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${jobSlug}-cv`}>Upload CV (PDF / DOC / DOCX)</Label>
        <label
          htmlFor={`${jobSlug}-cv`}
          className="flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-input bg-background/40 px-3 py-3 text-sm text-muted-foreground hover:border-primary/40 hover:text-foreground"
        >
          <FileUp className="h-4 w-4 text-primary" />
          <span className="truncate">
            {cvFile ? cvFile.name : "Click to choose a file"}
          </span>
        </label>
        <input
          id={`${jobSlug}-cv`}
          type="file"
          accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void onCvAttach(file);
            else setCvFile(null);
          }}
          disabled={state === "submitting"}
        />
        <p className="text-xs text-muted-foreground">
          Max 10 MB. Identical CVs are deduplicated automatically.
        </p>
        {parsing ? (
          <p className="inline-flex items-center gap-1.5 text-xs text-primary">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Reading CV…
          </p>
        ) : null}
        {!parsing && autoFilled.size > 0 ? (
          <p className="inline-flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-300">
            <Sparkles className="h-3.5 w-3.5" /> Auto-filled {autoFilled.size}{" "}
            field{autoFilled.size === 1 ? "" : "s"} from your CV — please review
            below.
          </p>
        ) : null}
        {parseWarning ? (
          <p className="inline-flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-300">
            <Info className="h-3.5 w-3.5" /> {parseWarning}
          </p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${jobSlug}-cover`}>Cover letter / message</Label>
        <Textarea
          id={`${jobSlug}-cover`}
          rows={5}
          value={cover}
          onChange={(e) => setCover(e.target.value)}
          placeholder="Anything you'd like the HR team to know…"
          disabled={state === "submitting"}
        />
      </div>

      <label className="flex items-start gap-3 text-sm text-muted-foreground">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-ring"
          disabled={state === "submitting"}
        />
        <span>
          I consent to Paris United Group Holding processing my personal data
          and CV for recruitment purposes.
        </span>
      </label>

      {error && (
        <p role="alert" className="text-sm text-rose-600 dark:text-rose-300">
          {error}
        </p>
      )}

      <Button
        type="submit"
        disabled={state === "submitting"}
        className="w-full sm:w-auto"
      >
        {state === "submitting" && <Loader2 className="h-4 w-4 animate-spin" />}
        {state === "submitting" ? "Submitting…" : "Submit application"}
      </Button>
    </form>
  );
}

function FormField({
  label,
  children,
  required,
}: {
  label: string;
  children: React.ReactNode;
  required?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </Label>
      {children}
    </div>
  );
}
