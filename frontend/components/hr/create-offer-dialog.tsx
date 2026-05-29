"use client";

import * as React from "react";
import { Handshake, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { Offer, OfferCreatePayload } from "@/lib/hr/types";


interface Props {
  applicationId: number;
  /** Optional pre-fill defaults. */
  defaults?: {
    position?: string;
  };
  onClose: () => void;
  onCreated: (offer: Offer) => void;
}


/**
 * Phase 6 — Create-offer dialog.
 *
 * Wired into the candidate workflow panel when the application is in
 * an offer-eligible status (recommended_for_offer / selected). Creates
 * the offer as a draft via POST /hr/offers and hands the new row back
 * to the caller so the candidate panel can refresh and the user can
 * keep editing in the offer drawer.
 */
export function CreateOfferDialog({
  applicationId,
  defaults,
  onClose,
  onCreated,
}: Props) {
  const [position, setPosition] = React.useState(defaults?.position ?? "");
  const [salary, setSalary] = React.useState("");
  const [joining, setJoining] = React.useState("");
  const [probation, setProbation] = React.useState("3 months");
  const [reporting, setReporting] = React.useState("");
  const [workLocation, setWorkLocation] = React.useState("");
  const [allowances, setAllowances] = React.useState("");
  const [remarks, setRemarks] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload: OfferCreatePayload = {
        application_id: applicationId,
        position: position.trim() || undefined,
        salary_offered: salary ? Number(salary) : null,
        joining_date: joining || null,
        probation_period: probation.trim() || null,
        reporting_manager: reporting.trim() || null,
        work_location: workLocation.trim() || null,
        allowances: allowances.trim() || null,
        remarks: remarks.trim() || null,
      };
      const offer = await hrApi.post<Offer>("/hr/offers", payload);
      onCreated(offer);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Create offer"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/60 backdrop-blur-sm p-4"
    >
      <form
        onSubmit={submit}
        className="w-full max-w-lg space-y-4 rounded-xl border border-border/60 bg-background p-5 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <Handshake className="h-4 w-4 text-primary" />
              Draft offer
            </h3>
            <p className="text-xs text-muted-foreground">
              Creates a draft offer in 'Draft' state. HR Manager needs to
              approve it before issuing to the candidate.
            </p>
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Position</Label>
            <Input
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              placeholder="Senior Engineer"
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Salary</Label>
            <Input
              type="number"
              min="0"
              value={salary}
              onChange={(e) => setSalary(e.target.value)}
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Joining date</Label>
            <Input
              type="date"
              value={joining}
              onChange={(e) => setJoining(e.target.value)}
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Probation</Label>
            <Input
              value={probation}
              onChange={(e) => setProbation(e.target.value)}
              placeholder="3 months"
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Reporting manager</Label>
            <Input
              value={reporting}
              onChange={(e) => setReporting(e.target.value)}
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Work location</Label>
            <Input
              value={workLocation}
              onChange={(e) => setWorkLocation(e.target.value)}
              placeholder="Doha HQ"
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Allowances (optional)</Label>
            <Textarea
              rows={2}
              value={allowances}
              onChange={(e) => setAllowances(e.target.value)}
              placeholder="Housing, transport, etc."
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Remarks (optional)</Label>
            <Textarea
              rows={2}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              disabled={saving}
            />
          </div>
        </div>

        {error && (
          <p
            role="alert"
            className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
          >
            {error}
          </p>
        )}

        <footer className="flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Create draft offer
          </Button>
        </footer>
      </form>
    </div>
  );
}
