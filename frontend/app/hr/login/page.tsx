"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { useAuth } from "@/components/auth-provider";

export default function HrLoginPage() {
  const { status } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (status === "authenticated") {
      router.replace("/hr");
    }
  }, [status, router]);

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
      <BackgroundDecor />
      <LoginForm
        badge="HR ATS Portal"
        title="Sign in to the HR portal"
        subtitle="Manage job openings, candidate applications, interviews, and reports."
        seedHint={{
          email: "hrmanager@pug.example.com",
          password: "ChangeMe!123",
        }}
      />
    </main>
  );
}

function BackgroundDecor() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      <div className="absolute -left-32 top-[-10%] h-72 w-72 rounded-full bg-sky-500/30 blur-3xl" />
      <div className="absolute right-[-10%] top-1/3 h-80 w-80 rounded-full bg-violet-500/20 blur-3xl" />
      <div className="absolute bottom-[-10%] left-1/3 h-72 w-72 rounded-full bg-teal-400/20 blur-3xl" />
    </div>
  );
}
