import Link from "next/link";
import { notFound } from "next/navigation";
import { canDecline, checkSeverity, fetchMission, MISSION_LABELS } from "@/lib/editorial";
import { isUuid } from "@/lib/ids";
import { decide, decline } from "../actions";

export const dynamic = "force-dynamic";

const SEVERITY = {
  ok: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  review: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  error: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
  neutral: "bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400",
};

export default async function MissionPage({ params }: { params: Promise<{ missionId: string }> }) {
  const { missionId } = await params;
  if (!isUuid(missionId)) notFound();
  const mission = await fetchMission(missionId, process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL);
  if (!mission) notFound();
  const pending = mission.approvals.find((a) => a.status === "PENDING");
  const result = mission.result;
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/editorial" className="text-sm text-amber-700 hover:underline">
        ← Rédaction
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">{mission.title}</h1>
      <p className="text-sm text-zinc-500">
        {MISSION_LABELS[mission.type]} · statut : <strong>{mission.status}</strong>
        {mission.error ? ` · ${mission.error}` : ""}
      </p>
      {canDecline(mission) && (
        <form action={decline.bind(null, mission.id)} className="mt-2">
          <button className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">Décliner pour YouTube, TikTok, Instagram (gratuit)</button>
        </form>
      )}

      <section className="mt-6">
        <h2 className="font-semibold">Tâches des agents</h2>
        <ol className="mt-2 space-y-1 text-sm">
          {mission.tasks.map((t) => (
            <li key={t.position}>
              {t.position}. {t.agent_name} — {t.status}
              {t.critical ? " (critique)" : ""}
              {t.attempts > 1 ? ` · ${t.attempts} tentatives` : ""}
              {t.error ? ` · ${t.error}` : ""}
            </li>
          ))}
        </ol>
      </section>

      {result && (
        <>
          <section className="mt-6 rounded border border-zinc-200 p-3 dark:border-zinc-800">
            <h2 className="font-semibold">Recommandation du Chief Editor : {result.recommendation}</h2>
            <ul className="mt-2 list-disc pl-5 text-sm">
              {result.findings.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </section>

          {pending && (
            <form action={decide.bind(null, mission.id, pending.id)} className="mt-4 flex flex-wrap items-center gap-2">
              <input name="comment" placeholder="Commentaire (facultatif)" className="flex-1 rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
              <button name="decision" value="approve" className="rounded bg-emerald-700 px-3 py-1 text-sm text-white">
                Valider
              </button>
              <button name="decision" value="reject" className="rounded bg-zinc-700 px-3 py-1 text-sm text-white">
                Rejeter
              </button>
            </form>
          )}

          <section className="mt-6">
            <h2 className="font-semibold">Livrable ({result.author})</h2>
            <pre className="mt-2 whitespace-pre-wrap rounded bg-zinc-100 p-3 text-sm dark:bg-zinc-900">{result.deliverable}</pre>
          </section>

          <section className="mt-6">
            <h2 className="font-semibold">Vérification phrase par phrase — {result.fact_check.verdict}</h2>
            <ul className="mt-2 space-y-1 text-sm">
              {result.fact_check.checks
                .filter((c) => c.status !== "NOT_FACTUAL")
                .map((c, i) => (
                  <li key={i}>
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${SEVERITY[checkSeverity(c.status)]}`}>{c.status}</span>{" "}
                    {c.sentence}
                    {c.detail && c.status !== "VERIFIED" ? <span className="text-xs text-zinc-500"> — {c.detail}</span> : null}
                  </li>
                ))}
            </ul>
          </section>
        </>
      )}

      {mission.approvals
        .filter((a) => a.status !== "PENDING")
        .map((a) => (
          <p key={a.id} className="mt-6 text-sm">
            Décision : <strong>{a.status}</strong> par {a.decided_by}
            {a.comment ? ` — ${a.comment}` : ""}
          </p>
        ))}
    </main>
  );
}
