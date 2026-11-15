/** Client Identité indépendante (ADR-0029). */
import { apiUrl } from "./modules";

export interface VoiceProfile {
  id: string;
  name: string;
  language: "fr" | "en";
  tone: string;
  kind: "SYNTHETIC" | "HUMAN_LICENSED";
  provider: string;
  voice: string;
  license: string;
  allowed_use: string;
  status: "PROPOSED" | "APPROVED" | "RETIRED";
}

export interface VisualProfile {
  id: string;
  series_id: string | null;
  platform: string | null;
  language: "fr" | "en" | null;
  rules: Record<string, unknown>;
  version: number;
  status: "ACTIVE" | "RETIRED";
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchVoices = (base?: string) => get<VoiceProfile[]>("identity/voices", base);
export const fetchVisuals = (base?: string) => get<VisualProfile[]>("identity/visuals", base);

/** Voix utilisable pour une langue : approuvée et de cette langue uniquement. */
export const brandVoice = (voices: VoiceProfile[], language: "fr" | "en"): VoiceProfile | undefined =>
  voices.find((v) => v.status === "APPROVED" && v.language === language);
