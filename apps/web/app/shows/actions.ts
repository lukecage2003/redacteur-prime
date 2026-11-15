"use server";

import { revalidatePath } from "next/cache";
import { requireUuid } from "@/lib/ids";
import { apiUrl } from "@/lib/modules";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const STATUSES = ["TESTING", "ACTIVE", "SUSPENDED", "RETIRED"];

export async function proposeTransition(rawSeriesId: string, form: FormData): Promise<void> {
  const seriesId = requireUuid(rawSeriesId);
  const to = String(form.get("to") ?? "");
  if (!STATUSES.includes(to)) throw new Error("statut invalide");
  const reason = String(form.get("reason") ?? "").trim() || null;
  // URL fixe : l'identifiant voyage dans le corps validé par l'API.
  const response = await fetch(apiUrl("shows/transitions", serverApi()), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ series_id: seriesId, to, reason }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Refusé par l'API (HTTP ${response.status}) : ${await response.text()}`);
  revalidatePath(`/shows/${seriesId}`);
}
