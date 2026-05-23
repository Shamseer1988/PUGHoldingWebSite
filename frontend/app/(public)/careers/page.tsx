import { ComingSoon } from "@/components/site/coming-soon";

export const metadata = { title: "Careers" };

export default function CareersPage() {
  return (
    <ComingSoon
      phaseLabel="Coming in Phase 4 (UI) · Phase 9 + 10 (wired)"
      title="Build your career with Paris United Group"
      description="Browse open positions across every group company, filter by department / company / location / employment type, and apply with your CV."
      features={[
        "Job search with multi-filter panel",
        "Job category, department, company, location filters",
        "Job detail pages",
        "Apply Now form with CV upload",
        "Candidate applications stored in the HR ATS",
      ]}
    />
  );
}
