"use server";

import { revalidatePath } from "next/cache";
import { requireUuid } from "@/lib/ids";
import { apiUrl } from "@/lib/modules";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

export async function decide(rawDecisionId: string, form: FormData): Promise<void> {
  const decision = String(form.get("decision") ?? "");
  if (!["approve", "reject", "revert"].includes(decision)) throw new Error("décision invalide");
  const reason = String(form.get("reason") ?? "").trim();
  // URL fixe : l'identifiant voyage dans le corps validé par l'API.
  const response = await fetch(apiUrl("governance/decide", serverApi()), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ decision_id: requireUuid(rawDecisionId), decision, reason }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Refusé par l'API (HTTP ${response.status}) : ${await response.text()}`);
  revalidatePath("/governance");
}
