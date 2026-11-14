import { describe, expect, it } from "vitest";
import { isUuid, requirePageNumber, requireUuid } from "./ids";

describe("validation des identifiants", () => {
  it("accepte un UUID et le normalise", () => {
    expect(requireUuid("9E049411-131C-4051-828D-5748E36E331A")).toBe("9e049411-131c-4051-828d-5748e36e331a");
  });

  it.each(["", "../../admin", "9e049411-131c-4051-828d-5748e36e331a/../x", "http://evil.test", "%2e%2e"])(
    "refuse %s",
    (value) => {
      expect(isUuid(value)).toBe(false);
      expect(() => requireUuid(value)).toThrow();
    },
  );

  it("valide les numéros de page", () => {
    expect(requirePageNumber(3)).toBe(3);
    for (const bad of [0, -1, 1.5, Number.NaN, 1e9]) expect(() => requirePageNumber(bad)).toThrow();
  });
});
