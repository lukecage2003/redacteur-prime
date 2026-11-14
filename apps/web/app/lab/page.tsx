import Link from "next/link";
import { fetchTheories, percent, STATUS_LABELS } from "@/lib/lab";
import { fetchDocuments } from "@/lib/library";
import { createTheory } from "./actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const input = "w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";

export default async function LabPage() {
  const [theories, library] = await Promise.all([fetchTheories(api()), fetchDocuments(fetch, api())]);
  const documents = library.ok ? library.documents : [];
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Laboratoire des théories</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Une théorie n&apos;est jamais canon. Elle devient THÉORIE avec une preuve canon vérifiée et une recherche de contre-preuves ; sinon elle reste SPÉCULATION.
      </p>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <form action={createTheory} className="space-y-3 rounded border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="font-semibold">Nouvelle théorie</h2>
          <input name="title" required maxLength={200} placeholder="Titre" className={input} />
          <textarea name="claim" required rows={3} maxLength={5000} placeholder="Énoncé à éprouver" className={input} />
          <input name="subjects" placeholder="Sujets (personnages), séparés par des virgules" className={input} />
          <fieldset className="max-h-40 space-y-1 overflow-y-auto text-sm">
            <legend className="text-xs text-zinc-500">Documents</legend>
            {documents.map((d) => (
              <label key={d.id} className="flex items-center gap-2">
                <input type="checkbox" name="document_ids" value={d.id} defaultChecked /> {d.title}
              </label>
            ))}
          </fieldset>
          <button className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">Créer</button>
        </form>

        <div>
          <h2 className="font-semibold">Théories</h2>
          {theories === null && <p className="mt-2 text-sm text-red-700">API injoignable.</p>}
          <ul className="mt-2 space-y-2 text-sm">
            {(theories ?? []).map((t) => (
              <li key={t.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                <Link href={`/lab/${t.id}`} className="font-medium hover:underline">
                  {t.title}
                </Link>
                <span className="ml-2 text-xs text-zinc-500">
                  {t.level} · {STATUS_LABELS[t.status]} · confiance {percent(t.confidence)} · {t.supports} pour / {t.refutes} contre
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </main>
  );
}
