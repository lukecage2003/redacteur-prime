import Link from "next/link";
import { notFound } from "next/navigation";
import { isUuid } from "@/lib/ids";
import { EVIDENCE_STATE_LABELS, evidenceState, fetchTheory, percent, STATUS_LABELS, type TheoryEvidence } from "@/lib/lab";
import { addAlternative, addEvidence, research, retractEvidence, review } from "../actions";

export const dynamic = "force-dynamic";

const input = "w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const button = "rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700";
const STATE_STYLE = {
  verified: "text-emerald-700 dark:text-emerald-400",
  visual: "text-zinc-600 dark:text-zinc-400",
  unverified: "text-amber-700 dark:text-amber-400",
  stale: "text-red-700 dark:text-red-400",
  retracted: "text-zinc-400 line-through",
};

function EvidenceItem({ theoryId, e }: { theoryId: string; e: TheoryEvidence }) {
  const state = evidenceState(e);
  return (
    <li className="rounded border border-zinc-200 p-2 text-sm dark:border-zinc-800">
      <p className={state === "retracted" ? "line-through opacity-60" : ""}>
        {e.excerpt ? <q>{e.excerpt}</q> : <em>preuve visuelle</em>}{" "}
        <Link href={`/library/${e.document_id}/pages/${e.page_number}`} className="text-amber-700 hover:underline">
          [{e.document_title}, p. {e.page_number}
          {e.panel_index ? `, case ${e.panel_index}` : ""}]
        </Link>
      </p>
      <p className="text-xs text-zinc-500">
        {e.level} · <span className={STATE_STYLE[state]}>{EVIDENCE_STATE_LABELS[state]}</span> · par {e.added_by}
        {e.note ? ` · ${e.note}` : ""}
        {e.retraction_reason ? ` · motif du retrait : ${e.retraction_reason}` : ""}
      </p>
      {state !== "retracted" && (
        <form action={retractEvidence.bind(null, theoryId, e.id)} className="mt-1 flex gap-2">
          <input name="reason" required placeholder="Motif du retrait" className={input} />
          <button className="rounded border border-zinc-300 px-2 text-xs dark:border-zinc-700">Retirer</button>
        </form>
      )}
    </li>
  );
}

export default async function TheoryPage({ params }: { params: Promise<{ theoryId: string }> }) {
  const { theoryId } = await params;
  if (!isUuid(theoryId)) notFound();
  const theory = await fetchTheory(theoryId, process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL);
  if (!theory) notFound();
  const byRole = (role: TheoryEvidence["role"]) => theory.evidence.filter((e) => e.role === role);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/lab" className="text-sm text-amber-700 hover:underline">
        ← Laboratoire
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">{theory.title}</h1>
      <p className="mt-1">{theory.claim}</p>
      <p className="mt-2 text-sm text-zinc-500">
        <strong>{theory.level}</strong> · {STATUS_LABELS[theory.status]} · confiance {percent(theory.confidence)} · contre-preuves{" "}
        {theory.counter_search_at ? "cherchées" : "pas encore cherchées"}
      </p>
      <details className="mt-1 text-xs text-zinc-500">
        <summary>Calcul ({theory.scoring.method})</summary>
        <ul className="ml-4 list-disc">
          {theory.scoring.explanation.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </details>
      <div className="mt-3 flex flex-wrap gap-2">
        <form action={research.bind(null, theory.id)}>
          <button className={button}>Chercher des contre-preuves (gratuit)</button>
        </form>
        <form action={review.bind(null, theory.id)}>
          <button className="rounded border border-amber-600 px-3 py-1.5 text-sm text-amber-700">Revue par le Chief Editor</button>
        </form>
      </div>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        {(["SUPPORTS", "REFUTES"] as const).map((role) => (
          <div key={role}>
            <h2 className="font-semibold">{role === "SUPPORTS" ? "Preuves pour" : "Contre-preuves"}</h2>
            <ul className="mt-2 space-y-2">
              {byRole(role).map((e) => (
                <EvidenceItem key={e.id} theoryId={theory.id} e={e} />
              ))}
              {byRole(role).length === 0 && <li className="text-sm text-zinc-500">Aucune.</li>}
            </ul>
          </div>
        ))}
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <form action={addEvidence.bind(null, theory.id)} className="space-y-2 rounded border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="font-semibold">Ajouter une preuve</h2>
          <select name="role" className={input} defaultValue="SUPPORTS">
            <option value="SUPPORTS">pour</option>
            <option value="REFUTES">contre</option>
          </select>
          <select name="document_id" className={input}>
            {theory.documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title} ({d.page_count ?? "?"} p.)
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <input name="page" type="number" min={1} required placeholder="Page" className={input} />
            <input name="panel" type="number" min={1} placeholder="Case" className={input} />
          </div>
          <input name="excerpt" placeholder="Extrait exact (vérifié sur la transcription)" className={input} />
          <select name="level" className={input} defaultValue="CANON">
            <option value="CANON">CANON (ce que la page montre ou dit)</option>
            <option value="INTERPRETATION">INTERPRÉTATION (note obligatoire)</option>
            <option value="SPECULATION">SPÉCULATION (note obligatoire)</option>
          </select>
          <input name="note" placeholder="Note" className={input} />
          <button className={button}>Ajouter</button>
        </form>

        <div>
          <h2 className="font-semibold">Explications alternatives</h2>
          <ul className="mt-2 list-disc pl-5 text-sm">
            {theory.alternatives.map((a) => (
              <li key={a.id}>{a.text}</li>
            ))}
          </ul>
          <form action={addAlternative.bind(null, theory.id)} className="mt-2 flex gap-2">
            <input name="text" required placeholder="Autre explication possible" className={input} />
            <button className={button}>Ajouter</button>
          </form>
        </div>
      </section>

      <section className="mt-6">
        <h2 className="font-semibold">Historique</h2>
        <ol className="mt-2 space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
          {theory.events.map((e, i) => (
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
