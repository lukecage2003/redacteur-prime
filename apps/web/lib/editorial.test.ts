import { describe, expect, it } from "vitest";
import { checkSeverity, MISSION_LABELS } from "./editorial";

describe("checkSeverity", () => {
  it("classe les statuts du Fact Checker", () => {
    expect(checkSeverity("VERIFIED")).toBe("ok");
    expect(checkSeverity("QUOTE_NOT_FOUND")).toBe("error");
    expect(checkSeverity("CONFLICTS_WITH_EVIDENCE")).toBe("error");
    expect(checkSeverity("NO_CITATION")).toBe("review");
    expect(checkSeverity("NOT_FACTUAL")).toBe("neutral");
  });

  it("a un libellé par type de mission", () => {
    expect(Object.keys(MISSION_LABELS)).toEqual(["CHARACTER_DOSSIER", "CONTINUITY_AUDIT", "FACT_CHECK"]);
  });
});
