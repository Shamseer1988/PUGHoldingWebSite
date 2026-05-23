"use client";

import * as React from "react";
import { CheckCircle2, Loader2, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  PublicApiError,
  subscribeToNewsletter,
} from "@/lib/public-api-client";

export function NewsletterForm() {
  const [email, setEmail] = React.useState("");
  const [state, setState] = React.useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }
    setState("submitting");
    try {
      await subscribeToNewsletter(email.trim());
      setState("success");
    } catch (err) {
      setState("error");
      setError(
        err instanceof PublicApiError
          ? err.message
          : err instanceof Error
          ? err.message
          : "Unable to subscribe. Please try again."
      );
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
          <p className="font-medium">You're on the list.</p>
          <p className="mt-1">
            We'll send updates from Paris United Group when there's
            something worth sharing.
          </p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3" id="newsletter">
      <Label htmlFor="newsletter-email" className="sr-only">
        Email address
      </Label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="newsletter-email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="pl-9"
            required
            disabled={state === "submitting"}
          />
        </div>
        <Button type="submit" disabled={state === "submitting"}>
          {state === "submitting" && <Loader2 className="h-4 w-4 animate-spin" />}
          {state === "submitting" ? "Subscribing…" : "Subscribe"}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-rose-600 dark:text-rose-300">
          {error}
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        No spam. Unsubscribe anytime.
      </p>
    </form>
  );
}
