"use server";

import { revalidatePath } from "next/cache";
import { requireUuid } from "@/lib/ids";
import { apiUrl } from "@/lib/modules";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const MAX_BYTES = 5_000_000;

async function post(path: string, body: unknown): Promise<void> {
  // URLs fixes : toutes les valeurs venues du client voyagent dans le corps validé par l'API.
  const response = await fetch(apiUrl(path, serverApi()), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Refusé par l'API (HTTP ${response.status}) : ${await response.text()}`);
}

export async function importStudio(form: FormData): Promise<void> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) throw new Error("Fichier CSV requis");
  if (file.size > MAX_BYTES) throw new Error("Fichier trop volumineux (5 Mo maximum)");
  await post("performance/imports", { csv: await file.text() });
  revalidatePath("/performance");
}

export async function setObjective(rawContentId: string, form: FormData): Promise<void> {
  const objective = String(form.get("objective") ?? "");
  await post("performance/objectives", { content_id: requireUuid(rawContentId), objective: objective || null });
  revalidatePath("/performance");
}

export async function linkScript(rawContentId: string, form: FormData): Promise<void> {
  const scriptId = String(form.get("script_id") ?? "").trim();
  await post("performance/links", { content_id: requireUuid(rawContentId), script_id: requireUuid(scriptId) });
  revalidatePath("/performance");
}
