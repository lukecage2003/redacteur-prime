/** Client Maximum Storytelling. */
import { apiUrl } from "./modules";

export interface ScriptSummary {
  id: string;
  title: string;
  language: "fr" | "en";
  step: string;
  status: string;
  versions: number | null;
  last_total: number | null;
}

export interface Criterion {
  score: number;
  max: number;
  notes: string[];
}

export interface ScriptDetail extends Omit<ScriptSummary, "versions"> {
  steps: string[];
  pass_mark: number;
  adapted_from: string | null;
  adaptations: string[];
  versions: { id: string; number: number; step: string; origin: string; author: string; created_at: string; content: string }[];
  level: string | null;
  scores: {
    version: number;
    total: number;
    factual_veto: boolean;
    criteria: Record<string, Criterion>;
    analysis: {
      words: number;
      estimated_minutes: number;
      works: { title: string; year: number; status: string }[];
      level_checks?: { level: string; ok: boolean; checks: { check: string; ok: boolean; detail: string }[] };
      retention?: { sections: { title: string; flags: string[]; visual_moments: string[] }[]; drop_offs: { at_ratio: number; section: string | null }[] };
    };
  }[];
  events: { action: string; author: string; reason: string | null; created_at: string }[];
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchScripts = (base?: string) => get<ScriptSummary[]>("scripts", base);
export const fetchScript = (id: string, base?: string) => get<ScriptDetail>(`scripts/${encodeURIComponent(id)}`, base);

export const CRITERIA_LABELS: Record<string, string> = {
  hook: "Accroche",
  architecture: "Architecture",
  retention: "Rétention",
  writing: "Écriture",
  originality: "Originalité",
  orality: "Oralité",
  accuracy: "Exactitude",
  conclusion: "Conclusion",
};

/** Verdict affiché : le veto factuel l'emporte toujours sur la note. */
export function verdict(score: { total: number; factual_veto: boolean }, passMark: number): string {
  if (score.factual_veto) return "veto factuel : non validable";
  return score.total >= passMark ? "validable après relecture humaine" : "à retravailler";
}
