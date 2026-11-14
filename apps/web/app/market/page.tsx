import Link from "next/link";
import { fetchAnalysis, fetchSources, gapLabel } from "@/lib/market";
import { addTopic, launchBrief, verifySource } from "./actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const input = "w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const button = "rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700";
const fmt = (n: number | null) => (n === null ? "—" : n.toLocaleString("fr-FR"));

export default async function MarketPage() {
  const [analysis, sources] = await Promise.all([fetchAnalysis(api()), fetchSources(api())]);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Marché — écarts EN → FR</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Données publiques collectées gratuitement (vues affichées par les plateformes). Aucune métrique privée de concurrent.
      </p>
      {analysis === null && <p className="mt-4 text-sm text-red-700">API injoignable.</p>}

      {analysis && (
        <section className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">Sujets ({analysis.items_considered} contenus, {analysis.window_days} jours)</h2>
            <form action={launchBrief}>
              <button className={button}>Note de marché du Chief Editor</button>
            </form>
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            {analysis.data_class} · {analysis.method} · {analysis.caveat}
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead className="text-xs text-zinc-500">
                <tr>
                  <th className="py-1">Sujet</th>
                  <th>Écart</th>
                  <th>Demande EN</th>
                  <th>Saturation FR</th>
                  <th>Contenus EN / FR</th>
                  <th>Médiane vues EN / FR</th>
                </tr>
              </thead>
              <tbody>
                {analysis.topics.map((t) => (
                  <tr key={t.topic_id} className="border-t border-zinc-200 align-top dark:border-zinc-800">
                    <td className="py-1.5 font-medium">
                      {t.topic}
                      <details className="text-xs font-normal text-zinc-500">
                        <summary>calcul et sources</summary>
                        <ul className="ml-4 list-disc">
                          {t.explanation.map((line) => (
                            <li key={line}>{line}</li>
                          ))}
                          {t.languages.en.sources.map((s, i) => (
                            <li key={`${s.url}-${i}`}>
                              {s.url ? (
                                <a href={s.url} className="underline" rel="noreferrer" target="_blank">
                                  {s.title}
                                </a>
                              ) : (
                                s.title
                              )}{" "}
                              — {fmt(s.views)} vues ({s.data_class})
                            </li>
                          ))}
                        </ul>
                      </details>
                    </td>
                    <td>
                      {t.gap_score ?? "—"} <span className="text-xs text-zinc-500">{gapLabel(t)}</span>
                    </td>
                    <td>{t.demand_en ?? "—"}</td>
                    <td>{t.saturation_fr ?? "—"}</td>
                    <td>
                      {t.languages.en.items} / {t.languages.fr.items}
                    </td>
                    <td>
                      {fmt(t.languages.en.median_views)} / {fmt(t.languages.fr.median_views)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {analysis.niches.length > 0 && <p className="mt-2 text-sm">Niches : {analysis.niches.join(", ")}</p>}
        </section>
      )}

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <form action={addTopic} className="space-y-2 rounded border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="font-semibold">Nouveau sujet</h2>
          <input name="name" required maxLength={200} placeholder="Nom (ex. Sandman)" className={input} />
          <input name="keywords_fr" placeholder="Mots-clés FR, séparés par des virgules" className={input} />
          <input name="keywords_en" placeholder="Mots-clés EN, séparés par des virgules" className={input} />
          <button className={button}>Ajouter</button>
        </form>

        <div>
          <h2 className="font-semibold">Sources</h2>
          <p className="text-xs text-zinc-500">Aucune collecte avant validation humaine de la fiche (accès, quota, conditions).</p>
          <ul className="mt-2 space-y-2 text-sm">
            {(sources ?? []).map((s) => (
              <li key={s.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                <span className="font-medium">{s.name}</span>{" "}
                <span className="text-xs text-zinc-500">
                  {s.kind} · {s.items} contenus · quota : {s.quota}
                </span>
                <p className="text-xs text-zinc-500">
                  Accès : {s.access} ·{" "}
                  <a href={s.terms_url} className="underline" rel="noreferrer" target="_blank">
                    conditions
                  </a>
                </p>
                {s.verified_at ? (
                  <p className="text-xs text-emerald-700">fiche validée par {s.verified_by}</p>
                ) : (
                  <form action={verifySource.bind(null, s.key)}>
                    <button className="mt-1 rounded border border-amber-600 px-2 text-xs text-amber-700">J&apos;ai relu la fiche : valider</button>
                  </form>
                )}
              </li>
            ))}
            {sources?.length === 0 && <li className="text-zinc-500">Aucune source : voir docs/modules/market.md.</li>}
          </ul>
        </div>
      </section>
    </main>
  );
}
