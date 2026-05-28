import { CareersView } from "@/app/(public)/careers/careers-view";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getPublicJobs, getSitePage } from "@/lib/public-api";

export const metadata = { title: "Careers" };
// Phase A-1: listing — refresh every 5 min.
export const revalidate = 300;

export default async function CareersPage() {
  const [jobs, page] = await Promise.all([
    getPublicJobs(),
    getSitePage("careers"),
  ]);

  return (
    <>
      <PageHero
        eyebrow={page?.hero_eyebrow ?? "Careers"}
        title={page?.hero_title ?? "Build your career with Paris United Group"}
        description={
          page?.hero_description ??
          "Roles across retail operations, FMCG sales, engineering, real estate, services, HR, and group functions."
        }
        accent="from-pug-green-600 via-pug-green-500 to-pug-gold-500"
        imageUrl={page?.banner_image_url}
        mobileImageUrl={page?.banner_mobile_url}
        videoUrl={page?.banner_video_url}
      />

      <Section className="pt-10">
        <CareersView jobs={jobs} />
      </Section>
    </>
  );
}
