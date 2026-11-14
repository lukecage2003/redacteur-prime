import { describe, expect, it } from "vitest";
import { describeRelation, fetchEntities, type RelationView } from "./knowledge";

const relation: RelationView = {
  id: "r",
  type: "APPEARS_IN",
  qualifier: null,
  level: "CANON",
  confidence: 1,
  origin: "EXTRACTOR",
  retracted: false,
  source: { id: "selina", name: "Selina" },
  target: { id: "comic", name: "Nuit noire #1" },
  evidence: [],
};

describe("describeRelation", () => {
  it("décrit une relation sortante et entrante", () => {
    expect(describeRelation(relation, "selina")).toBe("apparaît dans → Nuit noire #1");
    expect(describeRelation(relation, "comic")).toBe("Selina → apparaît dans (cette entité)");
    expect(describeRelation({ ...relation, qualifier: "se présente comme" }, "selina")).toBe(
      "se présente comme → Nuit noire #1",
    );
  });
});

describe("fetchEntities", () => {
  it("encode la recherche et tolère une API absente", async () => {
    let seen = "";
    const fake = (async (url: string) => {
      seen = url;
      return new Response("[]", { status: 200 });
    }) as unknown as typeof fetch;
    expect(await fetchEntities("Cat woman&x", "http://api.test", fake)).toEqual([]);
    expect(seen).toBe("http://api.test/api/v1/knowledge/entities?q=Cat%20woman%26x");
    const down = (async () => {
      throw new Error("down");
    }) as unknown as typeof fetch;
    expect(await fetchEntities(undefined, "http://api.test", down)).toBeNull();
  });
});
