import Link from "next/link";
import { ArrowRight, MessageCircle, Phone } from "lucide-react";

import { ContactForm } from "@/components/site/contact-form";
import { GlassCard } from "@/components/site/glass-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { Button } from "@/components/ui/button";
import { CONTACT_DETAILS } from "@/lib/site-config";

export const metadata = { title: "Contact Us" };

export default function ContactPage() {
  return (
    <>
      <PageHero
        eyebrow="Contact"
        title="Talk to Paris United Group"
        description="Reach the right department fast. Use the form below or any of the quick actions on the right."
        accent="from-violet-600 via-fuchsia-500 to-rose-500"
      />

      <Section className="pt-12">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[2fr_1fr]">
          <GlassCard className="p-6 sm:p-8">
            <h2 className="text-xl font-semibold tracking-tight">
              Send us a message
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Select a department and we'll route your message to the right team.
            </p>
            <div className="mt-6">
              <ContactForm />
            </div>
          </GlassCard>

          <aside className="space-y-4">
            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Reach us directly</h3>
              <ul className="mt-4 space-y-3 text-sm">
                {CONTACT_DETAILS.map((detail) => {
                  const Icon = detail.icon;
                  const inner = (
                    <div className="flex items-start gap-3">
                      <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
                        <Icon className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-muted-foreground">
                          {detail.label}
                        </p>
                        <p className="break-words font-medium">{detail.value}</p>
                      </div>
                    </div>
                  );
                  return (
                    <li key={detail.label}>
                      {detail.href ? (
                        <Link href={detail.href} className="hover:text-foreground">
                          {inner}
                        </Link>
                      ) : (
                        inner
                      )}
                    </li>
                  );
                })}
              </ul>
            </GlassCard>

            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Quick actions</h3>
              <div className="mt-4 flex flex-col gap-2">
                <Button asChild>
                  <Link href="tel:+9740000000000">
                    <Phone className="h-4 w-4" />
                    Call us
                  </Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href="https://wa.me/97400000000" target="_blank">
                    <MessageCircle className="h-4 w-4" />
                    WhatsApp
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </GlassCard>

            <GlassCard className="overflow-hidden p-0">
              <div
                aria-hidden
                className="aspect-[4/3] w-full bg-gradient-to-br from-emerald-500/30 via-teal-500/30 to-sky-500/30"
              >
                <div className="flex h-full w-full items-center justify-center text-sm font-medium text-muted-foreground">
                  Map placeholder · embed in Phase 5
                </div>
              </div>
            </GlassCard>
          </aside>
        </div>
      </Section>
    </>
  );
}
