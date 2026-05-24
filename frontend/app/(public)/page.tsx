import Link from "next/link";
import { ArrowRight, Briefcase, MessageSquare, Phone } from "lucide-react";

import { FeaturedCompaniesShowcase } from "@/components/site/featured-companies-showcase";
import { HeroSlider } from "@/components/site/hero-slider";
import { HomeAboutSection } from "@/components/site/home-about-section";
import { HomeBrandStrip } from "@/components/site/home-brand-strip";
import { JobCard } from "@/components/site/job-card";
import { LeadershipMessagesSection } from "@/components/site/leadership-messages-section";
import { NewsCard } from "@/components/site/news-card";
import { NewsletterForm } from "@/components/site/newsletter-form";
import { Section } from "@/components/site/section";
import { SectorCards } from "@/components/site/sector-cards";
import { StatsStrip } from "@/components/site/stats-strip";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/site/glass-card";
import {
  getFeaturedCompaniesSection,
  getHeroSlides,
  getHomepageLeadership,
  getNews,
  getPublicJobs,
  getSiteSettings,
} from "@/lib/public-api";

export const revalidate = 60;

export default async function HomePage() {
  const [hero, featured, leadershipSection, news, settings, openJobs] =
    await Promise.all([
      getHeroSlides(),
      getFeaturedCompaniesSection(),
      getHomepageLeadership(),
      getNews({ limit: 3 }),
      getSiteSettings(),
      getPublicJobs(),
    ]);

  const phone = settings.contact_phone ?? "+974 0000 0000";
  const whatsapp = settings.whatsapp_number ?? "+97400000000";

  return (
    <>
      {hero.length > 0 && <HeroSlider slides={hero} />}

      <Section
        eyebrow="Business overview"
        title="A snapshot of Paris United Group"
        description="Operating at scale across distribution, retail, and services — these numbers grow with every new store, new partnership, and new hire."
        centered
      >
        <StatsStrip />
      </Section>

      <HomeAboutSection
        imageUrl={settings.home_about_image_url}
        title={settings.home_about_title}
        body={settings.home_about_body}
      />

      <Section
        eyebrow="Our business sectors"
        title="Three pillars, one group"
        description="Each sector is led by experienced operators and supported by group-level investment in technology, talent, and supply chain."
        centered
      >
        <SectorCards />
      </Section>

      <FeaturedCompaniesShowcase
        section={featured.section}
        companies={featured.companies}
      />

      <LeadershipMessagesSection data={leadershipSection} />

      <HomeBrandStrip
        logos={settings.home_brand_logos}
        title={settings.home_brand_strip_title}
      />

      {news.length > 0 && (
        <Section
          eyebrow="Latest news"
          title="What's happening at Paris United Group"
        >
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {news.map((item) => (
              <NewsCard key={item.slug} item={item} />
            ))}
          </div>
          <div className="mt-8 text-center">
            <Button asChild variant="outline">
              <Link href="/news">
                All news and events
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </Section>
      )}

      <Section className="py-16 sm:py-20">
        <GlassCard className="relative overflow-hidden p-8 sm:p-10 lg:p-12">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-primary/20 blur-3xl"
          />
          <div className="grid items-center gap-8 lg:grid-cols-[1.5fr_2fr]">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                <Briefcase className="h-3.5 w-3.5 text-primary" />
                Careers
              </span>
              <h2 className="mt-3 text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
                Join one of Qatar's most diversified groups
              </h2>
              <p className="mt-2 text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {openJobs.length}
                </span>{" "}
                roles currently open across retail, distribution, services,
                engineering, and corporate functions.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Button asChild>
                  <Link href="/careers">
                    Browse open roles
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="ghost">
                  <Link href="/about">Why join us</Link>
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {openJobs.slice(0, 2).map((job) => (
                <JobCard key={job.slug} job={job} />
              ))}
            </div>
          </div>
        </GlassCard>
      </Section>

      <Section
        eyebrow="Stay in touch"
        title="Reach out or sign up for updates"
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <GlassCard className="p-6">
            <h3 className="text-lg font-semibold">Contact our team</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Use any of the channels below or send us a message directly
              from the contact page.
            </p>
            <ul className="mt-5 space-y-3 text-sm">
              <li className="flex items-center gap-3">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <Phone className="h-4 w-4" />
                </span>
                <div>
                  <p className="font-medium">{phone}</p>
                  <p className="text-xs text-muted-foreground">Sun – Thu · 8am – 6pm</p>
                </div>
              </li>
              <li className="flex items-center gap-3">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <MessageSquare className="h-4 w-4" />
                </span>
                <div>
                  <p className="font-medium">WhatsApp business</p>
                  <p className="text-xs text-muted-foreground">{whatsapp}</p>
                </div>
              </li>
            </ul>
            <div className="mt-6">
              <Button asChild>
                <Link href="/contact">
                  Open contact form
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </GlassCard>

          <GlassCard className="p-6">
            <h3 className="text-lg font-semibold">Newsletter</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Occasional updates from Paris United Group — new openings,
              store launches, and CSR initiatives.
            </p>
            <div className="mt-5">
              <NewsletterForm />
            </div>
          </GlassCard>
        </div>
      </Section>
    </>
  );
}
