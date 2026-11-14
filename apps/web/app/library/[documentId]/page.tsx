import Link from "next/link";
import { notFound } from "next/navigation";
import { DOCUMENT_STATUS_LABELS, fetchDocument, pageImageUrl } from "@/lib/library";

export const dynamic = "force-dynamic";

const serverApi = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

export default async function DocumentPage({ params }: { params: Promise<{ documentId: string }> }) {
  const { documentId } = await params;
  const doc = await fetchDocument(documentId, fetch, serverApi());
  if (!doc) notFound();
  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <Link href="/library" className="text-sm text-amber-700 hover:underline">
        ← Bibliothèque
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">{doc.title}</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        {doc.format ?? "—"} · {doc.page_count ?? "?"} pages · {DOCUMENT_STATUS_LABELS[doc.status]}
        {doc.error ? ` · ${doc.error}` : ""}
      </p>
      <ul className="mt-6 grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-8">
        {doc.pages.map((page) => (
          <li key={page.number}>
            <Link href={`/library/${documentId}/pages/${page.number}`} className="block">
              {page.status === "RENDERED" ? (
                // eslint-disable-next-line @next/next/no-img-element -- images servies par l'API
                <img
                  src={pageImageUrl(documentId, page.number, process.env.NEXT_PUBLIC_API_BASE_URL)}
                  alt={`Page ${page.number}`}
                  loading="lazy"
                  className="aspect-[2/3] w-full rounded border border-zinc-200 object-cover dark:border-zinc-800"
                />
              ) : (
                <div className="flex aspect-[2/3] items-center justify-center rounded border border-dashed text-xs text-zinc-500">
                  {page.status}
                </div>
              )}
              <span className="mt-1 block text-center text-xs text-zinc-500">{page.number}</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
