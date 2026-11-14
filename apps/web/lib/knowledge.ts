/** Client de lecture Knowledge (entités, relations, recherche). */
import { apiUrl } from "./modules";

export interface EntitySummary {
  id: string;
  type: string;
  canonical_name: string;
  relations: number;
}

export interface RelationView {
  id: string;
  type: string;
  qualifier: string | null;
  level: string;
  confidence: number;
  origin: "EXTRACTOR" | "HUMAN";
  retracted: boolean;
  source: { id: string; name: string };
  target: { id: string; name: string };
  evidence: { document_id: string; page: number; panel: number | null; excerpt: string | null }[];
}

export interface EntityDetail {
  id: string;
  type: string;
  canonical_name: string;
  description: string | null;
  aliases: { alias: string; language: string | null; origin: string }[];
  relations: RelationView[];
  history: { action: string; author: string; reason: string; created_at: string }[];
  merged_into?: string;
}

export interface SearchHit {
  kind: "TEXT" | "ENTITY";
  ref_id: string;
  document_id: string | null;
  page: number | null;
  panel: number | null;
  content: string;
  score: number;
  fulltext_rank: number | null;
  vector_similarity: number | null;
}

async function get<T>(path: string, base?: string, fetcher: typeof fetch = fetch): Promise<T | null> {
  try {
    const response = await fetcher(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchEntities = (query: string | undefined, base?: string, fetcher?: typeof fetch) =>
  get<EntitySummary[]>(`knowledge/entities${query ? `?q=${encodeURIComponent(query)}` : ""}`, base, fetcher);

export const fetchEntity = (id: string, base?: string, fetcher?: typeof fetch) =>
  get<EntityDetail>(`knowledge/entities/${encodeURIComponent(id)}`, base, fetcher);

export const searchLibrary = (query: string, base?: string, fetcher?: typeof fetch) =>
  get<SearchHit[]>(`search?q=${encodeURIComponent(query)}`, base, fetcher);

/** Phrase lisible d'une relation vue depuis une entité : « → Nuit noire #1 (apparaît dans) ». */
export const RELATION_LABELS: Record<string, string> = {
  APPEARS_IN: "apparaît dans",
  REFERENCES: "cite",
  CONTRADICTS: "contredit",
  PRECEDES: "précède",
  REVEALS: "révèle",
  FORESHADOWS: "annonce",
  RELATED_TO: "lié à",
  OPPOSES: "s'oppose à",
};

export function describeRelation(relation: RelationView, viewpointId: string): string {
  const outgoing = relation.source.id === viewpointId;
  const other = outgoing ? relation.target.name : relation.source.name;
  const label = relation.qualifier ?? RELATION_LABELS[relation.type] ?? relation.type;
  return outgoing ? `${label} → ${other}` : `${other} → ${label} (cette entité)`;
}
