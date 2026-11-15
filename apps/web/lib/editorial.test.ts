import { describe, expect, it } from "vitest";
import { canDecline, checkSeverity, MISSION_LABELS } from "./editorial";

describe("canDecline", () => {
  it("n'autorise que les livrables approuvés et déclinables", () => {
    expect(canDecline({ type: "CHARACTER_DOSSIER", status: "APPROVED" })).toBe(true);
    expect(canDecline({ type: "CHARACTER_DOSSIER", status: "AWAITING_APPROVAL" })).toBe(false);
    expect(canDecline({ type: "MARKET_BRIEF", status: "APPROVED" })).toBe(false);
  });
});

describe("checkSeverity", () => {
  it("classe les statuts du Fact Checker", () => {
    expect(checkSeverity("VERIFIED")).toBe("ok");
    expect(checkSeverity("QUOTE_NOT_FOUND")).toBe("error");
    expect(checkSeverity("CONFLICTS_WITH_EVIDENCE")).toBe("error");
    expect(checkSeverity("NO_CITATION")).toBe("review");
    expect(checkSeverity("NOT_FACTUAL")).toBe("neutral");
  });

  it("a un libellé par type de mission", () => {
    expect(Object.keys(MISSION_LABELS)).toEqual([
      "CHARACTER_DOSSIER",
      "CONTINUITY_AUDIT",
      "FACT_CHECK",
      "THEORY_REVIEW",
      "RESEARCH_DOSSIER",
      "MARKET_BRIEF",
      "SOCIAL_PACKAGE",
      "SCRIPT_REVIEW",
      "PERFORMANCE_REVIEW",
      "AUDIENCE_BRIEF",
      "OPPORTUNITY_BRIEF",
      "PACKAGING_REVIEW",
      "VIDEO_AUTOPSY",
    ]);
  });
});
