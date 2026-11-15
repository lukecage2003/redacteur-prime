import { describe, expect, it } from "vitest";
import { canDeclare } from "./distribution";

describe("canDeclare", () => {
  it("n'autorise la déclaration qu'après approbation", () => {
    expect(canDeclare({ status: "APPROVED" })).toBe(true);
    expect(canDeclare({ status: "PROPOSED" })).toBe(false);
    expect(canDeclare({ status: "PUBLISHED" })).toBe(false);
  });
});
