import Link from "next/link";
import { DOCUMENT_STATUS_LABELS, fetchDocuments, renderProgress } from "@/lib/library";

export const dynamic = "force-dynamic";

export default async function LibraryPage() {
  const result = await fetchDocuments(fetch, process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Bibliothèque</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Import : <code className="text-xs">primestone-library import DOSSIER --process</code> ou{" "}
        <code className="text-xs">POST /api/v1/library/imports</code>.
      </p>

      {!result.ok ? (
        <p className="mt-6 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {result.error}
        </p>
      ) : result.documents.length === 0 ? (
        <p className="mt-6 text-zinc-500">Aucun comic importé.</p>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-zinc-200 text-xs uppercase text-zinc-500 dark:border-zinc-800">
              <tr>
                <th className="py-2 pr-3">Titre</th>
                <th className="py-2 pr-3">Format</th>
                <th className="py-2 pr-3">Pages</th>
                <th className="py-2 pr-3">Rendu</th>
                <th className="py-2">Statut</th>
              </tr>
            </thead>
            <tbody>
              {result.documents.map((doc) => (
                <tr key={doc.id} className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="py-2 pr-3 font-medium">
                    <Link href={`/library/${doc.id}`} className="hover:underline">
                      {doc.title}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">{doc.format ?? "—"}</td>
                  <td className="py-2 pr-3">
                    {doc.page_count ?? "—"}
                    {doc.expected_page_count ? ` / ${doc.expected_page_count} attendues` : ""}
                  </td>
                  <td className="py-2 pr-3">{renderProgress(doc)} %</td>
                  <td className="py-2" title={doc.error ?? undefined}>
                    {DOCUMENT_STATUS_LABELS[doc.status]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
