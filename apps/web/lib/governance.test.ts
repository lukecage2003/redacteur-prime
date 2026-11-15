import { describe, expect, it } from "vitest";
import { allowedDecisions } from "./governance";

describe("allowedDecisions", () => {
  it("n'offre que les transitions permises", () => {
    expect(allowedDecisions("PROPOSED")).toEqual(["approve", "reject"]);
    expect(allowedDecisions("APPROVED")).toEqual(["revert"]);
    expect(allowedDecisions("REJECTED")).toEqual([]);
    expect(allowedDecisions("REVERTED")).toEqual([]);
  });
});
