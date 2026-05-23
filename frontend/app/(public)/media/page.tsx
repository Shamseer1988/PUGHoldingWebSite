import { ComingSoon } from "@/components/site/coming-soon";

export const metadata = { title: "Media" };

export default function MediaPage() {
  return (
    <ComingSoon
      phaseLabel="Coming in Phase 4 (UI) · Phase 5 + 6 (wired)"
      title="Media Gallery"
      description="Photo and video gallery with category filters, lightbox viewer, masonry grid, and smooth hover animations."
      features={[
        "Photo and video gallery",
        "Category filters",
        "Lightbox viewer",
        "Responsive masonry / grid layout",
        "Smooth hover animations",
      ]}
    />
  );
}
