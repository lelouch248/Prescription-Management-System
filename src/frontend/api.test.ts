import { describe, expect, it } from "vitest";
import { displayDate, toLocalInput } from "./api";

describe("date presentation", () => {
  it("keeps unknown values explicit", () => {
    expect(displayDate(null)).toBe("Not recorded");
  });

  it("creates a local datetime input without a trailing timezone", () => {
    const value = toLocalInput(new Date("2026-08-10T10:30:00Z"));
    expect(value).toMatch(/^2026-08-10T\d{2}:\d{2}$/);
    expect(value).not.toContain("Z");
  });
});
