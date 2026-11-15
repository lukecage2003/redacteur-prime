import Link from "next/link";
import { fetchCharter, fetchSeries } from "@/lib/creative";
import { brandVoice, fetchVisuals, fetchVoices } from "@/lib/identity";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

export default async function CreativePage() {
  const [charter, series, voices, visuals] = await Promise.all([
    fetchCharter(api()),
    fetchSeries(api()),
    fetchVoices(api()),
    fetchVisuals(api()),
  ]);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Marque et séries</h1>
      {charter && (
        <section className="mt-6">
          <h2 className="font-semibold">
            Charte v{charter.version} — {charter.name}
          </h2>
          {charter.rules.status && <p className="text-xs text-amber-700">{charter.rules.status}</p>}
          <ul className="mt-2 flex flex-wrap gap-2 text-xs">
            {charter.rules.colors.map((c) => (
              <li key={c.hex} className="flex items-center gap-1 rounded border border-zinc-200 px-2 py-1 dark:border-zinc-800">
                <span className="inline-block h-3 w-3 rounded-sm border border-zinc-300" style={{ background: c.hex }} /> {c.name} · {c.usage}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
            Ton : {charter.rules.tone.do.join(", ")} · Interdit : {charter.rules.tone.dont.join(", ")} · Miniatures : {charter.rules.thumbnail.max_words} mots au plus
          </p>
          <p className="text-xs text-zinc-500">Nouvelle version : primestone-creative charter-publish charte.json (chaque version est conservée).</p>
        </section>
      )}
      <section className="mt-8">
        <h2 className="font-semibold">Séries et franchises</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {(series ?? []).map((s) => (
            <li key={s.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
              <Link href={`/shows/${s.id}`} className="font-medium text-amber-700 hover:underline">{s.name}</Link>{" "}
              <span className="text-xs text-zinc-500">
                {s.status} · {s.target_minutes} min · {s.episodes.length} épisode(s){s.average_score !== null ? ` · note moyenne ${s.average_score}` : ""}
              </span>
              <p className="text-xs">Promesse : {s.promise}</p>
              <p className="text-xs text-zinc-500">Cohérence : {s.consistency.join(" ; ")}</p>
            </li>
          ))}
          {series?.length === 0 && <li className="text-zinc-500">Aucune série : primestone-creative series-create serie.json</li>}
        </ul>
      </section>
      <section className="mt-8">
        <h2 className="font-semibold">Identité de marque (sans le fondateur)</h2>
        <p className="text-xs text-zinc-500">
          Voix FR : {brandVoice(voices ?? [], "fr")?.name ?? "aucune approuvée"} · Voix EN : {brandVoice(voices ?? [], "en")?.name ?? "aucune approuvée"}
        </p>
        <ul className="mt-2 space-y-1 text-sm">
          {(voices ?? []).map((v) => (
            <li key={v.id}>
              {v.name} <span className="text-xs text-zinc-500">· {v.language} · {v.kind} · {v.provider} · licence : {v.license} · {v.status}</span>
            </li>
          ))}
          {voices?.length === 0 && <li className="text-zinc-500">Aucune voix : primestone-identity voice-propose voix.json (licence obligatoire)</li>}
        </ul>
        <ul className="mt-2 space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
          {(visuals ?? []).filter((v) => v.status === "ACTIVE").map((v) => (
            <li key={v.id}>
              Visuel v{v.version} · {v.language ?? "toutes langues"} · {v.platform ?? "toutes plateformes"}{v.series_id ? " · émission" : ""} : {Object.keys(v.rules).join(", ")}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
