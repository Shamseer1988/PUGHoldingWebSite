import Link from "next/link";
import { CheckCircle2, Mail, ShieldCheck } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getSiteSettings } from "@/lib/public-api";

export const metadata = {
  title: "Privacy Policy",
  description:
    "How Paris United Group Holding collects, uses, and protects personal information across its retail, distribution, and services businesses.",
};

// Phase A-1: legal copy — refresh hourly.
export const revalidate = 3600;

const LAST_UPDATED = "25 May 2026";

interface PolicySection {
  id: string;
  title: string;
  /** Renders as paragraphs (string[]) and/or bullet lists. */
  paragraphs?: string[];
  bullets?: string[];
}

const SECTIONS: PolicySection[] = [
  {
    id: "overview",
    title: "1. Overview",
    paragraphs: [
      "Paris United Group Holding (\"PUG Holding\", \"we\", \"us\", or \"our\") respects the privacy of every visitor, customer, partner, supplier, and job applicant who interacts with us. This Privacy Policy explains what personal information we collect, why we collect it, and the choices you have.",
      "PUG Holding is a diversified group operating across retail, wholesale distribution, FMCG, fashion, packaging, fresh food, building materials, garages, real estate, and engineering & construction. This policy applies to information processed by the group and its subsidiaries through this website and the supporting business operations.",
    ],
  },
  {
    id: "what-we-collect",
    title: "2. Information We Collect",
    paragraphs: [
      "We only collect personal information that is necessary for the purposes described in this policy. Depending on how you engage with us, this may include:",
    ],
    bullets: [
      "Contact details you submit through forms — name, phone number, email address, company, and any message content you choose to share.",
      "Career-application data — your CV, work history, qualifications, references, and answers to role-specific questions.",
      "Customer and supplier information needed to fulfil orders, deliveries, invoicing, and after-sales support across our retail and distribution businesses.",
      "Newsletter subscription data — your email address and the categories of updates you opt in to.",
      "Technical and usage information collected automatically when you browse the site — IP address, device type, browser, referring page, and pages viewed, gathered through standard server logs and cookies.",
    ],
  },
  {
    id: "how-we-use-it",
    title: "3. How We Use Your Information",
    paragraphs: ["We use personal information only for the following purposes:"],
    bullets: [
      "Responding to enquiries you send via the contact form, email, or phone.",
      "Processing job applications, scheduling interviews, and communicating outcomes.",
      "Fulfilling orders, deliveries, services, and warranty obligations.",
      "Sending newsletters and operational updates to subscribers who have opted in.",
      "Operating, maintaining, and improving the security, performance, and usability of this website and our internal systems.",
      "Complying with applicable laws of the State of Qatar and any other jurisdiction in which a PUG Holding subsidiary operates.",
    ],
  },
  {
    id: "legal-basis",
    title: "4. Legal Basis for Processing",
    paragraphs: [
      "We rely on one or more of the following lawful bases when we process your personal information: your consent (which you can withdraw at any time), the performance of a contract you have entered into with a PUG Holding entity, a legitimate business interest that is not overridden by your rights, and compliance with a legal obligation.",
    ],
  },
  {
    id: "sharing",
    title: "5. How We Share Information",
    paragraphs: [
      "We do not sell your personal information. We share it only with parties who help us deliver the services you have requested, and only to the extent required:",
    ],
    bullets: [
      "Subsidiaries and operating companies within the PUG Holding group, on a need-to-know basis.",
      "Trusted service providers — including hosting, email delivery, analytics, payment processors, and logistics partners — bound by confidentiality and data-protection obligations.",
      "Regulators, courts, or government authorities when we are legally required to disclose information.",
      "Professional advisors (auditors, legal counsel) where strictly necessary for legitimate business or compliance purposes.",
    ],
  },
  {
    id: "cookies",
    title: "6. Cookies & Similar Technologies",
    paragraphs: [
      "This website uses a minimal set of cookies and similar technologies to remember your preferences (for example, the light or dark theme you have selected), to keep our session and security infrastructure working correctly, and to understand which content is most useful so we can keep improving it. You can disable cookies in your browser, but parts of the site may not function as intended without them.",
    ],
  },
  {
    id: "retention",
    title: "7. How Long We Keep Your Information",
    paragraphs: [
      "We retain personal information only for as long as it is needed for the purpose it was collected, after which it is securely deleted or anonymised. Contractual records are kept for the period required by Qatari tax and commercial-law obligations. Career-application data is retained for up to 24 months unless you ask us to delete it sooner.",
    ],
  },
  {
    id: "security",
    title: "8. Security",
    paragraphs: [
      "We apply organisational, physical, and technical safeguards designed to protect personal information against unauthorised access, alteration, disclosure, or destruction. While no system is completely immune from risk, we continuously review our controls and train our teams to keep your data safe.",
    ],
  },
  {
    id: "your-rights",
    title: "9. Your Rights",
    paragraphs: [
      "Subject to applicable law, you have the right to ask us to:",
    ],
    bullets: [
      "Confirm what personal information we hold about you and provide a copy of it.",
      "Correct information that is inaccurate, incomplete, or out of date.",
      "Delete personal information when it is no longer required, subject to any legal retention obligations.",
      "Restrict or object to specific processing activities.",
      "Withdraw any consent you previously gave.",
    ],
  },
  {
    id: "children",
    title: "10. Children's Privacy",
    paragraphs: [
      "Our services are not directed to children under the age of 18, and we do not knowingly collect personal information from minors. If you believe a child has provided us with personal information, please contact us so we can remove it.",
    ],
  },
  {
    id: "updates",
    title: "11. Updates to This Policy",
    paragraphs: [
      "We may update this Privacy Policy from time to time to reflect changes in our practices, services, or applicable law. The \"last updated\" date at the top of this page indicates when the most recent revision took effect. We encourage you to review the policy periodically.",
    ],
  },
  {
    id: "contact",
    title: "12. Contact Us",
    paragraphs: [
      "If you have questions about this Privacy Policy, want to exercise any of your rights, or wish to raise a concern, please contact us using the details below. We will respond as quickly as practicable, and within any timelines mandated by applicable law.",
    ],
  },
];

export default async function PrivacyPolicyPage() {
  const settings = await getSiteSettings();

  return (
    <>
      <PageHero
        eyebrow="Legal"
        title="Privacy Policy"
        description={`How Paris United Group Holding collects, uses, and protects personal information across its retail, distribution, and services businesses. Last updated ${LAST_UPDATED}.`}
        accent="from-pug-green-700 via-pug-green-500 to-pug-gold-500"
      />

      <Section>
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1fr_3fr]">
          {/* Sticky in-page navigation */}
          <aside className="lg:sticky lg:top-28 lg:self-start">
            <GlassCard className="p-5">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300">
                  <ShieldCheck className="h-4 w-4" />
                </span>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-foreground/80">
                  On this page
                </p>
              </div>
              <ul className="mt-4 space-y-2 text-sm">
                {SECTIONS.map((s) => (
                  <li key={s.id}>
                    <Link
                      href={`#${s.id}`}
                      className="group/toc inline-flex items-start gap-2 text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <span
                        aria-hidden
                        className="mt-1.5 inline-block h-1 w-1 rounded-full bg-pug-gold-500/50 transition-all duration-200 group-hover/toc:scale-150 group-hover/toc:bg-pug-gold-500"
                      />
                      <span>{s.title.replace(/^\d+\.\s*/, "")}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </GlassCard>
          </aside>

          {/* Policy body */}
          <article className="space-y-10">
            {SECTIONS.map((section) => (
              <section key={section.id} id={section.id} className="scroll-mt-24">
                <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
                  {section.title}
                </h2>
                <div className="mt-2 h-px w-12 bg-gradient-to-r from-pug-gold-500 to-transparent" />
                {section.paragraphs?.map((p, i) => (
                  <p
                    key={i}
                    className="mt-4 text-sm leading-relaxed text-muted-foreground sm:text-base"
                  >
                    {p}
                  </p>
                ))}
                {section.bullets && (
                  <ul className="mt-4 space-y-2.5">
                    {section.bullets.map((b, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-3 text-sm leading-relaxed text-muted-foreground sm:text-base"
                      >
                        <CheckCircle2
                          className="mt-1 h-4 w-4 shrink-0 text-pug-gold-600 dark:text-pug-gold-400"
                          aria-hidden
                        />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                )}

                {section.id === "contact" && (
                  <GlassCard className="mt-5 p-5 sm:p-6">
                    <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-start gap-3">
                        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300">
                          <Mail className="h-5 w-5" />
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-foreground">
                            Privacy enquiries
                          </p>
                          <p className="mt-0.5 text-sm text-muted-foreground">
                            {settings.contact_email ?? "info@parisunitedgroup.com"}
                            {settings.contact_address
                              ? ` · ${settings.contact_address}`
                              : ""}
                          </p>
                        </div>
                      </div>
                      <Link
                        href="/contact"
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-pug-gold-500/40 bg-pug-gold-500/10 px-4 py-2 text-sm font-medium text-pug-gold-800 transition-all duration-200 hover:-translate-y-0.5 hover:bg-pug-gold-500/15 hover:shadow-[0_6px_18px_-10px_rgba(207,166,70,0.5)] dark:text-pug-gold-200"
                      >
                        Open contact form
                      </Link>
                    </div>
                  </GlassCard>
                )}
              </section>
            ))}
          </article>
        </div>
      </Section>
    </>
  );
}
