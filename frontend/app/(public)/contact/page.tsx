import { ComingSoon } from "@/components/site/coming-soon";

export const metadata = { title: "Contact Us" };

export default function ContactPage() {
  return (
    <ComingSoon
      phaseLabel="Coming in Phase 4 (UI) · Phase 5 + 6 (wired)"
      title="Contact Paris United Group"
      description="Send us a message routed to the right department, see our location, phone, email, and use quick actions like WhatsApp / call / directions."
      features={[
        "Contact form with department routing",
        "Office address, phone, email",
        "Embedded map placeholder",
        "WhatsApp / phone / email quick actions",
        "Inbox in the website admin (Phase 5)",
      ]}
    />
  );
}
