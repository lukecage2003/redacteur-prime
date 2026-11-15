import Link from "next/link";
import { fetchCosts, fetchLessons, fetchRights, rightsUsable } from "@/lib/memory";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

export default async function MemoryPage() {
  const [lessons, rights, costs] = await Promise.all([fetchLessons(api()), fetchRights(api()), fetchCosts(api())]);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Mémoire, droits et coûts</h1>
      <section className="mt-6">
        <h2 className="font-semibold">Leçons prouvées</h2>
        <p className="text-xs text-zinc-500">Seulement depuis des statistiques observées ou une expérience concluante.</p>
        <ul className="mt-2 space-y-1 text-sm">
          {(lessons ?? []).map((l) => (
            <li key={l.id} className={l.status === "RETRACTED" ? "text-zinc-400 line-through" : ""}>
              {l.lesson} <span className="text-xs text-zinc-500">· {l.evidence_level}{l.show ? ` · ${l.show}` : ""} · {l.recorded_by}</span>
            </li>
          ))}
          {lessons?.length === 0 && <li className="text-zinc-500">Aucune leçon : primestone-memory lesson …</li>}
        </ul>
      </section>
      <section className="mt-8">
        <h2 className="font-semibold">Registre des droits et sources</h2>
        <ul className="mt-2 space-y-1 text-sm">
          {(rights ?? []).map((r) => (
            <li key={r.id}>
              {r.kind} · {r.subject}{" "}
              <span className="text-xs text-zinc-500">
                {r.document_title ? `· ${r.document_title} p. ${r.page_number ?? "?"}${r.panel_number ? ` case ${r.panel_number}` : ""} ` : ""}· {r.basis} · {r.limits} · {rightsUsable(r) ? "utilisable" : "inutilisable (retiré ou échu)"}
              </span>
            </li>
          ))}
          {rights?.length === 0 && <li className="text-zinc-500">Registre vide : toute citation de case en production exige un droit.</li>}
        </ul>
      </section>
      {costs && (
        <section className="mt-8">
          <h2 className="font-semibold">Coûts</h2>
          <p className="text-sm">
            Total : {costs.total_usd.toFixed(2)} $ · mode zéro coût : {costs.zero_cost_mode ? "actif" : "désactivé"}
          </p>
          <ul className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
            {costs.by_show.map((s) => (
              <li key={s.series_id}>
                {s.name} : {Number(s.cost_usd).toFixed(2)} $ ({s.missions} mission(s))
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
