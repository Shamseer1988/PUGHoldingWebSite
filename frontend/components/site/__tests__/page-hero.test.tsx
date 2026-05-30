/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { PageHero } from "../page-hero";


// ---------------------------------------------------------------------------
// PageHero size variants — guard against accidentally shifting the existing
// 13 pages that already consume this component. The ``default`` branch MUST
// produce the original ``py-16 sm:py-20 lg:py-24`` padding; the ``compact``
// branch is the half-height variant the Offers landing opts into.
// ---------------------------------------------------------------------------


function getInnerWrapper(container: HTMLElement): HTMLElement {
  // The hero renders a <section> with a single ``container mx-auto …`` div
  // immediately inside, which is the element whose ``py-*`` classes set the
  // vertical scale. Walk down to find it without coupling to deeper layout
  // details that might change.
  const wrapper = container.querySelector<HTMLElement>(
    "section > div.container",
  );
  if (!wrapper) {
    throw new Error("PageHero inner container wrapper not found in render");
  }
  return wrapper;
}


describe("PageHero size variant", () => {
  it("omitted size renders the original padding (every other page stays put)", () => {
    const { container } = render(<PageHero title="Existing page" />);
    const cls = getInnerWrapper(container).className;
    expect(cls).toContain("py-16");
    expect(cls).toContain("sm:py-20");
    expect(cls).toContain("lg:py-24");
    expect(cls).not.toContain("py-8");
    expect(cls).not.toContain("sm:py-10");
    expect(cls).not.toContain("lg:py-12");
  });

  it('size="default" matches the omitted-size behaviour', () => {
    const { container } = render(
      <PageHero size="default" title="Explicit default" />,
    );
    const cls = getInnerWrapper(container).className;
    expect(cls).toContain("py-16 sm:py-20 lg:py-24");
  });

  it('size="compact" halves the vertical padding', () => {
    const { container } = render(
      <PageHero size="compact" title="Offers landing" />,
    );
    const cls = getInnerWrapper(container).className;
    expect(cls).toContain("py-8");
    expect(cls).toContain("sm:py-10");
    expect(cls).toContain("lg:py-12");
    // Crucially the default scale must NOT leak through.
    expect(cls).not.toContain("py-16");
    expect(cls).not.toContain("sm:py-20");
    expect(cls).not.toContain("lg:py-24");
  });
});
