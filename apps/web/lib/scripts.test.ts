import { describe, expect, it } from "vitest";
import { CRITERIA_LABELS, verdict } from "./scripts";

describe("verdict", () => {
  it("le veto l'emporte sur la note", () => {
    expect(verdict({ total: 99, factual_veto: true }, 70)).toBe("veto factuel : non validable");
    expect(verdict({ total: 75, factual_veto: false }, 70)).toBe("validable après relecture humaine");
    expect(verdict({ total: 40, factual_veto: false }, 70)).toBe("à retravailler");
  });

  it("couvre les 8 critères", () => {
    expect(Object.keys(CRITERIA_LABELS)).toHaveLength(8);
  });
});
