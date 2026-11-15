import { describe, expect, it } from "vitest";
import { SECURITY_HEADERS } from "../next.config";

describe("en-têtes de sécurité", () => {
  it("interdit l'intégration en iframe et le reniflage de type", () => {
    const map = Object.fromEntries(SECURITY_HEADERS.map((h) => [h.key, h.value]));
    expect(map["X-Frame-Options"]).toBe("DENY");
    expect(map["X-Content-Type-Options"]).toBe("nosniff");
    expect(map["Permissions-Policy"]).toContain("microphone=(self)");
  });
});
