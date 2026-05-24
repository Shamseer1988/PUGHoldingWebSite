import { CareersView } from "@/app/(public)/careers/careers-view";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getPublicJobs, getSiteSettings } from "@/lib/public-api";

export const metadata = { title: "Careers" };
export const revalidate = 60;

export default async function CareersPage() {
  const [jobs, settings] = await Promise.all([
    getPublicJobs(),
    getSiteSettings(),
  ]);

  return (
    <>
      <PageHero
        eyebrow="Careers"
        title="Build your career with Paris United Group"
        description="Roles across retail operations, FMCG sales, engineering, real estate, services, HR, and group functions."
        accent="from-pug-green-600 via-pug-green-500 to-pug-gold-500"
        imageUrl={settings.careers_banner_image_url}
        mobileImageUrl={settings.careers_banner_mobile_url}
      />

      <Section className="pt-10">
        <CareersView jobs={jobs} />
      </Section>
    </>
  );
}
