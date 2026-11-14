"use server";

import { revalidatePath } from "next/cache";
import { apiUrl } from "@/lib/modules";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

/** Lance les extracteurs forensiques (règles déterministes, coût nul). */
export async function runForensic(documentId: string): Promise<void> {
  const response = await fetch(apiUrl("forensic/analyses", serverApi()), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ document_ids: [documentId] }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Analyse refusée (HTTP ${response.status})`);
  revalidatePath(`/library/${documentId}/forensic`);
}
