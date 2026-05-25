import { GlassCard } from "@/components/site/glass-card";
import { LeadershipCard } from "@/components/site/leadership-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { Timeline } from "@/components/site/timeline";
import {
  ABOUT_INTRO,
  CORE_VALUES,
  MISSION,
  VISION,
} from "@/lib/dummy-data/site-content";
import { getLeadership, getSitePage } from "@/lib/public-api";

export const metadata = { title: "About Us" };
export const revalidate = 60;

export default async function AboutPage() {
  const [leadership, page] = await Promise.all([
    getLeadership(),
    getSitePage("about"),
  ]);

  // Hero — CMS row first, dummy data as the safety net.
  const heroEyebrow = page?.hero_eyebrow ?? ABOUT_INTRO.eyebrow;
  const heroTitle = page?.hero_title ?? ABOUT_INTRO.title;
  const heroDescription = page?.hero_description ?? ABOUT_INTRO.description;

  // Named sections — same fallback strategy. ``page.sections`` is an
  // empty object on a fresh install, so ``?.title`` is null → we use
  // the hardcoded copy that ships with the bundle.
  const vision = page?.sections?.vision;
  const mission = page?.sections?.mission;
  const historyIntro = page?.sections?.history_intro;
  const leadershipHeader = page?.sections?.leadership_header;

  return (
    <>
      <PageHero
        eyebrow={heroEyebrow ?? undefined}
        title={heroTitle ?? ABOUT_INTRO.title}
        description={heroDescription ?? undefined}
        accent="from-pug-green-700 via-pug-green-500 to-pug-gold-500"
        imageUrl={page?.banner_image_url}
        mobileImageUrl={page?.banner_mobile_url}
        videoUrl={page?.banner_video_url}
      />

      <Section
        eyebrow="Our purpose"
        title="Vision and mission"
        description="Long-term in horizon, customer-centric in design."
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <GlassCard className="p-6 sm:p-8">
            <h3 className="text-lg font-semibold sm:text-xl">
              {vision?.title ?? VISION.title}
            </h3>
            <p className="mt-3 text-muted-foreground sm:text-lg">
              {vision?.body ?? VISION.body}
            </p>
          </GlassCard>
          <GlassCard className="p-6 sm:p-8">
            <h3 className="text-lg font-semibold sm:text-xl">
              {mission?.title ?? MISSION.title}
            </h3>
            <p className="mt-3 text-muted-foreground sm:text-lg">
              {mission?.body ?? MISSION.body}
            </p>
          </GlassCard>
        </div>
      </Section>

      <Section
        eyebrow="What we believe"
        title="Our core values"
        description="The principles that show up in every business we run."
        centered
      >
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {CORE_VALUES.map((value) => {
            const Icon = value.icon;
            return (
              <GlassCard key={value.title} className="h-full p-5">
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-base font-semibold">{value.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {value.description}
                </p>
              </GlassCard>
            );
          })}
        </div>
      </Section>

      <Section
        eyebrow="Our history"
        title="From a single division to a diversified group"
        description="Key milestones across the last two decades of growth."
      >
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1fr_2fr]">
          <div>
            <p className="text-sm text-muted-foreground">
              {historyIntro?.body ??
                "We started with one focused FMCG distribution business and grew into a diversified group operating across retail, distribution, and services — guided by the same values throughout."}
            </p>
          </div>
          <Timeline />
        </div>
      </Section>

      {leadership.length > 0 && (
        <Section
          id="leadership"
          eyebrow={leadershipHeader?.eyebrow ?? "Leadership"}
          title={leadershipHeader?.title ?? "Messages from our leadership"}
          description={
            leadershipHeader?.body ??
            "The Chairman, Managing Director, and Executive Directors."
          }
        >
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {leadership.map((leader) => (
              <LeadershipCard key={leader.id} leader={leader} full />
            ))}
          </div>
        </Section>
      )}
    </>
  );
}
