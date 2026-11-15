/** Client Audience Intelligence. */
import { apiUrl } from "./modules";

export interface Segment {
  id: string;
  name: string;
  description: string;
  motivations: string[];
  knowledge_level: string | null;
  status: "HYPOTHESIS" | "CONFIRMED";
  evidence: { id: string; kind: string; statement: string; data_class: string }[];
  links: { target_kind: string; relation: string; label: string }[];
}

export interface Community {
  comments: number;
  by_kind: Record<string, number>;
  recurring: { kind: string; subject: string; count: number; examples: string[] }[];
  proposals: string[];
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

export const fetchSegments = (base?: string) => get<Segment[]>("audience/segments", base);
export const fetchCommunity = (base?: string) => get<Community>("audience/community", base);

/** Natures de preuve OBSERVÉES distinctes : un segment n'est confirmé qu'à partir de deux. */
export function observedKinds(segment: Pick<Segment, "evidence">): string[] {
  return [...new Set(segment.evidence.map((e) => e.kind).filter((k) => k !== "DECLARED"))].sort();
}
