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

export async function createScript(form: FormData): Promise<void> {
  const response = await post("scripts", {
    title: field(form, "title"),
    language: field(form, "language") === "en" ? "en" : "fr",
    content: field(form, "content"),
    document_ids: form.getAll("document_ids").map((v) => requireUuid(String(v))),
  });
  const { script_id } = (await response.json()) as { script_id: string };
  redirect(`/scripts/${requireUuid(script_id)}`);
}

export async function addVersion(rawId: string, form: FormData): Promise<void> {
  const id = requireUuid(rawId);
  await post("scripts/versions", { script_id: id, content: field(form, "content") });
  revalidatePath(`/scripts/${id}`);
}

export async function moveStep(rawId: string, form: FormData): Promise<void> {
  const id = requireUuid(rawId);
  await post("scripts/steps", { script_id: id, step: field(form, "step"), reason: field(form, "reason") || null });
  revalidatePath(`/scripts/${id}`);
}

export async function evaluate(rawId: string): Promise<void> {
  const id = requireUuid(rawId);
  await post("scripts/evaluations", { script_id: id });
  revalidatePath(`/scripts/${id}`);
}

export async function validate(rawId: string): Promise<void> {
  const id = requireUuid(rawId);
  await post("scripts/validations", { script_id: id });
  revalidatePath(`/scripts/${id}`);
}

export async function packageScript(rawId: string): Promise<void> {
  const id = requireUuid(rawId);
  await post("creative/packaging", { script_id: id });
  revalidatePath(`/scripts/${id}`);
}
