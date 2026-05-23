import { ComingSoon } from "@/components/site/coming-soon";

export const metadata = { title: "About Us" };

export default function AboutPage() {
  return (
    <ComingSoon
      phaseLabel="Coming in Phase 4"
      title="About Paris United Group"
      description="A detailed company introduction with vision, mission, core values, history timeline, business philosophy, quality commitment, and full Chairman / MD / Executive Directors messages."
      features={[
        "Group introduction and vision",
        "Mission and core values",
        "History timeline",
        "Business philosophy",
        "Quality commitment",
        "Chairman / MD / Executive Directors messages",
      ]}
    />
  );
}
