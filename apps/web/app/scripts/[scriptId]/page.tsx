import Link from "next/link";
import { notFound } from "next/navigation";
import { isUuid } from "@/lib/ids";
import { CRITERIA_LABELS, fetchScript, verdict } from "@/lib/scripts";
import { addVersion, evaluate, moveStep, validate } from "../actions";

export const dynamic = "force-dynamic";

const input = "w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const button = "rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700";

export default async function ScriptPage({ params }: { params: Promise<{ scriptId: string }> }) {
  const { scriptId } = await params;
  if (!isUuid(scriptId)) notFound();
  const script = await fetchScript(scriptId, process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL);
  if (!script) notFound();
  const versions = script.versions;
  const last = versions.at(-1);
  const score = script.scores.at(-1);
  const editable = script.status !== "VALIDATED";
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/scripts" className="text-sm text-amber-700 hover:underline">
        ← Scripts
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">{script.title}</h1>
      <p className="text-sm text-zinc-500">
        {script.language.toUpperCase()} · étape <strong>{script.step}</strong> · {script.status} · {versions.length} version(s)
      </p>
      <ol className="mt-3 flex flex-wrap gap-1 text-xs">
        {script.steps.map((step, i) => (
          <li key={step} className={`rounded px-1.5 py-0.5 ${step === script.step ? "bg-amber-600 text-white" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400"}`}>
            {i + 1}. {step}
          </li>
        ))}
      </ol>

      {editable && (
        <div className="mt-4 flex flex-wrap items-end gap-2">
          <form action={evaluate.bind(null, script.id)}>
            <button className={button}>Évaluer la dernière version (gratuit)</button>
          </form>
          <form action={validate.bind(null, script.id)}>
            <button className="rounded border border-amber-600 px-3 py-1.5 text-sm text-amber-700">Validation finale</button>
          </form>
          <form action={moveStep.bind(null, script.id)} className="flex gap-2">
            <select name="step" className={input} defaultValue={script.step}>
              {script.steps.slice(0, -1).map((step) => (
                <option key={step}>{step}</option>
              ))}
            </select>
            <input name="reason" placeholder="Motif" className={input} />
            <button className="rounded border border-zinc-300 px-2 text-sm dark:border-zinc-700">Aller</button>
          </form>
        </div>
      )}

      {score && (
        <section className="mt-6">
          <h2 className="font-semibold">
            Version {score.version} : {score.total}/100 — {verdict(score, script.pass_mark)}
          </h2>
          <p className="text-xs text-zinc-500">
            Pré-notation heuristique ({score.analysis.words} mots, ~{score.analysis.estimated_minutes} min) : à confirmer par une relecture humaine.
          </p>
          <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
            {Object.entries(score.criteria).map(([key, c]) => (
              <li key={key} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                <span className="font-medium">{CRITERIA_LABELS[key] ?? key}</span> {c.score}/{c.max}
                <p className="text-xs text-zinc-500">{c.notes.join(" ; ")}</p>
              </li>
            ))}
          </ul>
          {score.analysis.level_checks && (
            <div className="mt-3 text-sm">
              <h3 className="font-medium">Niveau {score.analysis.level_checks.level}</h3>
              <ul className="list-disc pl-5 text-xs">
                {score.analysis.level_checks.checks.map((c) => (
                  <li key={c.check} className={c.ok ? "text-emerald-700" : "text-amber-700"}>
                    {c.check} : {c.detail}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {score.analysis.retention && (
            <div className="mt-3 text-sm">
              <h3 className="font-medium">Rétention (repères du script{score.analysis.retention.drop_offs.length ? " + décrochages observés" : ""})</h3>
              <ul className="list-disc pl-5 text-xs">
                {score.analysis.retention.sections
                  .filter((s) => s.flags.length > 0)
                  .map((s) => (
                    <li key={s.title}>
                      {s.title} : {s.flags.join(" ; ")}
                    </li>
                  ))}
                {score.analysis.retention.drop_offs.map((d) => (
                  <li key={d.at_ratio} className="text-red-700">
                    Décrochage observé à {Math.round(d.at_ratio * 100)} % ({d.section ?? "?"})
                  </li>
                ))}
              </ul>
            </div>
          )}
          {score.analysis.works.length > 0 && (
            <p className="mt-2 text-xs text-zinc-500">
              Œuvres citées :{" "}
              {score.analysis.works.map((w) => `${w.title} (${w.year}) — ${w.status === "IN_LIBRARY" ? "dans la bibliothèque" : "à sourcer"}`).join(" · ")}
            </p>
          )}
        </section>
      )}

      {editable && (
        <form action={addVersion.bind(null, script.id)} className="mt-6 space-y-2">
          <h2 className="font-semibold">Nouvelle version</h2>
          <textarea name="content" required rows={12} defaultValue={last?.content ?? ""} className={`${input} font-mono`} />
          <button className={button}>Enregistrer la version</button>
        </form>
      )}

      <section className="mt-6">
        <h2 className="font-semibold">Historique</h2>
        <ol className="mt-2 space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
          {script.events.map((e, i) => (
            <li key={`${e.created_at}-${i}`}>
              {new Date(e.created_at).toLocaleString("fr-FR")} — {e.action} par {e.author}
              {e.reason ? ` (${e.reason})` : ""}
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
