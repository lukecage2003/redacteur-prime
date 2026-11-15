/** Client Creative Intelligence. */
import { apiUrl } from "./modules";

export interface Charter {
  version: number;
  name: string;
  rules: { status?: string; colors: { name: string; hex: string; usage: string }[]; tone: { do: string[]; dont: string[] }; thumbnail: { max_words: number } };
}

export interface Series {
  id: string;
  name: string;
  promise: string;
  identity: string;
  tone: string;
  target_minutes: number;
  status: string;
  segment: string | null;
  episodes: { number: number; title: string; script_id: string; score: number | null }[];
  average_score: number | null;
  consistency: string[];
}

export interface Packaging {
  titles: { title: string; honest: boolean; issues: string[]; readability: string[]; audience_fit: string[] }[];
  thumbnails: { concept: string; composition: string; brand_issues: string[] }[];
  promises: string[];
  hooks: string[];
  tests: { variable: string; hypothesis: string }[];
  rule: string;
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchCharter = (base?: string) => get<Charter>("creative/charter", base);
export const fetchSeries = (base?: string) => get<Series[]>("creative/series", base);
export const fetchPackagings = (scriptId: string, base?: string) =>
  get<{ content: Packaging; charter_version: number }[]>(`creative/packaging/${encodeURIComponent(scriptId)}`, base);

/** Titres utilisables : honnêtes ET lisibles ; les autres restent visibles avec leur motif. */
export const usableTitles = (p: Pick<Packaging, "titles">) => p.titles.filter((t) => t.honest && t.readability[0] === "lisible");
