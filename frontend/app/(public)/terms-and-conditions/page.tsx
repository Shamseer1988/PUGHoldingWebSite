import Link from "next/link";
import { CheckCircle2, FileText, Mail } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getSiteSettings } from "@/lib/public-api";

export const metadata = {
  title: "Terms & Conditions",
  description:
    "Terms of use governing the Paris United Group Holding website and the services provided through it.",
};

// Phase A-1: legal copy — refresh hourly.
export const revalidate = 3600;

const LAST_UPDATED = "25 May 2026";

interface TermsSection {
  id: string;
  title: string;
  paragraphs?: string[];
  bullets?: string[];
}

const SECTIONS: TermsSection[] = [
  {
    id: "acceptance",
    title: "1. Acceptance of These Terms",
    paragraphs: [
      "These Terms & Conditions (\"Terms\") govern your access to and use of the Paris United Group Holding website (\"the Site\"). By accessing or using the Site you confirm that you have read, understood, and agreed to be bound by these Terms.",
      "If you are using the Site on behalf of a company or other legal entity, you represent that you have the authority to bind that entity to these Terms. If you do not agree with any part of these Terms, please do not use the Site.",
    ],
  },
  {
    id: "company",
    title: "2. About Paris United Group Holding",
    paragraphs: [
      "Paris United Group Holding (\"PUG Holding\", \"we\", \"us\", or \"our\") is a diversified holding group registered in the State of Qatar. The group operates across retail, wholesale distribution, FMCG, fashion, packaging, fresh food, building materials, garages, real estate, and engineering & construction. References to PUG Holding in these Terms include its subsidiaries and operating companies where the context requires.",
    ],
  },
  {
    id: "use-of-site",
    title: "3. Use of the Site",
    paragraphs: [
      "You may use this Site to learn about PUG Holding, our group companies, our services, our news, and our careers; to submit enquiries through the contact form; to subscribe to our newsletter; and to apply for advertised roles. You agree to use the Site lawfully and responsibly. In particular, you agree NOT to:",
    ],
    bullets: [
      "Use the Site in any way that breaches applicable Qatari law or the law of any other jurisdiction from which you access the Site.",
      "Attempt to gain unauthorised access to the Site, the servers on which it runs, or any connected database, account, or computer system.",
      "Introduce viruses, trojans, worms, logic bombs, or any other material that is malicious or technologically harmful.",
      "Scrape, mirror, frame, or otherwise reproduce substantial portions of the Site without our prior written consent.",
      "Use automated systems (bots, crawlers) to access the Site in a way that places an unreasonable load on our infrastructure.",
      "Submit false, misleading, or impersonated information through any form on the Site.",
    ],
  },
  {
    id: "ip",
    title: "4. Intellectual Property",
    paragraphs: [
      "All content on the Site — including the Paris United Group Holding name, brand marks, logos of our subsidiaries and partner brands, text, images, video, audio, source code, layouts, and underlying technology — is owned by or licensed to PUG Holding and is protected by applicable copyright, trademark, and other intellectual-property laws.",
      "You may view, download, and print pages of the Site for your own personal, non-commercial use, provided you do not modify any content and you retain all copyright and proprietary notices. You may not otherwise reproduce, distribute, publish, transmit, modify, create derivative works of, or commercially exploit any content from the Site without our prior written consent.",
    ],
  },
  {
    id: "accounts",
    title: "5. User Submissions",
    paragraphs: [
      "When you submit information to us through the Site — for example, a contact-form enquiry, a career application, or a newsletter signup — you confirm that the information is accurate, that you have the right to share it, and that you are not infringing the rights of any third party. We handle the personal information you submit in accordance with our Privacy Policy.",
      "We may use feedback, comments, and suggestions you voluntarily share with us about our group, our companies, or our services without obligation to you and without compensation.",
    ],
  },
  {
    id: "third-parties",
    title: "6. Third-Party Links & Brand References",
    paragraphs: [
      "The Site may contain links to third-party websites and may reference brands, partners, suppliers, and clients of PUG Holding for informational purposes. We do not control those third-party sites or their content. Inclusion of a link or a brand mark does not imply endorsement; conversely, the absence of a brand does not imply lack of endorsement. Your use of any third-party site is governed by that site's own terms.",
    ],
  },
  {
    id: "no-warranty",
    title: "7. Information Disclaimer",
    paragraphs: [
      "We work to keep the information on this Site accurate and up to date, but the Site and its content are provided on an \"as is\" and \"as available\" basis. Information about products, services, openings, branches, prices, and partners may change without notice. To the maximum extent permitted by law, we make no warranties or representations, express or implied, regarding the accuracy, completeness, reliability, or fitness for a particular purpose of any content on the Site.",
    ],
  },
  {
    id: "liability",
    title: "8. Limitation of Liability",
    paragraphs: [
      "To the maximum extent permitted by applicable law, PUG Holding, its subsidiaries, directors, employees, and agents shall not be liable for any indirect, incidental, special, consequential, or punitive losses or damages arising out of or in connection with your use of, or inability to use, the Site — including, without limitation, loss of profits, business interruption, loss of data, or any error or omission in the content of the Site.",
      "Nothing in these Terms limits any liability that cannot be limited under the applicable law of the State of Qatar.",
    ],
  },
  {
    id: "indemnity",
    title: "9. Indemnity",
    paragraphs: [
      "You agree to indemnify and hold harmless PUG Holding and its subsidiaries, directors, employees, and agents from and against any claims, liabilities, damages, losses, and reasonable costs arising out of your breach of these Terms or your misuse of the Site.",
    ],
  },
  {
    id: "careers",
    title: "10. Careers & Recruitment",
    paragraphs: [
      "Job descriptions published on the Site are provided for information only and do not constitute an offer of employment. Submission of an application does not guarantee an interview, shortlisting, or offer. PUG Holding does not charge applicants any fee at any stage of the recruitment process. Any communication suggesting otherwise is fraudulent and should be reported to us immediately.",
    ],
  },
  {
    id: "privacy",
    title: "11. Privacy",
    paragraphs: [
      "Your use of the Site is also governed by our Privacy Policy, which describes how we collect, use, and safeguard personal information. By using the Site you agree to the practices described in the Privacy Policy.",
    ],
  },
  {
    id: "changes",
    title: "12. Changes to the Site & to These Terms",
    paragraphs: [
      "We may modify, suspend, or discontinue all or any part of the Site at any time, with or without notice. We may also revise these Terms from time to time. The \"last updated\" date at the top of this page indicates when the most recent revision took effect, and the revised Terms apply from that date. Your continued use of the Site after a revision constitutes your acceptance of the revised Terms.",
    ],
  },
  {
    id: "law",
    title: "13. Governing Law & Jurisdiction",
    paragraphs: [
      "These Terms are governed by and construed in accordance with the laws of the State of Qatar. Any dispute arising out of or in connection with these Terms or your use of the Site shall be subject to the exclusive jurisdiction of the competent courts of Qatar, without prejudice to any mandatory dispute-resolution mechanism that may apply between PUG Holding and a contractual counterparty in a separate written agreement.",
    ],
  },
  {
    id: "contact",
    title: "14. Contact",
    paragraphs: [
      "If you have any questions about these Terms or about the Site, please contact us using the details below.",
    ],
  },
];

export default async function TermsAndConditionsPage() {
  const settings = await getSiteSettings();

  return (
    <>
      <PageHero
        eyebrow="Legal"
        title="Terms & Conditions"
        description={`The terms of use that govern your access to the Paris United Group Holding website and the services we provide through it. Last updated ${LAST_UPDATED}.`}
        accent="from-pug-green-700 via-pug-green-500 to-pug-gold-500"
      />

      <Section>
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1fr_3fr]">
          {/* Sticky in-page navigation */}
          <aside className="lg:sticky lg:top-28 lg:self-start">
            <GlassCard className="p-5">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300">
                  <FileText className="h-4 w-4" />
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
                            Legal enquiries
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
