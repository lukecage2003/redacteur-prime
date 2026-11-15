import { describe, expect, it } from "vitest";
import { rightsUsable } from "./memory";

describe("rightsUsable", () => {
  it("écarte les droits retirés ou échus", () => {
    expect(rightsUsable({ status: "ACTIVE", expired: false })).toBe(true);
    expect(rightsUsable({ status: "ACTIVE", expired: true })).toBe(false);
    expect(rightsUsable({ status: "WITHDRAWN", expired: false })).toBe(false);
  });
});
