/** Client Editorial Director. */
import { apiUrl } from "./modules";

export interface AgentInfo {
  key: string;
  name: string;
  role: string;
  limits: string;
  phase: number;
  available: boolean;
}

export interface MissionSummary {
  id: string;
  type: string;
  title: string;
  status: string;
  recommendation: string | null;
  created_at: string;
}

export interface FactCheckEntry {
  sentence: string;
  status: string;
  detail: string;
}

export interface MissionDetail {
  id: string;
  type: string;
  title: string;
  status: string;
  error: string | null;
  tasks: { position: number; key: string; agent_name: string; critical: boolean; status: string; attempts: number; error: string | null }[];
  result: {
    recommendation: string;
    summary: string;
    findings: string[];
    deliverable: string | null;
    author: string;
    fact_check: { verdict: string; counts: Record<string, number>; checks: FactCheckEntry[] };
  } | null;
  approvals: { id: string; status: string; recommendation: string; decided_by: string | null; comment: string | null }[];
  agent_runs: { agent: string; provider: string; model: string | null; cost_usd: string; error: string | null }[];
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchAgents = (base?: string) => get<AgentInfo[]>("editorial/agents", base);
export const fetchMissions = (base?: string) => get<MissionSummary[]>("editorial/missions", base);
export const fetchMission = (id: string, base?: string) =>
  get<MissionDetail>(`editorial/missions/${encodeURIComponent(id)}`, base);

/** Gravité d'un statut de vérification, pour l'affichage. */
export function checkSeverity(status: string): "ok" | "review" | "error" | "neutral" {
  if (status === "VERIFIED") return "ok";
  if (["QUOTE_NOT_FOUND", "INVALID_CITATION", "CONFLICTS_WITH_EVIDENCE"].includes(status)) return "error";
  if (["PAGE_NOT_TRANSCRIBED", "PARAPHRASE", "NO_CITATION"].includes(status)) return "review";
  return "neutral";
}

export const MISSION_LABELS: Record<string, string> = {
  CHARACTER_DOSSIER: "Dossier de personnage",
  CONTINUITY_AUDIT: "Audit de continuité",
  FACT_CHECK: "Vérification d'un texte",
  THEORY_REVIEW: "Revue de théorie",
  RESEARCH_DOSSIER: "Dossier de recherche",
  MARKET_BRIEF: "Note de marché EN → FR",
};
