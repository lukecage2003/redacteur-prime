"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requirePageNumber, requireUuid } from "@/lib/ids";
import { apiUrl } from "@/lib/modules";
import { parseTranscriptionForm } from "@/lib/transcription";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

/** Enregistre la transcription humaine (gratuite) puis recharge la page. */
export async function saveTranscription(rawDocumentId: string, rawPage: number, form: FormData): Promise<void> {
  // Les arguments d'une action serveur viennent du client : validation stricte avant l'appel.
  const documentId = requireUuid(rawDocumentId);
  const page = requirePageNumber(rawPage);
  const texts = parseTranscriptionForm(form);
  const response = await fetch(
    apiUrl(`library/documents/${documentId}/pages/${page}/transcription`, serverApi()),
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
