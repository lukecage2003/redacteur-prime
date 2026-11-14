"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireUuid } from "@/lib/ids";
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

export async function createMission(form: FormData): Promise<void> {
  const documentIds = form.getAll("document_ids").map((v) => requireUuid(String(v)));
  const type = field(form, "type");
  const response = await post("editorial/missions", {
    type,
    document_ids: documentIds,
    character: field(form, "character") || null,
    draft: field(form, "draft") || null,
  });
  const { mission_id } = (await response.json()) as { mission_id: string };
  redirect(`/editorial/${requireUuid(mission_id)}`);
}

export async function decide(rawMissionId: string, rawApprovalId: string, form: FormData): Promise<void> {
  const missionId = requireUuid(rawMissionId);
  await post("editorial/approvals", {
    approval_id: requireUuid(rawApprovalId),
    decision: field(form, "decision") === "approve" ? "approve" : "reject",
    comment: field(form, "comment") || null,
  });
  revalidatePath(`/editorial/${missionId}`);
}
