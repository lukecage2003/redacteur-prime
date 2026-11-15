/** Assistant vocal : protocole WebSocket et encodage WAV (micro du navigateur). */

export const PERSONALITIES = [
  { key: "conversation", label: "Conversation" },
  { key: "research", label: "Recherche" },
  { key: "editorial", label: "Éditorial" },
  { key: "director", label: "Directeur" },
  { key: "brainstorming", label: "Brainstorming" },
] as const;

/** URL WebSocket de l'API (http → ws, https → wss). */
export function voiceSocketUrl(base: string, location?: { protocol: string; host: string }): string {
  const root = base.replace(/\/+$/, "") || (location ? `${location.protocol}//${location.host}` : "");
  return `${root.replace(/^http/, "ws")}/api/v1/ws/voice`;
}

/** Échantillons flottants [-1, 1] → WAV PCM 16 bits mono, rééchantillonné à `targetRate`. */
export function encodeWav(samples: Float32Array, sourceRate: number, targetRate = 16_000): Uint8Array {
  const ratio = sourceRate / targetRate;
  const length = Math.floor(samples.length / ratio);
  const buffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(buffer);
  const write = (offset: number, text: string) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  write(0, "RIFF");
  view.setUint32(4, 36 + length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, targetRate, true);
  view.setUint32(28, targetRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, length * 2, true);
  for (let i = 0; i < length; i++) {
    const s = Math.max(-1, Math.min(1, samples[Math.floor(i * ratio)] ?? 0));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Uint8Array(buffer);
}

export function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}
