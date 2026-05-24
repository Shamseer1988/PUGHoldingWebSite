import { Section } from "@/components/site/section";
import { resolveAssetUrl } from "@/lib/public-api";

interface HomeBrandStripProps {
  logos: string | null;
  title: string | null;
}

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
          <p className="text-center text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
            {title}
          </p>
        )}
        <div className="grid grid-cols-3 items-center gap-x-6 gap-y-6 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-10">
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
                className="max-h-12 w-auto opacity-70 transition-opacity hover:opacity-100 dark:opacity-80 dark:invert-0 sm:max-h-14"
              />
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}
