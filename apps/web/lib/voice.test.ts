import { describe, expect, it } from "vitest";
import { encodeWav, PERSONALITIES, toBase64, voiceSocketUrl } from "./voice";

describe("voiceSocketUrl", () => {
  it("passe en ws/wss", () => {
    expect(voiceSocketUrl("https://api.example.test/")).toBe("wss://api.example.test/api/v1/ws/voice");
    expect(voiceSocketUrl("", { protocol: "http:", host: "localhost:3000" })).toBe("ws://localhost:3000/api/v1/ws/voice");
  });
});

describe("encodeWav", () => {
  it("produit un WAV 16 kHz mono rééchantillonné", () => {
    const wav = encodeWav(new Float32Array(48_000).fill(0.5), 48_000);
    const text = new TextDecoder().decode(wav.slice(0, 4));
    expect(text).toBe("RIFF");
    const view = new DataView(wav.buffer);
    expect(view.getUint32(24, true)).toBe(16_000);
    expect(wav.length).toBe(44 + 16_000 * 2);
    expect(view.getInt16(44, true)).toBe(Math.floor(0.5 * 0x7fff));
    expect(toBase64(wav.slice(0, 4))).toBe("UklGRg==");
  });

  it("propose les cinq personnalités", () => {
    expect(PERSONALITIES.map((p) => p.key)).toHaveLength(5);
  });
});
