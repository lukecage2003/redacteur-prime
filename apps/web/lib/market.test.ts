import { describe, expect, it } from "vitest";
import { gapLabel, splitKeywords } from "./market";

describe("gapLabel", () => {
  it("ne chiffre jamais sans données", () => {
    expect(gapLabel({ status: "INSUFFICIENT_DATA", gap_score: null })).toBe("données insuffisantes");
  });

  it("qualifie l'écart", () => {
    expect(gapLabel({ status: "SCORED", gap_score: 0.7 })).toBe("écart fort");
    expect(gapLabel({ status: "SCORED", gap_score: 0.2 })).toBe("écart modéré");
    expect(gapLabel({ status: "SCORED", gap_score: 0 })).toBe("saturé en français");
  });
});

describe("splitKeywords", () => {
  it("découpe et nettoie", () => {
    expect(splitKeywords(" sandman, rêve ,, ")).toEqual(["sandman", "rêve"]);
  });
});
