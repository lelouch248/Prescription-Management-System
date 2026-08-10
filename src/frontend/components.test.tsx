import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge, Brand, EmptyState } from "./components";

describe("shared accessible components", () => {
  it("renders the product identity and empty-state guidance", () => {
    render(
      <>
        <Brand />
        <EmptyState
          title="No documents yet"
          description="Upload an original."
        />
      </>,
    );
    expect(screen.getByText("HealthVault")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "No documents yet" }),
    ).toBeInTheDocument();
  });

  it("exposes verification status as text, not color alone", () => {
    render(<Badge tone="warning">Unverified</Badge>);
    expect(screen.getByText("Unverified")).toBeVisible();
  });
});
