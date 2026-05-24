import { Reveal, RevealGroup } from "@/components/site/reveal";
import { Section } from "@/components/site/section";
import { resolveAssetUrl } from "@/lib/public-api";

interface HomeBrandStripProps {
  logos: string | null;
  title: string | null;
}

/**
 * Logo wall used on the home page.
 *
 * The whole strip fades up when it enters the viewport. Individual
 * logos stagger in with a soft scale via `RevealGroup` so the row
 * "writes itself" rather than appearing at once, and each tile lifts
 * + boosts opacity on hover for a tactile, modern feel.
 */
export function HomeBrandStrip({ logos, title }: HomeBrandStripProps) {
  const items = (logos ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((url) => resolveAssetUrl(url))
    .filter((url): url is string => Boolean(url));

  if (items.length === 0) return null;

  return (
    <Section className="py-12 sm:py-16">
      <div className="space-y-6">
        {title && (
          <Reveal direction="fade">
            <p className="text-center text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
              {title}
            </p>
          </Reveal>
        )}
        <RevealGroup
          className="grid grid-cols-3 items-center gap-x-6 gap-y-6 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-10"
          stagger={0.04}
          direction="zoom"
          duration={0.5}
        >
          {items.map((url, idx) => (
            <div
              key={`${url}-${idx}`}
              className="flex items-center justify-center"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={url}
                alt=""
                loading="lazy"
                className="max-h-12 w-auto opacity-70 grayscale transition-all duration-300 hover:-translate-y-0.5 hover:opacity-100 hover:grayscale-0 dark:opacity-80 sm:max-h-14"
              />
            </div>
          ))}
        </RevealGroup>
      </div>
    </Section>
  );
}
