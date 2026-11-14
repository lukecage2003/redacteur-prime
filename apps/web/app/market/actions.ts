"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireUuid } from "@/lib/ids";
import { splitKeywords } from "@/lib/market";
import { apiUrl } from "@/lib/modules";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const field = (form: FormData, name: string) => {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
};

async function post(path: string, body: unknown): Promise<Response> {
  // URLs fixes : toutes les valeurs venues du client voyagent dans le corps validé par l'API.
  const response = await fetch(apiUrl(path, serverApi()), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Refusé par l'API (HTTP ${response.status}) : ${await response.text()}`);
  return response;
}

export async function addTopic(form: FormData): Promise<void> {
  await post("market/topics", {
    name: field(form, "name"),
    keywords_fr: splitKeywords(field(form, "keywords_fr")),
    keywords_en: splitKeywords(field(form, "keywords_en")),
  });
  revalidatePath("/market");
}

export async function verifySource(key: string): Promise<void> {
  await post("market/sources/verifications", { key });
  revalidatePath("/market");
}

export async function launchBrief(): Promise<void> {
  const response = await post("editorial/missions", { type: "MARKET_BRIEF" });
  const { mission_id } = (await response.json()) as { mission_id: string };
  redirect(`/editorial/${requireUuid(mission_id)}`);
}
