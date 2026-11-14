import Link from "next/link";
import { isUuid } from "@/lib/ids";
import { notFound } from "next/navigation";
import { fetchForensicReport, formatPageRanges, type ForensicObservation } from "@/lib/library";
import { runForensic } from "./actions";

export const dynamic = "force-dynamic";

const LEVEL_STYLES: Record<string, string> = {
  CANON: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  INTERPRETATION: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  THEORY: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
  SPECULATION: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
};

function Level({ level }: { level: string }) {
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${LEVEL_STYLES[level] ?? ""}`}>{level}</span>;
}

function EvidenceList({ obs, documentId }: { obs: ForensicObservation; documentId: string }) {
  return (
    <ul className="mt-1 space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
      {obs.evidence.map((e, i) => (
        <li key={i}>
          {e.role === "REFUTES" ? "↯ " : "✓ "}
          <Link
            href={`/library/${e.document_id === documentId ? documentId : e.document_id}/pages/${e.page}`}
            className="underline"
          >
            p. {e.page}
            {e.panel ? `, case ${e.panel}` : ""}
          </Link>{" "}
          — « {e.excerpt} »
        </li>
      ))}
    </ul>
  );
}

export default async function ForensicPage({ params }: { params: Promise<{ documentId: string }> }) {
  const { documentId } = await params;
  if (!isUuid(documentId)) notFound();
  const report = await fetchForensicReport(
    [documentId],
    fetch,
    process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL,
  );
  const doc = report?.documents[documentId];
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href={`/library/${documentId}`} className="text-sm text-amber-700 hover:underline">
        ← Document
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Analyse forensique{doc ? ` — ${doc.title}` : ""}</h1>
      <form action={runForensic.bind(null, documentId)} className="mt-3">
        <button className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">
          Lancer / mettre à jour l&apos;analyse (gratuit)
        </button>
      </form>

      {!report || !doc ? (
        <p className="mt-6 text-zinc-500">Rapport indisponible.</p>
      ) : (
        <div className="mt-6 space-y-8">
          <section
            className={`rounded border p-3 text-sm ${report.status === "COMPLETE" ? "border-emerald-300" : "border-amber-300"}`}
          >
            <strong>{report.status === "COMPLETE" ? "Analyse complète" : "Analyse INCOMPLÈTE"}</strong> — {doc.analyzed_pages}/
            {doc.expected_pages} pages transcrites
            {doc.missing_pages.length > 0 && <> · pages manquantes : {formatPageRanges(doc.missing_pages)}</>}
            <span className="ml-2 text-xs text-zinc-500">({report.extractor})</span>
          </section>

          <section>
            <h2 className="text-lg font-semibold">Contradictions à examiner ({report.contradiction_candidates.length})</h2>
            <ul className="mt-2 space-y-3">
              {report.contradiction_candidates.map((o) => (
                <li key={o.id} className="rounded border border-zinc-200 p-3 dark:border-zinc-800">
                  <Level level={o.level} /> <span className="text-sm">{o.statement}</span>
                  <EvidenceList obs={o} documentId={documentId} />
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold">Personnages</h2>
            <table className="mt-2 w-full text-left text-sm">
              <thead className="text-xs uppercase text-zinc-500">
                <tr>
                  <th className="py-1 pr-3">Nom</th>
                  <th className="py-1 pr-3">Répliques</th>
                  <th className="py-1 pr-3">Mentions</th>
                  <th className="py-1">Première attestation</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(report.characters).map(([name, c]) => (
                  <tr key={name} className="border-t border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-medium">{name}</td>
                    <td className="py-1 pr-3">{c.speeches}</td>
                    <td className="py-1 pr-3">{c.mentions}</td>
                    <td className="py-1">
                      {c.first_appearances.map((f, i) => (
                        <span key={i}>
                          p. {f.page} <Level level={f.level} />
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section>
            <h2 className="text-lg font-semibold">Affirmations des personnages ({report.claims.length})</h2>
            <p className="text-xs text-zinc-500">Ce qu&apos;un personnage affirme n&apos;est pas un fait : il peut mentir ou se tromper.</p>
            <ul className="mt-2 space-y-2">
              {report.claims.map((o) => (
                <li key={o.id} className="text-sm">
                  <Level level={o.level} /> {o.statement}
                  <EvidenceList obs={o} documentId={documentId} />
                </li>
              ))}
            </ul>
          </section>

          {report.alias_candidates.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold">Variantes de noms à confirmer</h2>
              <ul className="mt-2 space-y-1 text-sm">
                {report.alias_candidates.map((o) => (
                  <li key={o.id}>
                    <Level level={o.level} /> {o.statement} ({Math.round(o.confidence * 100)} %)
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section>
            <h2 className="text-lg font-semibold">Observations par type et niveau</h2>
            <ul className="mt-2 text-sm">
              {Object.entries(report.observations_by_kind).map(([kind, levels]) => (
                <li key={kind}>
                  {kind} :{" "}
                  {Object.entries(levels)
                    .map(([level, n]) => `${n} ${level}`)
                    .join(", ")}
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </main>
  );
}
