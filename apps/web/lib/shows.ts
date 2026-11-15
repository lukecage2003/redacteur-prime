/** Client du moteur d'émissions (ADR-0028). */
import { apiUrl } from "./modules";

export type ShowStatus = "DRAFT" | "TESTING" | "ACTIVE" | "SUSPENDED" | "RETIRED";

export interface ShowFormat {
  id: string;
  name: string;
  platform: string;
  language: "fr" | "en";
  min_minutes: string;
  max_minutes: string;
  structure: string[];
  status: string;
  version: number;
}

export interface ShowEpisode {
  id: string;
  number: number;
  status: "PROPOSED" | "IN_PRODUCTION" | "APPROVED" | "PUBLISHED";
  language: string | null;
  title: string;
  script_status: string;
  guideline_version: number | null;
  conformance: string[];
}

export interface Show {
  id: string;
  name: string;
  promise: string;
  tone: string;
  status: ShowStatus;
  languages: string[];
  expertise_level: string | null;
  pillar: string | null;
  guideline_version: number;
  evidence_requirements: Record<string, unknown>;
  formats: ShowFormat[];
  episodes: ShowEpisode[];
  pending: { id: string; action: string; proposal: Record<string, unknown> }[];
}

export interface ShowPerformance {
  contents: number;
  status?: string;
  total?: Record<string, number>;
  by_language?: Record<string, Record<string, number>>;
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchShow = (id: string, base?: string) => get<Show>(`shows/${encodeURIComponent(id)}`, base);
export const fetchShowPerformance = (id: string, base?: string) =>
  get<ShowPerformance>(`shows/${encodeURIComponent(id)}/performance`, base);

const NEXT: Record<ShowStatus, ShowStatus[]> = {
  DRAFT: ["TESTING", "RETIRED"],
  TESTING: ["ACTIVE", "RETIRED"],
  ACTIVE: ["SUSPENDED", "RETIRED"],
  SUSPENDED: ["ACTIVE", "RETIRED"],
  RETIRED: [],
};

/** Transitions proposables (chacune devient une décision du fondateur). */
export const nextStatuses = (status: ShowStatus): ShowStatus[] => NEXT[status];

/** Une émission n'accepte de nouveaux épisodes qu'en test ou active. */
export const acceptsEpisodes = (status: ShowStatus): boolean => status === "TESTING" || status === "ACTIVE";
