import { describe, expect, it } from "vitest";
import { brandVoice, type VoiceProfile } from "./identity";

const voice = (name: string, language: "fr" | "en", status: VoiceProfile["status"]): VoiceProfile => ({
  id: name,
  name,
  language,
  tone: "posé",
  kind: "SYNTHETIC",
  provider: "piper",
  voice: "local",
  license: "licence",
  allowed_use: "narration",
  status,
});

describe("brandVoice", () => {
  it("ne retient qu'une voix approuvée de la même langue", () => {
    const voices = [voice("A", "fr", "PROPOSED"), voice("B", "fr", "APPROVED"), voice("C", "en", "RETIRED")];
    expect(brandVoice(voices, "fr")?.name).toBe("B");
    expect(brandVoice(voices, "en")).toBeUndefined();
  });
});
