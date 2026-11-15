import Link from "next/link";
import { fetchCommunity, fetchSegments, observedKinds } from "@/lib/audience";
import { createSegment } from "./actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const input = "w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";

export default async function AudiencePage() {
  const [segments, community] = await Promise.all([fetchSegments(api()), fetchCommunity(api())]);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Audiences</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Segments définis par motivations et niveau de connaissance, jamais par l&apos;âge. Confirmé seulement avec deux natures de preuves observées.
      </p>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <div>
          <h2 className="font-semibold">Segments</h2>
          <ul className="mt-2 space-y-2 text-sm">
            {(segments ?? []).map((s) => (
              <li key={s.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                <span className="font-medium">{s.name}</span>{" "}
                <span className={`text-xs ${s.status === "CONFIRMED" ? "text-emerald-700" : "text-amber-700"}`}>
                  {s.status === "CONFIRMED" ? "confirmé" : "hypothèse"}
                </span>
                <p className="text-xs text-zinc-500">
                  {s.motivations.join(" · ")} {s.knowledge_level ? `· ${s.knowledge_level}` : ""} · preuves observées : {observedKinds(s).join(", ") || "aucune"}
                </p>
                {s.links.length > 0 && <p className="text-xs text-zinc-500">liens : {s.links.map((l) => `${l.relation} ${l.label}`).join(" · ")}</p>}
              </li>
            ))}
          </ul>
        </div>
        <form action={createSegment} className="space-y-2 rounded border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="font-semibold">Nouveau segment (hypothèse)</h2>
          <input name="name" required maxLength={300} placeholder="Nom (ex. Curieux du cosmique)" className={input} />
          <textarea name="description" required rows={2} placeholder="Ce qu'ils cherchent" className={input} />
          <input name="motivations" required placeholder="Motivations, séparées par des virgules" className={input} />
          <select name="knowledge_level" className={input} defaultValue="">
            <option value="">Niveau de connaissance : —</option>
            <option value="NOVICE">Débutant</option>
            <option value="INTERMEDIATE">Intermédiaire</option>
            <option value="EXPERT">Expert</option>
          </select>
          <button className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">Créer</button>
        </form>
      </section>

      {community && (
        <section className="mt-8">
          <h2 className="font-semibold">Communauté ({community.comments} commentaires publics)</h2>
          <p className="text-xs text-zinc-500">{community.rule}</p>
          <ul className="mt-2 list-disc pl-5 text-sm">
            {community.proposals.map((p) => (
              <li key={p}>{p}</li>
            ))}
            {community.proposals.length === 0 && <li className="text-zinc-500">Pas encore de question ou demande récurrente.</li>}
          </ul>
        </section>
      )}
    </main>
  );
}
