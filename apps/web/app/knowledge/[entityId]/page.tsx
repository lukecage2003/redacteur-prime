import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { isUuid } from "@/lib/ids";
import { describeRelation, fetchEntities, fetchEntity } from "@/lib/knowledge";
import { correctEntity, retractRelation } from "../actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const input = "rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const LEVEL = {
  CANON: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  INTERPRETATION: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  SPECULATION: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
} as Record<string, string>;

export default async function EntityPage({ params }: { params: Promise<{ entityId: string }> }) {
  const { entityId } = await params;
  if (!isUuid(entityId)) notFound();
  const entity = await fetchEntity(entityId, api());
  if (!entity) notFound();
  if (entity.merged_into) redirect(`/knowledge/${entity.merged_into}`);
  const sameType = ((await fetchEntities(undefined, api())) ?? []).filter(
    (e) => e.type === entity.type && e.id !== entity.id,
  );
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/knowledge" className="text-sm text-amber-700 hover:underline">
        ← Connaissances
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">{entity.canonical_name}</h1>
      <p className="text-sm text-zinc-500">
        {entity.type} · alias : {entity.aliases.map((a) => a.alias).join(", ")}
      </p>

      <section className="mt-6">
        <h2 className="text-lg font-semibold">Relations prouvées</h2>
        <ul className="mt-2 space-y-3">
          {entity.relations.map((r) => (
            <li
              key={r.id}
              className={`rounded border p-3 text-sm dark:border-zinc-800 ${r.retracted ? "opacity-50" : "border-zinc-200"}`}
            >
              <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${LEVEL[r.level] ?? ""}`}>{r.level}</span>{" "}
              {describeRelation(r, entity.id)}
              <span className="ml-2 text-xs text-zinc-500">
                {r.origin === "HUMAN" ? "saisie humaine" : "extraite"}
                {r.retracted ? " · RETIRÉE" : ""}
              </span>
              <ul className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                {r.evidence.slice(0, 5).map((e, i) => (
                  <li key={i}>
                    <Link href={`/library/${e.document_id}/pages/${e.page}`} className="underline">
                      p. {e.page}
                      {e.panel ? `, case ${e.panel}` : ""}
                    </Link>{" "}
                    {e.excerpt ? `— « ${e.excerpt} »` : ""}
                  </li>
                ))}
                {r.evidence.length > 5 && <li>… et {r.evidence.length - 5} autre(s) preuve(s)</li>}
              </ul>
              {!r.retracted && (
                <form action={retractRelation.bind(null, entity.id, r.id)} className="mt-2 flex gap-2">
                  <input name="reason" placeholder="Motif du retrait" required className={`${input} flex-1`} />
                  <button className="text-xs text-red-700 underline">Retirer</button>
                </form>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8 grid gap-4 sm:grid-cols-3">
        <form action={correctEntity.bind(null, entity.id)} className="space-y-2 rounded border border-zinc-200 p-3 dark:border-zinc-800">
          <h3 className="text-sm font-semibold">Ajouter un alias</h3>
          <input type="hidden" name="action" value="add_alias" />
          <input name="value" placeholder="Alias (ex. nom VF)" required className={`${input} w-full`} />
          <input name="language" placeholder="fr / en" className={`${input} w-full`} />
          <input name="reason" placeholder="Motif" required className={`${input} w-full`} />
          <button className="rounded bg-zinc-800 px-2 py-1 text-xs text-white">Ajouter</button>
        </form>
        <form action={correctEntity.bind(null, entity.id)} className="space-y-2 rounded border border-zinc-200 p-3 dark:border-zinc-800">
          <h3 className="text-sm font-semibold">Renommer</h3>
          <input type="hidden" name="action" value="rename" />
          <input name="value" defaultValue={entity.canonical_name} required className={`${input} w-full`} />
          <input name="reason" placeholder="Motif" required className={`${input} w-full`} />
          <button className="rounded bg-zinc-800 px-2 py-1 text-xs text-white">Renommer</button>
        </form>
        <form action={correctEntity.bind(null, entity.id)} className="space-y-2 rounded border border-zinc-200 p-3 dark:border-zinc-800">
          <h3 className="text-sm font-semibold">Absorber un doublon</h3>
          <input type="hidden" name="action" value="merge" />
          <select name="other_entity_id" required className={`${input} w-full`}>
            {sameType.map((e) => (
              <option key={e.id} value={e.id}>
                {e.canonical_name}
              </option>
            ))}
          </select>
          <input name="reason" placeholder="Motif" required className={`${input} w-full`} />
          <button className="rounded bg-zinc-800 px-2 py-1 text-xs text-white">Fusionner ici</button>
        </form>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">Historique des corrections</h2>
        <ul className="mt-2 text-sm">
          {entity.history.length === 0 && <li className="text-zinc-500">Aucune correction.</li>}
          {entity.history.map((h, i) => (
            <li key={i}>
              {new Date(h.created_at).toLocaleString("fr-FR")} — {h.action} par {h.author} : {h.reason}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
