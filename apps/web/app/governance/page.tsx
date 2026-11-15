import Link from "next/link";
import { allowedDecisions, fetchBrands, fetchDecisions, fetchPillars, fetchPolicies } from "@/lib/governance";
import { decide } from "./actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const LABELS = { approve: "Approuver", reject: "Rejeter", revert: "Annuler" } as const;

export default async function GovernancePage() {
  const [brands, decisions, policies, pillars] = await Promise.all([
    fetchBrands(api()),
    fetchDecisions(api()),
    fetchPolicies(api()),
    fetchPillars(api()),
  ]);
  const brand = brands?.[0];
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Gouvernance éditoriale</h1>
      {brand && (
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          {brand.name} · {brand.languages.join(" / ")} · {brand.mission}
        </p>
      )}
      <p className="mt-1 text-xs text-zinc-500">Les agents proposent ; seul le fondateur approuve, rejette ou annule. Tout est journalisé.</p>
      <section className="mt-6">
        <h2 className="font-semibold">Journal des décisions</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {(decisions ?? []).map((d) => (
            <li key={d.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
              <span className="font-medium">{d.action}</span>{" "}
              <span className="text-xs text-zinc-500">
                {d.status} · {d.subject_type} {d.subject_id ?? ""} · proposé par {d.proposed_by}
                {d.decided_by ? ` · décidé par ${d.decided_by}` : ""}
                {d.reason ? ` · ${d.reason}` : ""}
              </span>
              <pre className="mt-1 overflow-x-auto text-xs text-zinc-600 dark:text-zinc-400">{JSON.stringify(d.proposal)}</pre>
              {allowedDecisions(d.status).length > 0 && (
                <form action={decide.bind(null, d.id)} className="mt-2 flex flex-wrap items-center gap-2">
                  <input name="reason" placeholder="Motif (obligatoire pour rejeter ou annuler)" className="min-w-0 flex-1 rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" />
                  {allowedDecisions(d.status).map((a) => (
                    <button key={a} name="decision" value={a} className="rounded bg-zinc-800 px-3 py-1 text-xs text-white dark:bg-zinc-200 dark:text-zinc-900">
                      {LABELS[a]}
                    </button>
                  ))}
                </form>
              )}
            </li>
          ))}
          {decisions?.length === 0 && <li className="text-zinc-500">Aucune décision.</li>}
        </ul>
      </section>
      <section className="mt-8 grid gap-6 sm:grid-cols-2">
        <div>
          <h2 className="font-semibold">Piliers éditoriaux</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {(pillars ?? []).map((p) => (
              <li key={p.id}>
                {p.name} <span className="text-xs text-zinc-500">· {p.status} · v{p.version}</span>
              </li>
            ))}
            {pillars?.length === 0 && <li className="text-zinc-500">Aucun pilier : primestone-brand pillar NOM &quot;description&quot;</li>}
          </ul>
        </div>
        <div>
          <h2 className="font-semibold">Politiques</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {(policies ?? []).map((p) => (
              <li key={p.action}>
                {p.action} <span className="text-xs text-zinc-500">· {p.requires_approval ? `approbation ${p.approver}` : "automatique (journalisé)"} · v{p.version}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </main>
  );
}
