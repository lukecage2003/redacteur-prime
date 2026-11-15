/** Client Droits, mémoire éditoriale et coûts (ADR-0031). */
import { apiUrl } from "./modules";

export interface Lesson {
  id: string;
  lesson: string;
  evidence_level: "OBSERVED" | "DEMONSTRATED";
  status: "ACTIVE" | "RETRACTED";
  show: string | null;
  recorded_by: string;
}

export interface RightsRecord {
  id: string;
  kind: string;
  subject: string;
  basis: string;
  limits: string;
  status: string;
  expired: boolean;
  document_title: string | null;
  page_number: number | null;
  panel_number: number | null;
}

export interface Costs {
  zero_cost_mode: boolean;
  total_usd: number;
  by_show: { series_id: string; name: string; missions: number; cost_usd: string }[];
  by_mission: { mission_id: string; type: string; title: string; runs: number; cost_usd: string }[];
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchLessons = (base?: string) => get<Lesson[]>("memory/lessons", base);
export const fetchRights = (base?: string) => get<RightsRecord[]>("memory/rights", base);
export const fetchCosts = (base?: string) => get<Costs>("memory/costs", base);

/** Un droit ne couvre une production que s'il est actif et non échu. */
export const rightsUsable = (r: Pick<RightsRecord, "status" | "expired">): boolean => r.status === "ACTIVE" && !r.expired;
