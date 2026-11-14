import { describe, expect, it } from "vitest";
import { EVIDENCE_STATE_LABELS, evidenceState, percent, STATUS_LABELS } from "./lab";

const base = { retracted_at: null, excerpt: "Je suis Catwoman", verified: true, still_found: true };

describe("evidenceState", () => {
  it("distingue les états d'une preuve", () => {
    expect(evidenceState(base)).toBe("verified");
    expect(evidenceState({ ...base, retracted_at: "2026-11-14" })).toBe("retracted");
    expect(evidenceState({ ...base, still_found: false })).toBe("stale");
    expect(evidenceState({ ...base, excerpt: null, still_found: null })).toBe("visual");
    expect(evidenceState({ ...base, verified: false, still_found: null })).toBe("unverified");
  });

  it("a un libellé par état et par statut", () => {
    expect(Object.keys(EVIDENCE_STATE_LABELS)).toHaveLength(5);
    expect(Object.keys(STATUS_LABELS)).toEqual(["OPEN", "SUPPORTED", "CONTESTED", "REFUTED"]);
  });
});

describe("percent", () => {
  it("arrondit la confiance", () => {
    expect(percent(0.5)).toBe("50 %");
    expect(percent(0.833)).toBe("83 %");
  });
});
