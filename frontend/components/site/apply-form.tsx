"use client";

import * as React from "react";
import { CheckCircle2, FileUp, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

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
  const [cvName, setCvName] = React.useState("");
  const [consent, setConsent] = React.useState(false);
  const [state, setState] = React.useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!consent) {
      setError("Please confirm consent before submitting.");
      return;
    }
    setState("submitting");
    await new Promise((r) => setTimeout(r, 900));
    setState("success");
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
          <p className="mt-2 text-xs opacity-70">
            (Phase 10 wires this to the HR ATS candidate intake.)
          </p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" id={`apply-${jobSlug}`}>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Full name" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} required disabled={state === "submitting"} />
        </FormField>
        <FormField label="Email" required>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required disabled={state === "submitting"} />
        </FormField>
        <FormField label="Phone" required>
          <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required disabled={state === "submitting"} />
        </FormField>
        <FormField label="Nationality">
          <Input value={nationality} onChange={(e) => setNationality(e.target.value)} disabled={state === "submitting"} />
        </FormField>
        <FormField label="Current location">
          <Input value={location} onChange={(e) => setLocation(e.target.value)} disabled={state === "submitting"} />
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
          <Input value={salary} onChange={(e) => setSalary(e.target.value)} disabled={state === "submitting"} />
        </FormField>
        <FormField label="Notice period">
          <Input value={notice} onChange={(e) => setNotice(e.target.value)} disabled={state === "submitting"} placeholder="e.g. Immediate / 1 month" />
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
            {cvName ? cvName : "Click to choose a file"}
          </span>
        </label>
        <input
          id={`${jobSlug}-cv`}
          type="file"
          accept=".pdf,.doc,.docx"
          className="hidden"
          onChange={(e) => setCvName(e.target.files?.[0]?.name ?? "")}
          disabled={state === "submitting"}
        />
        <p className="text-xs text-muted-foreground">
          Phase 10 wires the upload to secure storage with duplicate detection.
        </p>
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
