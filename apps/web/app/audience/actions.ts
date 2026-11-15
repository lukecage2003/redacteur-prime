"use server";

import { revalidatePath } from "next/cache";
import { apiUrl } from "@/lib/modules";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const field = (form: FormData, name: string) => {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
};

export async function createSegment(form: FormData): Promise<void> {
  // URL fixe : les valeurs voyagent dans le corps validé par l'API.
  const response = await fetch(apiUrl("audience/segments", serverApi()), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: field(form, "name"),
      description: field(form, "description"),
      motivations: field(form, "motivations").split(",").map((m) => m.trim()).filter(Boolean),
      knowledge_level: field(form, "knowledge_level") || null,
    }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Refusé par l'API (HTTP ${response.status}) : ${await response.text()}`);
  revalidatePath("/audience");
}
