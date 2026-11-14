import Link from "next/link";
import { fetchContents, fetchReport, METRIC_LABELS, signalStrength } from "@/lib/performance";
import { fetchScripts } from "@/lib/scripts";
import { importStudio, linkScript } from "./actions";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const SHOWN = ["views", "ctr", "avg_view_percentage", "avg_view_duration_s"];
const fmt = (v: number | undefined) => (v === undefined ? "—" : v.toLocaleString("fr-FR", { maximumFractionDigits: 1 }));

export default async function PerformancePage() {
  const [contents, report, scripts] = await Promise.all([fetchContents(api()), fetchReport(api()), fetchScripts(api())]);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Performances de la chaîne</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Données de la chaîne Primestone uniquement (export YouTube Studio, gratuit). Aucune métrique de concurrent.
      </p>

      <form action={importStudio} className="mt-4 flex flex-wrap items-center gap-2 rounded border border-zinc-200 p-3 text-sm dark:border-zinc-800">
        <span className="font-medium">Importer un export CSV de YouTube Studio</span>
        <input type="file" name="file" accept=".csv,text/csv" required className="text-sm" />
        <button className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">Importer</button>
      </form>

      {report && (
        <section className="mt-6">
          <h2 className="font-semibold">Ce que les données suggèrent</h2>
          <p className="text-xs text-zinc-500">
            {report.method} · {report.linked_to_scored_script}/{report.contents} vidéo(s) reliée(s) à un script noté · {report.caveat}
          </p>
          {report.status !== "OK" && (
            <p className="mt-2 text-sm">Données insuffisantes : reliez au moins {report.min_items} vidéos à des scripts notés.</p>
          )}
          <ul className="mt-2 list-disc pl-5 text-sm">
            {report.signals.slice(0, 6).map((s) => (
              <li key={`${s.criterion}-${s.target}`}>
                {s.criterion} ↔ {METRIC_LABELS[s.target] ?? s.target} : rho {s.rho.toFixed(2)} ({signalStrength(s.rho)}, n = {s.n})
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-6 overflow-x-auto">
        <h2 className="font-semibold">Vidéos</h2>
        <table className="mt-2 w-full min-w-[40rem] text-left text-sm">
          <thead className="text-xs text-zinc-500">
            <tr>
              <th className="py-1">Titre</th>
              {SHOWN.map((m) => (
                <th key={m}>{METRIC_LABELS[m]}</th>
              ))}
              <th>Script</th>
            </tr>
          </thead>
          <tbody>
            {(contents ?? []).map((c) => (
              <tr key={c.id} className="border-t border-zinc-200 align-top dark:border-zinc-800">
                <td className="py-1.5">{c.title}</td>
                {SHOWN.map((m) => (
                  <td key={m}>{fmt(c.metrics[m])}</td>
                ))}
                <td>
                  {c.script_id ? (
                    <Link href={`/scripts/${c.script_id}`} className="text-amber-700 hover:underline">
                      {c.script_title} {c.script_total !== null ? `(${c.script_total}/100)` : ""}
                    </Link>
                  ) : (
                    <form action={linkScript.bind(null, c.id)} className="flex gap-1">
                      <select name="script_id" className="max-w-40 rounded border border-zinc-300 text-xs dark:border-zinc-700 dark:bg-zinc-900">
                        {(scripts ?? []).map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.title}
                          </option>
                        ))}
                      </select>
                      <button className="rounded border border-zinc-300 px-1 text-xs dark:border-zinc-700">Relier</button>
                    </form>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
