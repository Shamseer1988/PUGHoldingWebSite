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
import { getLeadership, getSiteSettings } from "@/lib/public-api";

export const metadata = { title: "About Us" };
export const revalidate = 60;

export default async function AboutPage() {
  const [leadership, settings] = await Promise.all([
    getLeadership(),
    getSiteSettings(),
  ]);

  return (
    <>
      <PageHero
        eyebrow={ABOUT_INTRO.eyebrow}
        title={ABOUT_INTRO.title}
        description={ABOUT_INTRO.description}
        accent="from-pug-green-700 via-pug-green-500 to-pug-gold-500"
        imageUrl={settings.about_banner_image_url}
        videoUrl={settings.about_banner_video_url}
      />

      <Section
        eyebrow="Our purpose"
        title="Vision and mission"
        description="Long-term in horizon, customer-centric in design."
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <GlassCard className="p-6 sm:p-8">
            <h3 className="text-lg font-semibold sm:text-xl">{VISION.title}</h3>
            <p className="mt-3 text-muted-foreground sm:text-lg">{VISION.body}</p>
          </GlassCard>
          <GlassCard className="p-6 sm:p-8">
            <h3 className="text-lg font-semibold sm:text-xl">{MISSION.title}</h3>
            <p className="mt-3 text-muted-foreground sm:text-lg">{MISSION.body}</p>
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
              We started with one focused FMCG distribution business and grew
              into a diversified group operating across retail, distribution,
              and services — guided by the same values throughout.
            </p>
          </div>
          <Timeline />
        </div>
      </Section>

      {leadership.length > 0 && (
        <Section
          id="leadership"
          eyebrow="Leadership"
          title="Messages from our leadership"
          description="The Chairman, Managing Director, and Executive Directors."
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
