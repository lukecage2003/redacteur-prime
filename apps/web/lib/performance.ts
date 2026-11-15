/** Client Performance Intelligence (chaîne Primestone uniquement). */
import { apiUrl } from "./modules";

export interface ContentPerf {
  id: string;
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
};

/** Lecture d'une corrélation de rang : jamais présentée comme une cause. */
export function signalStrength(rho: number): "fort" | "modéré" | "faible" {
  const a = Math.abs(rho);
  return a >= 0.7 ? "fort" : a >= 0.5 ? "modéré" : "faible";
}
