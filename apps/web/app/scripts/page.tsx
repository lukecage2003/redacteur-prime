import Link from "next/link";
import { fetchDocuments } from "@/lib/library";
import { fetchScripts } from "@/lib/scripts";
import { createScript } from "./actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const input = "w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";

export default async function ScriptsPage() {
  const [scripts, library] = await Promise.all([fetchScripts(api()), fetchDocuments(fetch, api())]);
  const documents = library.ok ? library.documents : [];
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Scripts</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        13 étapes, pré-notation sur 100 et veto factuel : un script avec une erreur factuelle majeure n&apos;est jamais validé.
      </p>
      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <form action={createScript} className="space-y-2 rounded border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="font-semibold">Nouveau script</h2>
          <input name="title" required maxLength={300} placeholder="Titre" className={input} />
          <select name="language" className={input} defaultValue="fr">
            <option value="fr">Français</option>
            <option value="en">English</option>
          </select>
          <textarea name="content" rows={8} placeholder={"00:00 - Introduction\nTexte…\n\n02:10 - Partie 1\n…"} className={`${input} font-mono`} />
          <fieldset className="max-h-32 space-y-1 overflow-y-auto text-sm">
            <legend className="text-xs text-zinc-500">Comics cités (pour vérifier les citations de pages)</legend>
            {documents.map((d) => (
              <label key={d.id} className="flex items-center gap-2">
                <input type="checkbox" name="document_ids" value={d.id} /> {d.title}
              </label>
            ))}
          </fieldset>
          <button className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">Créer</button>
        </form>
        <div>
          <h2 className="font-semibold">Scripts</h2>
          {scripts === null && <p className="mt-2 text-sm text-red-700">API injoignable.</p>}
          <ul className="mt-2 space-y-2 text-sm">
            {(scripts ?? []).map((s) => (
              <li key={s.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                <Link href={`/scripts/${s.id}`} className="font-medium hover:underline">
                  {s.title}
                </Link>
                <span className="ml-2 text-xs text-zinc-500">
                  {s.language.toUpperCase()} · {s.step} · {s.status} · v{s.versions ?? 0}
                  {s.last_total !== null ? ` · ${s.last_total}/100` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </main>
  );
}
