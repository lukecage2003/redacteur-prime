import { describe, expect, it } from "vitest";
import { observedKinds } from "./audience";

describe("observedKinds", () => {
  it("ignore les déclarations et dédoublonne", () => {
    const evidence = [
      { id: "1", kind: "DECLARED", statement: "", data_class: "HYPOTHESIS" },
      { id: "2", kind: "METRIC", statement: "", data_class: "PRIVATE_AUTHORIZED" },
      { id: "3", kind: "METRIC", statement: "", data_class: "PRIVATE_AUTHORIZED" },
      { id: "4", kind: "COMMENT_CLUSTER", statement: "", data_class: "PUBLIC" },
    ];
    expect(observedKinds({ evidence })).toEqual(["COMMENT_CLUSTER", "METRIC"]);
  });
});
