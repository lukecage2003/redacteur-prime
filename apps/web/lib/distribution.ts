/** Client Distribution et portefeuille (ADR-0030). */
import { apiUrl } from "./modules";

export interface PlanItem {
  id: string;
  title: string;
  status: "PROPOSED" | "APPROVED" | "PUBLISHED" | "CANCELLED";
  scheduled_for: string | null;
  published_url: string | null;
  declared_by: string | null;
  platform: string;
  channel: string;
  language: "fr" | "en";
  show: string | null;
}

export interface ChannelPerformance {
  channel_id: string;
  name: string;
  platform: string;
  language: string;
  stats_authorization: string;
  performance: Record<string, number | string>;
}

async function get<T>(path: string, base?: string): Promise<T | null> {
  try {
    const response = await fetch(apiUrl(path, base), { cache: "no-store" });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

export const fetchPlan = (base?: string) => get<PlanItem[]>("distribution/plan", base);
export const fetchChannelPerformance = (base?: string) => get<ChannelPerformance[]>("distribution/channels/performance", base);

/** Un élément ne se déclare publié qu'après approbation du fondateur. */
export const canDeclare = (item: Pick<PlanItem, "status">): boolean => item.status === "APPROVED";
