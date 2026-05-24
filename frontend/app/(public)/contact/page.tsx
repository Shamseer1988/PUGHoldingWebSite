import Link from "next/link";
import {
  ArrowRight,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
} from "lucide-react";

import { ContactForm } from "@/components/site/contact-form";
import { GlassCard } from "@/components/site/glass-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { Button } from "@/components/ui/button";
import { parseContactMapEmbed } from "@/lib/contact-map";
import { getSiteSettings } from "@/lib/public-api";

export const metadata = { title: "Contact Us" };
export const revalidate = 60;

export default async function ContactPage() {
  const settings = await getSiteSettings();
  const mapEmbed = parseContactMapEmbed(settings.contact_map_embed);

  const contactRows = [
    settings.contact_address && {
      icon: <MapPin className="h-4 w-4" />,
      label: "Address",
      value: settings.contact_address,
      href: undefined,
    },
    settings.contact_phone && {
      icon: <Phone className="h-4 w-4" />,
      label: "Phone",
      value: settings.contact_phone,
      href: `tel:${settings.contact_phone.replace(/\s/g, "")}`,
    },
    settings.contact_email && {
      icon: <Mail className="h-4 w-4" />,
      label: "Email",
      value: settings.contact_email,
      href: `mailto:${settings.contact_email}`,
    },
  ].filter(Boolean) as Array<{
    icon: React.ReactNode;
    label: string;
    value: string;
    href?: string;
  }>;

  const phoneHref = settings.contact_phone
    ? `tel:${settings.contact_phone.replace(/\s/g, "")}`
    : "tel:+9740000000000";
  const whatsappHref = settings.whatsapp_number
    ? `https://wa.me/${settings.whatsapp_number.replace(/[^0-9]/g, "")}`
    : "https://wa.me/97400000000";

  return (
    <>
      <PageHero
        eyebrow="Contact"
        title="Talk to Paris United Group"
        description="Reach the right department fast. Use the form below or any of the quick actions on the right."
        accent="from-pug-gold-500 via-pug-gold-600 to-pug-green-600"
        imageUrl={settings.contact_banner_image_url}
        mobileImageUrl={settings.contact_banner_mobile_url}
      />

      <Section className="pt-12">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[2fr_1fr]">
          <GlassCard className="p-6 sm:p-8">
            <h2 className="text-xl font-semibold tracking-tight">
              Send us a message
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Select a department and we'll route your message to the right team.
            </p>
            <div className="mt-6">
              <ContactForm />
            </div>
          </GlassCard>

          <aside className="space-y-4">
            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Reach us directly</h3>
              {contactRows.length === 0 ? (
                <p className="mt-3 text-sm text-muted-foreground">
                  Contact details will appear here once site settings are
                  configured in the admin panel.
                </p>
              ) : (
                <ul className="mt-4 space-y-3 text-sm">
                  {contactRows.map((row) => {
                    const inner = (
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
                          {row.icon}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-muted-foreground">
                            {row.label}
                          </p>
                          <p className="break-words font-medium">
                            {row.value}
                          </p>
                        </div>
                      </div>
                    );
                    return (
                      <li key={row.label}>
                        {row.href ? (
                          <Link href={row.href} className="hover:text-foreground">
                            {inner}
                          </Link>
                        ) : (
                          inner
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </GlassCard>

            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Quick actions</h3>
              <div className="mt-4 flex flex-col gap-2">
                <Button asChild>
                  <Link href={phoneHref}>
                    <Phone className="h-4 w-4" />
                    Call us
                  </Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href={whatsappHref} target="_blank">
                    <MessageCircle className="h-4 w-4" />
                    WhatsApp
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </GlassCard>

            <GlassCard className="overflow-hidden p-0">
              {mapEmbed.safeSrc ? (
                <div className="relative aspect-[4/3] w-full">
                  <iframe
                    title="Office location map"
                    src={mapEmbed.safeSrc}
                    loading="lazy"
                    referrerPolicy="no-referrer-when-downgrade"
                    allowFullScreen
                    className="absolute inset-0 h-full w-full border-0"
                  />
                </div>
              ) : (
                <div
                  aria-hidden
                  className="flex aspect-[4/3] w-full items-center justify-center bg-gradient-to-br from-pug-green-500/30 via-pug-gold-500/30 to-pug-green-700/30 p-6 text-center text-sm font-medium text-muted-foreground"
                >
                  Map will appear here once an embed is added under
                  Admin&nbsp;&rarr;&nbsp;Site&nbsp;Settings&nbsp;&rarr;&nbsp;Contact.
                </div>
              )}
            </GlassCard>
          </aside>
        </div>
      </Section>
    </>
  );
}
