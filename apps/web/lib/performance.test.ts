import { describe, expect, it } from "vitest";
import { METRIC_LABELS, signalStrength } from "./performance";

describe("signalStrength", () => {
  it("qualifie la corrélation, signe ignoré", () => {
    expect(signalStrength(0.8)).toBe("fort");
    expect(signalStrength(-0.6)).toBe("modéré");
    expect(signalStrength(0.2)).toBe("faible");
  });

  it("a un libellé par métrique stockable", () => {
    expect(Object.keys(METRIC_LABELS)).toHaveLength(9);
  });
});
