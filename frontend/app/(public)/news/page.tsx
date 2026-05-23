import { ComingSoon } from "@/components/site/coming-soon";

export const metadata = { title: "News & Events" };

export default function NewsPage() {
  return (
    <ComingSoon
      phaseLabel="Coming in Phase 4"
      title="News & Events"
      description="Latest announcements, featured stories, event schedule, and rich news detail pages with image galleries and social sharing."
      features={[
        "Search and category filters",
        "Featured news strip",
        "News and event detail pages",
        "Image galleries inside articles",
        "Social share buttons",
      ]}
    />
  );
}
