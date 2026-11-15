import Link from "next/link";
import { notFound } from "next/navigation";
import { isUuid } from "@/lib/ids";
import { acceptsEpisodes, fetchShow, fetchShowPerformance, nextStatuses } from "@/lib/shows";
import { proposeTransition } from "../actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

export default async function ShowPage({ params }: { params: Promise<{ seriesId: string }> }) {
  const { seriesId } = await params;
  if (!isUuid(seriesId)) notFound();
  const [show, perf] = await Promise.all([fetchShow(seriesId, api()), fetchShowPerformance(seriesId, api())]);
  if (!show) notFound();
  const next = nextStatuses(show.status);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/creative" className="text-sm text-amber-700 hover:underline">
        ← Marque et séries
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">{show.name}</h1>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        {show.status} · règles v{show.guideline_version} · {show.languages.join(" / ")}
        {show.expertise_level ? ` · ${show.expertise_level}` : ""}
        {show.pillar ? ` · pilier ${show.pillar}` : ""}
      </p>
      <p className="mt-1 text-sm">Promesse : {show.promise}</p>
      {!acceptsEpisodes(show.status) && <p className="mt-1 text-xs text-amber-700">Aucun nouvel épisode accepté dans cet état.</p>}
      {show.pending.length > 0 && (
        <p className="mt-2 text-xs">
          {show.pending.length} décision(s) en attente :{" "}
          <Link href="/governance" className="text-amber-700 hover:underline">
            gouvernance
          </Link>
        </p>
      )}
      {next.length > 0 && show.pending.every((p) => p.action !== "SHOW_LIFECYCLE") && (
        <form action={proposeTransition.bind(null, show.id)} className="mt-3 flex flex-wrap items-center gap-2">
          <select name="to" className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900">
            {next.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <input name="reason" placeholder="Motif" className="min-w-0 flex-1 rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" />
          <button className="rounded bg-zinc-800 px-3 py-1 text-xs text-white dark:bg-zinc-200 dark:text-zinc-900">Proposer la transition</button>
        </form>
      )}
      <section className="mt-6">
        <h2 className="font-semibold">Formats</h2>
        <ul className="mt-2 space-y-1 text-sm">
          {show.formats.map((f) => (
            <li key={f.id}>
              {f.name} <span className="text-xs text-zinc-500">· {f.platform} · {f.language} · {f.min_minutes} à {f.max_minutes} min · {f.structure.join(" → ")} · {f.status}</span>
            </li>
          ))}
          {show.formats.length === 0 && <li className="text-zinc-500">Aucun format : primestone-shows format ID format.json</li>}
        </ul>
      </section>
      <section className="mt-6">
        <h2 className="font-semibold">Épisodes</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {show.episodes.map((e) => (
            <li key={e.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
              {e.number}. {e.title}{" "}
              <span className="text-xs text-zinc-500">
                · {e.status} · {e.language ?? "?"} · script {e.script_status} · règles v{e.guideline_version ?? "?"}
              </span>
              <p className="text-xs text-zinc-600 dark:text-zinc-400">{e.conformance.join(" ; ")}</p>
            </li>
          ))}
        </ul>
      </section>
      <section className="mt-6">
        <h2 className="font-semibold">Performance de l&apos;émission</h2>
        {perf && perf.contents > 0 && perf.total ? (
          <p className="text-sm">
            {Object.entries(perf.total)
              .map(([k, v]) => `${k} : ${v}`)
              .join(" · ")}
          </p>
        ) : (
          <p className="text-sm text-zinc-500">Non fourni : aucune statistique importée pour ses contenus.</p>
        )}
      </section>
    </main>
  );
}
