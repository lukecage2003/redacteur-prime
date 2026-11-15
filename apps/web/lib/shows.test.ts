import { describe, expect, it } from "vitest";
import { acceptsEpisodes, nextStatuses } from "./shows";

describe("cycle de vie des émissions", () => {
  it("suit les transitions autorisées par le serveur", () => {
    expect(nextStatuses("DRAFT")).toEqual(["TESTING", "RETIRED"]);
    expect(nextStatuses("SUSPENDED")).toContain("ACTIVE");
    expect(nextStatuses("RETIRED")).toEqual([]);
  });
  it("refuse les épisodes hors test et activité", () => {
    expect(acceptsEpisodes("ACTIVE")).toBe(true);
    expect(acceptsEpisodes("SUSPENDED")).toBe(false);
    expect(acceptsEpisodes("DRAFT")).toBe(false);
  });
});
