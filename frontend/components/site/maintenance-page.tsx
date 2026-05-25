import Image from "next/image";
import Link from "next/link";
import { Clock3, Mail, Wrench } from "lucide-react";

import type { SiteSettings } from "@/lib/admin/types";

interface MaintenancePageProps {
  settings: SiteSettings;
}

const DEFAULT_MESSAGE =
  "Our website is getting a fresh polish. We'll be back online shortly — thank you for your patience.";

/**
 * Full-screen "under construction" experience shown across every public
 * route when ``site_settings.maintenance_mode_enabled`` is on. The
 * admin and HR portals stay reachable so the team can disable the
 * banner from the admin settings page.
 */
export function MaintenancePage({ settings }: MaintenancePageProps) {
  const message = settings.maintenance_message?.trim() || DEFAULT_MESSAGE;
  const eta = settings.maintenance_eta?.trim() || null;
  const contactEmail = settings.contact_email?.trim() || null;
  const siteName = settings.site_name || "Paris United Group Holding";
  const tagline = settings.tagline?.trim() || null;

  const year = new Date().getFullYear();

  return (
    <main
      id="main-content"
      // Inline style backstops the Tailwind class so the dark background
      // is guaranteed even if a parent layer or the OS light-mode tries
      // to bleed through.
      style={{ backgroundColor: "hsl(145 60% 6%)", colorScheme: "dark" }}
      className="relative isolate flex min-h-screen flex-col items-center justify-center overflow-hidden bg-pug-green-900 px-4 py-12 text-white sm:px-6"
    >
      {/* Layered background — ambient gradient + soft blobs.
          Pure CSS so the page works with JS disabled. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br from-pug-green-900 via-pug-green-800 to-pug-green-900"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 left-1/4 -z-10 h-[28rem] w-[28rem] rounded-full bg-pug-gold-500/25 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute bottom-[-10rem] right-[10%] -z-10 h-[22rem] w-[22rem] rounded-full bg-pug-gold-500/15 blur-3xl"
      />

      {/* Subtle grid pattern */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.06] [background-image:linear-gradient(rgba(255,255,255,0.6)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.6)_1px,transparent_1px)] [background-size:48px_48px]"
      />

      <div className="mx-auto flex w-full max-w-2xl flex-col items-center text-center">
        {/* Brand mark */}
        <Link
          href="/"
          aria-label={siteName}
          className="mb-8 inline-flex items-center justify-center rounded-2xl bg-white/10 p-3 ring-1 ring-white/15 backdrop-blur"
        >
          <Image
            src="/logo-mark.png"
            alt={siteName}
            width={56}
            height={56}
            priority
            className="h-14 w-14"
          />
        </Link>

        {/* Animated icon — three offset cogs with a slow rotate. */}
        <div className="relative mb-8 flex h-24 w-24 items-center justify-center sm:h-28 sm:w-28">
          <span
            aria-hidden
            className="absolute inset-0 animate-ping rounded-full bg-pug-gold-500/15"
            style={{ animationDuration: "3.2s" }}
          />
          <span
            aria-hidden
            className="absolute inset-2 rounded-full bg-pug-gold-500/20 ring-1 ring-pug-gold-500/30"
          />
          <span
            aria-hidden
            className="relative flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-pug-gold-400 to-pug-gold-600 text-pug-green-900 shadow-lg shadow-pug-gold-500/30 sm:h-20 sm:w-20"
          >
            <Wrench
              className="h-7 w-7 sm:h-9 sm:w-9 motion-safe:animate-[spin_8s_linear_infinite]"
              strokeWidth={2.2}
              aria-hidden
            />
          </span>
        </div>

        <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-pug-gold-500/40 bg-pug-gold-500/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-pug-gold-200">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-pug-gold-300 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-pug-gold-300" />
          </span>
          Under maintenance
        </span>

        <h1 className="text-balance font-serif text-3xl font-semibold leading-tight tracking-tight text-white sm:text-4xl md:text-5xl">
          We&rsquo;ll be back shortly
        </h1>

        <p className="mt-4 max-w-lg text-pretty text-base text-white/80 sm:text-lg">
          {message}
        </p>

        {eta && (
          <div className="mt-6 inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/[0.06] px-4 py-2 text-sm text-white/90 backdrop-blur">
            <Clock3 className="h-4 w-4 text-pug-gold-300" aria-hidden />
            <span>
              <span className="text-white/60">Expected back: </span>
              <span className="font-medium text-white">{eta}</span>
            </span>
          </div>
        )}

        {contactEmail && (
          <p className="mt-8 text-sm text-white/70">
            Need to reach us in the meantime?
            <br className="sm:hidden" />{" "}
            <Link
              href={`mailto:${contactEmail}`}
              className="inline-flex items-center gap-1.5 font-medium text-pug-gold-300 underline-offset-4 hover:underline"
            >
              <Mail className="h-4 w-4" aria-hidden />
              {contactEmail}
            </Link>
          </p>
        )}

        {/* Subtle social row */}
        {(settings.social_linkedin ||
          settings.social_instagram ||
          settings.social_facebook ||
          settings.social_youtube) && (
          <div className="mt-8 flex items-center gap-3 text-sm text-white/60">
            <span>Follow updates:</span>
            <div className="flex items-center gap-2">
              {settings.social_linkedin && (
                <SocialDot href={settings.social_linkedin} label="LinkedIn">
                  in
                </SocialDot>
              )}
              {settings.social_instagram && (
                <SocialDot href={settings.social_instagram} label="Instagram">
                  ig
                </SocialDot>
              )}
              {settings.social_facebook && (
                <SocialDot href={settings.social_facebook} label="Facebook">
                  fb
                </SocialDot>
              )}
              {settings.social_youtube && (
                <SocialDot href={settings.social_youtube} label="YouTube">
                  yt
                </SocialDot>
              )}
            </div>
          </div>
        )}
      </div>

      <footer className="mt-16 text-center text-xs text-white/50">
        <p className="font-medium tracking-wide">{siteName}</p>
        {tagline && <p className="mt-1">{tagline}</p>}
        <p className="mt-2">&copy; {year} {siteName}. All rights reserved.</p>
      </footer>
    </main>
  );
}

function SocialDot({
  href,
  label,
  children,
}: {
  href: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-label={label}
      target="_blank"
      rel="noreferrer noopener"
      className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/15 bg-white/5 text-[10px] font-semibold uppercase tracking-wide text-white/70 transition hover:border-pug-gold-400 hover:text-pug-gold-200"
    >
      {children}
    </Link>
  );
}
