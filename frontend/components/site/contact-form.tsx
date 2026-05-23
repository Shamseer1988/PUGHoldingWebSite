"use client";

import * as React from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const DEPARTMENTS = [
  "General Inquiry",
  "HR Department",
  "Sales",
  "Distribution",
  "Retail",
  "Services",
  "Management Office",
];

export function ContactForm() {
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [subject, setSubject] = React.useState("");
  const [department, setDepartment] = React.useState(DEPARTMENTS[0]);
  const [message, setMessage] = React.useState("");
  const [state, setState] = React.useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("submitting");
    await new Promise((r) => setTimeout(r, 800));
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
          <p className="font-medium">Thanks — we received your message.</p>
          <p className="mt-1">
            The {department} team will get back to you shortly.
          </p>
          <p className="mt-2 text-xs opacity-70">
            (Phase 6 will write this to the contact_messages table and email
            the right department.)
          </p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="contact-name">Full name</Label>
          <Input
            id="contact-name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            disabled={state === "submitting"}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="contact-email">Email</Label>
          <Input
            id="contact-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            disabled={state === "submitting"}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="contact-phone">Phone</Label>
          <Input
            id="contact-phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+974 ..."
            disabled={state === "submitting"}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="contact-department">Department</Label>
          <Select
            id="contact-department"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            disabled={state === "submitting"}
          >
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="contact-subject">Subject</Label>
        <Input
          id="contact-subject"
          required
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="How can we help?"
          disabled={state === "submitting"}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="contact-message">Message</Label>
        <Textarea
          id="contact-message"
          required
          rows={5}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Tell us a little more…"
          disabled={state === "submitting"}
        />
      </div>

      <Button type="submit" disabled={state === "submitting"} className="w-full sm:w-auto">
        {state === "submitting" && <Loader2 className="h-4 w-4 animate-spin" />}
        {state === "submitting" ? "Sending…" : "Send message"}
      </Button>
    </form>
  );
}
