/** Client du laboratoire des théories. */
import { apiUrl } from "./modules";

export type TheoryStatus = "OPEN" | "SUPPORTED" | "CONTESTED" | "REFUTED";
export type TheoryLevel = "THEORY" | "SPECULATION";

export interface TheorySummary {
  id: string;
  title: string;
  claim: string;
  level: TheoryLevel;
  status: TheoryStatus;
  confidence: number;
  subjects: string[];
  supports: number;
  refutes: number;
  counter_search_at: string | null;
  updated_at: string;
}

export interface TheoryEvidence {
  id: string;
  role: "SUPPORTS" | "REFUTES";
  document_id: string;
  document_title: string;
  page_number: number;
  panel_index: number | null;
  excerpt: string | null;
  verified: boolean;
  still_found: boolean | null;
  level: string;
  note: string | null;
  origin: string;
  added_by: string;
  retracted_at: string | null;
  retraction_reason: string | null;
}

export interface TheoryDetail extends Omit<TheorySummary, "supports" | "refutes"> {
  author: string;
  document_ids: string[];
  documents: { id: string; title: string; page_count: number | null }[];
  evidence: TheoryEvidence[];
  alternatives: { id: string; text: string; author: string; created_at: string }[];
  events: { action: string; detail: Record<string, unknown>; author: string; reason: string | null; created_at: string }[];
  scoring: { method: string; support: number; against: number; explanation: string[] };
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchTheories = (base?: string) => get<TheorySummary[]>("lab/theories", base);
export const fetchTheory = (id: string, base?: string) => get<TheoryDetail>(`lab/theories/${encodeURIComponent(id)}`, base);

export const STATUS_LABELS: Record<TheoryStatus, string> = {
  OPEN: "à instruire",
  SUPPORTED: "soutenue",
  CONTESTED: "contestée",
  REFUTED: "réfutée",
};

/** État d'une preuve pour l'affichage : retirée, obsolète, vérifiée ou non vérifiable. */
export function evidenceState(e: Pick<TheoryEvidence, "retracted_at" | "excerpt" | "verified" | "still_found">): "retracted" | "stale" | "verified" | "visual" | "unverified" {
  if (e.retracted_at) return "retracted";
  if (e.excerpt && e.still_found === false) return "stale";
  if (!e.excerpt) return "visual";
  return e.verified ? "verified" : "unverified";
}

export const EVIDENCE_STATE_LABELS = {
  retracted: "retirée",
  stale: "extrait absent de la transcription actuelle",
  verified: "extrait vérifié",
  visual: "preuve visuelle (attestée par un humain)",
  unverified: "page non transcrite : invérifiable",
} as const;

export const percent = (confidence: number) => `${Math.round(confidence * 100)} %`;
