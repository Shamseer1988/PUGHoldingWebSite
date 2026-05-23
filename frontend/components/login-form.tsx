"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, Eye, EyeOff, Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthApiError } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface LoginFormProps {
  title: string;
  subtitle: string;
  /** Shown above the form (e.g. "Website Admin" or "HR ATS Portal"). */
  badge: string;
  /** Default seed email shown as a hint on the form. */
  seedHint?: { email: string; password: string };
  /** Where to send the user if they hit "Back to home". */
  homeHref?: string;
  className?: string;
}

export function LoginForm({
  title,
  subtitle,
  badge,
  seedHint,
  homeHref = "/",
  className,
}: LoginFormProps) {
  const { login } = useAuth();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      if (err instanceof AuthApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Unable to log in. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={cn("w-full max-w-md", className)}
    >
      <Card className="glass-card">
        <CardHeader className="space-y-2 text-center">
          <span className="mx-auto inline-flex items-center rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            {badge}
          </span>
          <CardTitle className="text-2xl sm:text-3xl">{title}</CardTitle>
          <CardDescription>{subtitle}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                placeholder="you@example.com"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={submitting}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={submitting}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute inset-y-0 right-0 inline-flex h-10 w-10 items-center justify-center text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600 dark:text-rose-300"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={submitting || !email || !password}
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          {seedHint && (
            <div className="mt-6 rounded-md border border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Seed credentials (dev)</p>
              <p className="mt-1">
                <span className="font-mono">{seedHint.email}</span> /{" "}
                <span className="font-mono">{seedHint.password}</span>
              </p>
              <p className="mt-1 text-[11px]">
                Run <span className="font-mono">python -m app.scripts.seed_users</span>{" "}
                to create the seed accounts.
              </p>
            </div>
          )}

          <div className="mt-6 text-center">
            <Link
              href={homeHref}
              className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to home
            </Link>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
