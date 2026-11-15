/** Client gouvernance éditoriale (ADR-0027). */
import { apiUrl } from "./modules";

export interface Decision {
  id: string;
  action: string;
  subject_type: string;
  subject_id: string | null;
  proposal: Record<string, unknown>;
  status: "PROPOSED" | "APPROVED" | "REJECTED" | "SUPERSEDED" | "REVERTED";
  proposed_by: string;
  decided_by: string | null;
  decided_at: string | null;
  reason: string | null;
  created_at: string;
}

export interface Policy {
  action: string;
  requires_approval: boolean;
  approver: string;
  note: string | null;
  version: number;
}

export interface Pillar {
  id: string;
  name: string;
  description: string;
  status: "PROPOSED" | "ACTIVE" | "RETIRED";
  version: number;
}

export interface Brand {
  id: string;
  slug: string;
  name: string;
  mission: string;
  languages: string[];
  primary_language: string;
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchBrands = (base?: string) => get<Brand[]>("governance/brands", base);
export const fetchPolicies = (base?: string) => get<Policy[]>("governance/policies", base);
export const fetchPillars = (base?: string) => get<Pillar[]>("governance/pillars", base);
export const fetchDecisions = (base?: string) => get<Decision[]>("governance/decisions", base);

/** Décisions possibles pour le fondateur selon le statut (jamais pour un agent). */
export function allowedDecisions(status: Decision["status"]): ("approve" | "reject" | "revert")[] {
  if (status === "PROPOSED") return ["approve", "reject"];
  if (status === "APPROVED") return ["revert"];
  return [];
}
