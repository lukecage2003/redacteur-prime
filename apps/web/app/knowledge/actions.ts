"use server";

import { revalidatePath } from "next/cache";
import { requireUuid } from "@/lib/ids";
import { apiUrl } from "@/lib/modules";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

async function post(path: string, body: unknown): Promise<void> {
  // URLs fixes : les valeurs venues du client ne voyagent que dans le corps validé par l'API.
  const response = await fetch(apiUrl(path, serverApi()), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Refusé par l'API (HTTP ${response.status}) : ${await response.text()}`);
}

/** Construit le graphe à partir de toute la bibliothèque (gratuit). */
export async function buildKnowledge(): Promise<void> {
  const response = await fetch(apiUrl("library/documents?limit=200", serverApi()), { cache: "no-store" });
  const documents = (await response.json()) as { id: string }[];
  if (documents.length > 0) {
    await post("forensic/analyses", { document_ids: documents.map((d) => d.id) });
    await post("knowledge/build", { document_ids: documents.map((d) => d.id) });
  }
  revalidatePath("/knowledge");
}

const text = (form: FormData, name: string) => {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
};

export async function correctEntity(rawEntityId: string, form: FormData): Promise<void> {
  const entityId = requireUuid(rawEntityId);
  const action = text(form, "action");
  const body: Record<string, unknown> = { action, entity_id: entityId, reason: text(form, "reason") };
  if (action === "merge") body.other_entity_id = requireUuid(text(form, "other_entity_id"));
  else if (action === "rename" || action === "add_alias") {
    body.value = text(form, "value");
    body.language = text(form, "language") || null;
  } else throw new Error("action inconnue");
  await post("knowledge/corrections", body);
  revalidatePath(`/knowledge/${entityId}`);
}

export async function retractRelation(rawEntityId: string, rawRelationId: string, form: FormData): Promise<void> {
  const entityId = requireUuid(rawEntityId);
  await post("knowledge/corrections", {
    action: "retract_relation",
    relation_id: requireUuid(rawRelationId),
    reason: text(form, "reason") || "retrait manuel",
  });
  revalidatePath(`/knowledge/${entityId}`);
}
