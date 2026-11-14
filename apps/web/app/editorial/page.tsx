import Link from "next/link";
import { fetchAgents, fetchMissions, MISSION_LABELS } from "@/lib/editorial";
import { fetchDocuments } from "@/lib/library";
import { createMission } from "./actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const input = "w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";

export default async function EditorialPage() {
  const [missions, agents, library] = await Promise.all([fetchMissions(api()), fetchAgents(api()), fetchDocuments(fetch, api())]);
  const documents = library.ok ? library.documents : [];
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Rédaction — Chief Editor</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Missions exécutées par des agents gratuits ; chaque livrable est vérifié citation par citation, puis soumis à votre validation.
      </p>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <form action={createMission} className="space-y-3 rounded border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="font-semibold">Nouvelle mission</h2>
          <select name="type" className={input} defaultValue="CHARACTER_DOSSIER">
            {Object.entries(MISSION_LABELS).filter(([value]) => !["THEORY_REVIEW", "MARKET_BRIEF", "SOCIAL_PACKAGE", "SCRIPT_REVIEW"].includes(value)).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <fieldset className="max-h-40 space-y-1 overflow-y-auto text-sm">
            <legend className="text-xs text-zinc-500">Documents (dans l&apos;ordre de lecture)</legend>
            {documents.map((d) => (
              <label key={d.id} className="flex items-center gap-2">
                <input type="checkbox" name="document_ids" value={d.id} defaultChecked /> {d.title}
              </label>
            ))}
          </fieldset>
          <input name="character" placeholder="Personnage (dossier)" className={input} />
          <input name="question" placeholder="Question (dossier de recherche)" className={input} />
          <p className="text-xs text-zinc-500">
            Revue de théorie : à lancer depuis la fiche de la théorie, dans le <Link href="/lab" className="underline">laboratoire</Link>.
          </p>
          <textarea name="draft" rows={4} placeholder="Texte à vérifier, citations au format « … » [Titre, p. 12, case 3]" className={input} />
          <button className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">Lancer (gratuit)</button>
        </form>

        <div>
          <h2 className="font-semibold">Missions</h2>
          <ul className="mt-2 space-y-2 text-sm">
            {(missions ?? []).map((m) => (
              <li key={m.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                <Link href={`/editorial/${m.id}`} className="font-medium hover:underline">
                  {m.title}
                </Link>
                <span className="ml-2 text-xs text-zinc-500">
                  {MISSION_LABELS[m.type]} · {m.status}
                  {m.recommendation ? ` · ${m.recommendation}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="font-semibold">Agents</h2>
        <ul className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
          {(agents ?? []).map((a) => (
            <li key={a.key} className={`rounded border p-2 dark:border-zinc-800 ${a.available ? "border-zinc-200" : "opacity-50"}`}>
              <span className="font-medium">{a.name}</span>
              <span className="ml-2 text-xs text-zinc-500">{a.available ? "disponible" : `phase ${a.phase}`}</span>
              <p className="text-xs text-zinc-600 dark:text-zinc-400">
                {a.role} — limite : {a.limits}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
