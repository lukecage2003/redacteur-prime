/** Client Market Intelligence. */
import { apiUrl } from "./modules";

export interface MarketSource {
  id: string;
  key: string;
  name: string;
  kind: "YOUTUBE_API" | "RSS" | "MANUAL";
  access: string;
  quota: string;
  terms_url: string;
  data_class: string;
  language: string | null;
  verified_at: string | null;
  verified_by: string | null;
  items: number;
  last_collected: string | null;
}

export interface LanguageStats {
  items: number;
  items_with_views: number;
  median_views: number | null;
  sufficient: boolean;
  sources: { title: string; url: string | null; channel: string | null; views: number | null; observed_at: string | null; data_class: string }[];
}

export interface TopicResult {
  topic: string;
  topic_id: string;
  status: "SCORED" | "INSUFFICIENT_DATA";
  gap_score: number | null;
  demand_en: number | null;
  saturation_fr: number | null;
  cultural_difference: number | null;
  explanation: string[];
  languages: { fr: LanguageStats; en: LanguageStats };
}

export interface MarketAnalysis {
  method: string;
  data_class: string;
  window_days: number;
  min_items: number;
  caveat: string;
  items_considered: number;
  topics: TopicResult[];
  opportunities: string[];
  popular: string[];
  niches: string[];
  saturated_fr: string[];
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchSources = (base?: string) => get<MarketSource[]>("market/sources", base);
export const fetchAnalysis = (base?: string) => get<MarketAnalysis>("market/analysis", base);

/** Lecture d'un score d'écart pour l'affichage ; jamais de chiffre sans données. */
export function gapLabel(topic: Pick<TopicResult, "status" | "gap_score">): string {
  if (topic.status !== "SCORED" || topic.gap_score === null) return "données insuffisantes";
  if (topic.gap_score >= 0.5) return "écart fort";
  if (topic.gap_score > 0) return "écart modéré";
  return "saturé en français";
}

/** Mots-clés saisis « a, b , c » → ["a", "b", "c"]. */
export const splitKeywords = (raw: string) =>
  raw
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
