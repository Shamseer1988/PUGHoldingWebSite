import { ComingSoon } from "@/components/site/coming-soon";

export const metadata = { title: "Group Companies" };

export default function CompaniesPage() {
  return (
    <ComingSoon
      phaseLabel="Coming in Phase 4"
      title="Group Companies"
      description="Browse every Paris United Group company across Distribution, Retail, and Services with category filters, glassmorphism cards, and detail pages."
      features={[
        "Category filters (Distribution / Retail / Services)",
        "Company cards with logo, name, services",
        "Branch counts where applicable",
        "Detail pages with banner, gallery, contacts",
        "Related companies",
      ]}
    />
  );
}
