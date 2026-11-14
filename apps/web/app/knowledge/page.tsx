import Link from "next/link";
import { fetchEntities, searchLibrary } from "@/lib/knowledge";
import { buildKnowledge } from "./actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

export default async function KnowledgePage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q } = await searchParams;
  const query = (q ?? "").slice(0, 200);
  const [entities, hits] = await Promise.all([
    fetchEntities(query || undefined, api()),
    query ? searchLibrary(query, api()) : Promise.resolve(null),
  ]);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Connaissances</h1>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <form className="flex gap-2" action="/knowledge">
          <input
            name="q"
            defaultValue={query}
            placeholder="Rechercher (tolère les fautes)"
            className="w-72 rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button className="rounded border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-700">Chercher</button>
        </form>
        <form action={buildKnowledge}>
          <button className="rounded bg-amber-600 px-3 py-1 text-sm font-medium text-white hover:bg-amber-700">
            Construire depuis la bibliothèque (gratuit)
          </button>
        </form>
      </div>

      {hits && (
        <section className="mt-6">
          <h2 className="text-lg font-semibold">Résultats</h2>
          <ul className="mt-2 space-y-2 text-sm">
            {hits.map((hit) => (
              <li key={`${hit.kind}-${hit.ref_id}`} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                {hit.kind === "ENTITY" ? (
                  <Link href={`/knowledge/${hit.ref_id}`} className="font-medium underline">
                    {hit.content}
                  </Link>
                ) : (
                  <>
                    « {hit.content} » —{" "}
                    <Link href={`/library/${hit.document_id}/pages/${hit.page}`} className="underline">
                      p. {hit.page}
                      {hit.panel ? `, case ${hit.panel}` : ""}
                    </Link>
                  </>
                )}
                <span className="ml-2 text-xs text-zinc-500">
                  {hit.fulltext_rank !== null ? "texte " : ""}
                  {hit.vector_similarity !== null ? `· similarité ${Math.round(hit.vector_similarity * 100)} %` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Entités ({entities?.length ?? 0})</h2>
        {!entities ? (
          <p className="text-sm text-zinc-500">API indisponible.</p>
        ) : (
          <ul className="mt-2 grid gap-2 sm:grid-cols-2">
            {entities.map((e) => (
              <li key={e.id} className="rounded border border-zinc-200 p-2 text-sm dark:border-zinc-800">
                <Link href={`/knowledge/${e.id}`} className="font-medium hover:underline">
                  {e.canonical_name}
                </Link>
                <span className="ml-2 text-xs text-zinc-500">
                  {e.type} · {e.relations} relation(s)
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
