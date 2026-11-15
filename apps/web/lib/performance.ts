/** Client Performance Intelligence (chaîne Primestone uniquement). */
import { apiUrl } from "./modules";

export interface ContentPerf {
  id: string;
  objective: string | null;
  format: string | null;
  title: string;
  external_id: string;
  script_id: string | null;
  script_title: string | null;
  script_total: number | null;
  metrics: Record<string, number>;
}

export interface PerfReport {
  method: string;
  status: "OK" | "INSUFFICIENT_DATA";
  contents: number;
  linked_to_scored_script: number;
  min_items: number;
  benchmarks: Record<string, number>;
  signals: { criterion: string; target: string; rho: number; n: number }[];
  recommendations: string[];
  caveat: string;
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export interface Experiment {
  id: string;
  title: string;
  hypothesis: string;
  variable: string;
  metric: string;
  status: "PLANNED" | "RUNNING" | "CONCLUDED" | "INCONCLUSIVE";
  result: { winner: string | null; reason: string; p_value?: number } | null;
  conclusion: string | null;
  next_experiment: string | null;
}

export const OBJECTIVE_LABELS: Record<string, string> = {
  DISCOVERY: "Découverte",
  EXPLORATION: "Exploration",
  EXPERTISE: "Expertise",
  COMMUNITY: "Communauté",
};

/** Verdict d'une expérience : jamais de gagnant sans conclusion statistique. */
export function experimentVerdict(e: Pick<Experiment, "status" | "result">): string {
  if (e.status === "CONCLUDED" && e.result?.winner) return `variante ${e.result.winner} (démontré dans ce contexte)`;
  if (e.status === "INCONCLUSIVE") return `non concluant : ${e.result?.reason ?? "données insuffisantes"}`;
  return "en cours";
}

export const fetchExperiments = (base?: string) => get<Experiment[]>("performance/experiments", base);
export const fetchContents = (base?: string) => get<ContentPerf[]>("performance/contents", base);
export const fetchReport = (base?: string) => get<PerfReport>("performance/report", base);

export const METRIC_LABELS: Record<string, string> = {
  views: "Vues",
  impressions: "Impressions",
  ctr: "CTR (%)",
  avg_view_duration_s: "Durée moy. (s)",
  avg_view_percentage: "Rétention (%)",
  watch_time_min: "Visionnage (min)",
  likes: "J'aime",
  comments: "Commentaires",
  subscribers_gained: "Abonnés gagnés",
  subscribers_lost: "Abonnés perdus",
  shares: "Partages",
  saves: "Enregistrements",
  returning_viewers: "Spectateurs connus",
  new_viewers: "Nouveaux spectateurs",
  unique_viewers: "Spectateurs uniques",
  engaged_views: "Vues engagées",
};

/** Lecture d'une corrélation de rang : jamais présentée comme une cause. */
export function signalStrength(rho: number): "fort" | "modéré" | "faible" {
  const a = Math.abs(rho);
  return a >= 0.7 ? "fort" : a >= 0.5 ? "modéré" : "faible";
}
