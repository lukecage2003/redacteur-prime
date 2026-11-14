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
const optionalInt = (form: FormData, name: string) => {
  const value = Number.parseInt(field(form, name), 10);
  return Number.isFinite(value) ? value : null;
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

export async function createTheory(form: FormData): Promise<void> {
  const response = await post("lab/theories", {
    title: field(form, "title"),
    claim: field(form, "claim"),
    document_ids: form.getAll("document_ids").map((v) => requireUuid(String(v))),
    subjects: field(form, "subjects")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  });
  const { theory_id } = (await response.json()) as { theory_id: string };
  redirect(`/lab/${requireUuid(theory_id)}`);
}

export async function addEvidence(rawTheoryId: string, form: FormData): Promise<void> {
  const theoryId = requireUuid(rawTheoryId);
  await post("lab/evidence", {
    theory_id: theoryId,
    role: field(form, "role") === "REFUTES" ? "REFUTES" : "SUPPORTS",
    document_id: requireUuid(field(form, "document_id")),
    page: optionalInt(form, "page"),
    panel: optionalInt(form, "panel"),
    excerpt: field(form, "excerpt") || null,
    level: field(form, "level") || "CANON",
    note: field(form, "note") || null,
  });
  revalidatePath(`/lab/${theoryId}`);
}

export async function retractEvidence(rawTheoryId: string, rawEvidenceId: string, form: FormData): Promise<void> {
  const theoryId = requireUuid(rawTheoryId);
  await post("lab/evidence/retractions", { evidence_id: requireUuid(rawEvidenceId), reason: field(form, "reason") });
  revalidatePath(`/lab/${theoryId}`);
}

export async function addAlternative(rawTheoryId: string, form: FormData): Promise<void> {
  const theoryId = requireUuid(rawTheoryId);
  await post("lab/alternatives", { theory_id: theoryId, text: field(form, "text") });
  revalidatePath(`/lab/${theoryId}`);
}

export async function research(rawTheoryId: string): Promise<void> {
  const theoryId = requireUuid(rawTheoryId);
  await post("lab/research", { theory_id: theoryId });
  revalidatePath(`/lab/${theoryId}`);
}

export async function review(rawTheoryId: string): Promise<void> {
  const response = await post("editorial/missions", { type: "THEORY_REVIEW", theory_id: requireUuid(rawTheoryId) });
  const { mission_id } = (await response.json()) as { mission_id: string };
  redirect(`/editorial/${requireUuid(mission_id)}`);
}
