import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Users } from "lucide-react";

import { KpiCard } from "@/components/hr/kpi-card";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("KpiCard", () => {
  test("renders a deep link with the label and formatted value", () => {
    render(
      <KpiCard
        label="Selected"
        value={1234}
        href="/hr/candidates?status=selected"
        icon={Users}
        tone="ready"
      />,
    );
    const link = screen.getByRole("link", { name: /Selected/ });
    expect(link).toHaveAttribute("href", "/hr/candidates?status=selected");
    // Number is locale-formatted.
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("Selected")).toBeInTheDocument();
  });

  test("renders string values verbatim and an optional delta", () => {
    render(
      <KpiCard
        label="No-show rate"
        value="8%"
        href="/hr/onboarding"
        icon={Users}
        delta="last 90 days"
      />,
    );
    expect(screen.getByText("8%")).toBeInTheDocument();
    expect(screen.getByText("last 90 days")).toBeInTheDocument();
  });
});
