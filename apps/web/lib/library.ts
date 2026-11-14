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
