/** Client de lecture de la Comic Library (API /api/v1/library). */
import { apiUrl } from "./modules";

export type DocumentStatus = "UPLOADED" | "VALIDATED" | "COMPLETE" | "INCOMPLETE" | "REJECTED" | "FAILED";

export interface LibraryDocument {
  id: string;
  comic_id: string;
  title: string;
  original_filename: string;
  format: "PDF" | "CBZ" | null;
  status: DocumentStatus;
  page_count: number | null;
  expected_page_count: number | null;
  pages_rendered: number;
  error: string | null;
}

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  UPLOADED: "Téléversé",
  VALIDATED: "En cours de rendu",
  COMPLETE: "Complet",
  INCOMPLETE: "Pages manquantes",
  REJECTED: "Rejeté",
  FAILED: "Échec",
};

/** Progression du rendu en pourcentage entier (0 si le nombre de pages est inconnu). */
export function renderProgress(doc: Pick<LibraryDocument, "page_count" | "pages_rendered">): number {
  if (!doc.page_count) return 0;
  return Math.min(100, Math.floor((doc.pages_rendered / doc.page_count) * 100));
}

export type LibraryResult = { ok: true; documents: LibraryDocument[] } | { ok: false; error: string };

export async function fetchDocuments(
  fetcher: typeof fetch = fetch,
  base?: string,
): Promise<LibraryResult> {
  try {
    const response = await fetcher(apiUrl("library/documents?limit=200", base), { cache: "no-store" });
    if (!response.ok) return { ok: false, error: `API indisponible (HTTP ${response.status})` };
    return { ok: true, documents: (await response.json()) as LibraryDocument[] };
  } catch {
    return { ok: false, error: "API injoignable" };
  }
}

export interface PageSummary {
  number: number;
  status: "PENDING" | "RENDERED" | "FAILED";
  width: number | null;
  height: number | null;
  error: string | null;
}

export interface DocumentDetail extends LibraryDocument {
  pages: PageSummary[];
}

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PageAnalysis {
  analysis_id: string;
  detector: string;
  provider: string;
  model: string;
  prompt_version: string;
  reading_direction: "LTR" | "RTL";
  cost_usd: string;
  panels: { index: number; bbox: Box }[];
  texts: {
    order: number;
    panel_index: number | null;
    kind: "DIALOGUE" | "THOUGHT" | "NARRATION" | "SFX" | "CAPTION" | "OTHER";
    text: string;
    language: string | null;
    confidence: number;
    speaker: string | null;
    speaker_confidence: number | null;
    bbox: Box;
  }[];
}

/** Position CSS (en %) d'une boîte normalisée, pour la superposer à l'image de la page. */
export function boxStyle(box: Box): { left: string; top: string; width: string; height: string } {
  const pct = (v: number) => `${(Math.min(1, Math.max(0, v)) * 100).toFixed(2)}%`;
  return { left: pct(box.x), top: pct(box.y), width: pct(box.width), height: pct(box.height) };
}

async function getJson<T>(path: string, fetcher: typeof fetch, base?: string): Promise<T | null> {
  try {
    const response = await fetcher(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchDocument = (id: string, fetcher: typeof fetch = fetch, base?: string) =>
  getJson<DocumentDetail>(`library/documents/${encodeURIComponent(id)}`, fetcher, base);

export const fetchAnalysis = (id: string, page: number, fetcher: typeof fetch = fetch, base?: string) =>
  getJson<PageAnalysis>(`library/documents/${encodeURIComponent(id)}/pages/${page}/analysis`, fetcher, base);

export const pageImageUrl = (id: string, page: number, base?: string) =>
  apiUrl(`library/documents/${encodeURIComponent(id)}/pages/${page}/image`, base);

export interface ForensicEvidence {
  document_id: string;
  page: number;
  panel: number | null;
  excerpt: string | null;
  role: "SUPPORTS" | "REFUTES";
}

export interface ForensicObservation {
  id: string;
  kind: string;
  level: "CANON" | "INTERPRETATION" | "THEORY" | "SPECULATION";
  subject: string | null;
  predicate: string | null;
  value: string | null;
  statement: string;
  confidence: number;
  evidence: ForensicEvidence[];
}

export interface ForensicReport {
  status: "COMPLETE" | "INCOMPLETE";
  extractor: string;
  documents: Record<
    string,
    { title: string; expected_pages: number; analyzed_pages: number; missing_pages: number[]; complete: boolean }
  >;
  observations_by_kind: Record<string, Record<string, number>>;
  characters: Record<
    string,
    { speeches: number; mentions: number; first_appearances: (ForensicEvidence & { level: string })[] }
  >;
  contradiction_candidates: ForensicObservation[];
  alias_candidates: ForensicObservation[];
  claims: ForensicObservation[];
}

export const fetchForensicReport = (ids: string[], fetcher: typeof fetch = fetch, base?: string) =>
  getJson<ForensicReport>(
    `forensic/report?${ids.map((id) => `document_ids=${encodeURIComponent(id)}`).join("&")}`,
    fetcher,
    base,
  );

/** Résume une liste de pages manquantes : [1,2,3,7] → "1–3, 7". */
export function formatPageRanges(pages: number[]): string {
  const sorted = [...new Set(pages)].sort((a, b) => a - b);
  const parts: string[] = [];
  for (let i = 0; i < sorted.length; i++) {
    const start = sorted[i]!;
    let end = start;
    while (i + 1 < sorted.length && sorted[i + 1] === end + 1) end = sorted[++i]!;
    parts.push(start === end ? `${start}` : `${start}–${end}`);
  }
  return parts.join(", ");
}

export const fetchPanels = (id: string, page: number, fetcher: typeof fetch = fetch, base?: string) =>
  getJson<{ index: number; bbox: Box }[]>(
    `library/documents/${encodeURIComponent(id)}/pages/${page}/panels`,
    fetcher,
    base,
  );
