import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function HrPlaceholderPage() {
  return (
    <main className="container mx-auto flex min-h-screen max-w-2xl flex-col items-start justify-center gap-4 px-4 py-16">
      <span className="rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
        Phase 1 placeholder
      </span>
      <h1 className="text-2xl font-semibold sm:text-3xl">HR ATS Portal</h1>
      <p className="text-muted-foreground">
        The separate HR Admin / ATS login arrives in Phase 2 at{" "}
        <code className="rounded bg-muted px-1.5 py-0.5">/hr/login</code>.
        From Phases 7-16 it will host job openings, candidate applications,
        CV parsing, scoring, AI review, workflow pipeline, interview
        management, and HR reports.
      </p>
      <Button asChild variant="outline">
        <Link href="/">
          <ArrowLeft className="h-4 w-4" />
          Back to home
        </Link>
      </Button>
    </main>
  );
}
