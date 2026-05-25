import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement matchMedia — provide a safe default so
// components that call `window.matchMedia` during render don't blow up.
// Individual tests can override via `vi.spyOn(window, "matchMedia")` to
// simulate `prefers-reduced-motion: reduce`.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// jsdom also lacks IntersectionObserver, which framer-motion's
// `useInView` polyfills through but still throws if completely absent
// from the global scope.
if (typeof globalThis.IntersectionObserver === "undefined") {
  class MockIntersectionObserver implements IntersectionObserver {
    readonly root: Element | Document | null = null;
    readonly rootMargin: string = "";
    readonly thresholds: ReadonlyArray<number> = [];
    constructor(_callback: IntersectionObserverCallback) {}
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
    takeRecords(): IntersectionObserverEntry[] { return []; }
  }
  (globalThis as { IntersectionObserver: typeof IntersectionObserver }).IntersectionObserver =
    MockIntersectionObserver;
}
