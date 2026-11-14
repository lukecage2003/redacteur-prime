/**
 * Carte des intelligences de la plateforme et de leur statut de livraison.
 * Les statuts suivent ROADMAP.md : une fonctionnalité n'est VALIDATED qu'après
 * validation sur cas réels, pas parce que le code existe.
 */

export type DeliveryStatus = "NOT_IMPLEMENTED" | "IMPLEMENTED" | "TESTED" | "VALIDATED" | "BLOCKED";

export interface IntelligenceModule {
  id: string;
  name: string;
  phase: number;
  summary: string;
  status: DeliveryStatus;
}

export const MODULES: readonly IntelligenceModule[] = [
  { id: "comic", name: "Comic Intelligence", phase: 2, summary: "Bibliothèque, import par lots, rendu des pages", status: "TESTED" },
  { id: "vision", name: "Comic Vision", phase: 3, summary: "OCR, cases, bulles, ordre de lecture", status: "TESTED" },
  { id: "forensic", name: "Forensic Intelligence", phase: 4, summary: "Observations prouvées, CANON / INTERPRÉTATION / THÉORIE / SPÉCULATION", status: "TESTED" },
  { id: "knowledge", name: "Knowledge Intelligence", phase: 5, summary: "Entités, relations, provenance, recherche hybride", status: "NOT_IMPLEMENTED" },
  { id: "editorial", name: "Editorial Intelligence", phase: 6, summary: "Chief Editor et agents spécialisés", status: "NOT_IMPLEMENTED" },
  { id: "market", name: "Market Intelligence", phase: 8, summary: "Tendances FR / EN, sujets sous-exploités en français", status: "NOT_IMPLEMENTED" },
  { id: "social", name: "Social Intelligence", phase: 9, summary: "Déclinaisons YouTube, TikTok, Instagram", status: "NOT_IMPLEMENTED" },
  { id: "storytelling", name: "Storytelling Intelligence", phase: 10, summary: "Scripts FR / EN, notation sur 100, veto factuel", status: "NOT_IMPLEMENTED" },
  { id: "performance", name: "Performance Intelligence", phase: 11, summary: "Boucle mesurer → apprendre → optimiser", status: "NOT_IMPLEMENTED" },
  { id: "voice", name: "Adaptive Voice Intelligence", phase: 12, summary: "Assistant vocal temps réel, 5 personnalités", status: "NOT_IMPLEMENTED" },
];

export const STATUS_LABELS: Record<DeliveryStatus, string> = {
  NOT_IMPLEMENTED: "Non implémenté",
  IMPLEMENTED: "Implémenté",
  TESTED: "Testé",
  VALIDATED: "Validé",
  BLOCKED: "Bloqué",
};

export function modulesByPhase(modules: readonly IntelligenceModule[] = MODULES): IntelligenceModule[] {
  return [...modules].sort((a, b) => a.phase - b.phase || a.name.localeCompare(b.name));
}

/** URL absolue d'un chemin de l'API versionnée, sans double barre oblique. */
export function apiUrl(path: string, base: string = process.env.NEXT_PUBLIC_API_BASE_URL ?? ""): string {
  const cleanBase = base.replace(/\/+$/, "");
  const cleanPath = path.replace(/^\/+/, "");
  return `${cleanBase}/api/v1/${cleanPath}`;
}
