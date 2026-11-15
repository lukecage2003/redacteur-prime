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
  { id: "knowledge", name: "Knowledge Intelligence", phase: 5, summary: "Entités, relations, provenance, recherche hybride", status: "TESTED" },
  { id: "editorial", name: "Editorial Intelligence", phase: 6, summary: "Chief Editor et agents spécialisés", status: "TESTED" },
  { id: "lab", name: "Research et Theory Laboratory", phase: 7, summary: "Théories avec preuves, contre-preuves, alternatives et confiance calculée", status: "TESTED" },
  { id: "market", name: "Market Intelligence", phase: 8, summary: "Écarts EN → FR sur données publiques, niches, saturation (estimations)", status: "TESTED" },
  { id: "social", name: "Social Intelligence", phase: 9, summary: "Déclinaisons YouTube, TikTok, Instagram depuis les faits vérifiés", status: "TESTED" },
  { id: "storytelling", name: "Storytelling Intelligence", phase: 10, summary: "Scripts FR / EN en 13 étapes, pré-notation sur 100, veto factuel", status: "TESTED" },
  { id: "performance", name: "Performance Intelligence", phase: 11, summary: "Chaîne Primestone : repères et signaux script → rétention / CTR", status: "TESTED" },
  { id: "audience", name: "Audience Intelligence", phase: 15, summary: "Segments prouvés, graphe d'audience, communauté sans données personnelles", status: "TESTED" },
  { id: "creative", name: "Creative Intelligence", phase: 18, summary: "Packaging honnête, charte de marque versionnée, séries et franchises", status: "TESTED" },
  { id: "governance", name: "Brand Intelligence et gouvernance", phase: 20, summary: "Marque PRIMESTONE, piliers, politiques, décisions approuvées par le fondateur, réversibles", status: "TESTED" },
  { id: "voice", name: "Adaptive Voice Intelligence", phase: 12, summary: "Assistant vocal temps réel, 5 personnalités", status: "TESTED" },
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
