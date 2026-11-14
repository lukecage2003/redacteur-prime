"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { apiUrl } from "@/lib/modules";
import { parseTranscriptionForm } from "@/lib/transcription";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

/** Enregistre la transcription humaine (gratuite) puis recharge la page. */
export async function saveTranscription(documentId: string, page: number, form: FormData): Promise<void> {
  const texts = parseTranscriptionForm(form);
  const response = await fetch(
    apiUrl(`library/documents/${encodeURIComponent(documentId)}/pages/${page}/transcription`, serverApi()),
    {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ texts, author: "propriétaire" }),
      cache: "no-store",
    },
  );
  if (!response.ok) throw new Error(`Enregistrement refusé (HTTP ${response.status})`);
  revalidatePath(`/library/${documentId}/pages/${page}`);
  redirect(`/library/${documentId}/pages/${page}?saved=1`);
}
