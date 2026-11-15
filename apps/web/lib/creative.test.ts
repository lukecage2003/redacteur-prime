import { describe, expect, it } from "vitest";
import { usableTitles } from "./creative";

describe("usableTitles", () => {
  it("écarte les titres malhonnêtes ou illisibles", () => {
    const titles = [
      { title: "A", honest: true, issues: [], readability: ["lisible"], audience_fit: ["adapté"] },
      { title: "B", honest: false, issues: ["x"], readability: ["lisible"], audience_fit: ["adapté"] },
      { title: "C", honest: true, issues: [], readability: ["trop long"], audience_fit: ["adapté"] },
    ];
    expect(usableTitles({ titles }).map((t) => t.title)).toEqual(["A"]);
  });
});
