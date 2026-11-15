import { describe, expect, it } from "vitest";
import { experimentVerdict, METRIC_LABELS, signalStrength } from "./performance";

describe("experimentVerdict", () => {
  it("ne déclare un gagnant que conclu", () => {
    expect(experimentVerdict({ status: "CONCLUDED", result: { winner: "A", reason: "" } })).toContain("variante A");
    expect(experimentVerdict({ status: "INCONCLUSIVE", result: { winner: null, reason: "échantillon insuffisant" } })).toContain("échantillon insuffisant");
    expect(experimentVerdict({ status: "RUNNING", result: null })).toBe("en cours");
  });
});

describe("signalStrength", () => {
  it("qualifie la corrélation, signe ignoré", () => {
    expect(signalStrength(0.8)).toBe("fort");
    expect(signalStrength(-0.6)).toBe("modéré");
    expect(signalStrength(0.2)).toBe("faible");
  });

  it("a un libellé par métrique stockable", () => {
    expect(Object.keys(METRIC_LABELS).length).toBeGreaterThanOrEqual(9);
  });
});
