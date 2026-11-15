import Link from "next/link";
import { canDeclare, fetchChannelPerformance, fetchPlan } from "@/lib/distribution";

export const dynamic = "force-dynamic";

const api = () => process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

export default async function DistributionPage() {
  const [plan, channels] = await Promise.all([fetchPlan(api()), fetchChannelPerformance(api())]);
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Distribution</h1>
      <p className="mt-1 text-xs text-zinc-500">La plateforme ne publie jamais : tu publies, puis tu déclares (primestone-distribution declare).</p>
      <section className="mt-6">
        <h2 className="font-semibold">Plan de diffusion</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {(plan ?? []).map((i) => (
            <li key={i.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
              {i.title}{" "}
              <span className="text-xs text-zinc-500">
                · {i.status} · {i.channel} ({i.platform}, {i.language}){i.show ? ` · ${i.show}` : ""}
                {i.scheduled_for ? ` · prévu ${new Date(i.scheduled_for).toLocaleString("fr-FR")}` : ""}
              </span>
              {canDeclare(i) && <p className="text-xs text-amber-700">Approuvé : à publier puis déclarer.</p>}
              {i.published_url && (
                <p className="text-xs">
                  Publié (déclaré par {i.declared_by}) : <a href={i.published_url} className="text-amber-700 hover:underline" rel="noreferrer noopener" target="_blank">{i.published_url}</a>
                </p>
              )}
            </li>
          ))}
          {plan?.length === 0 && <li className="text-zinc-500">Plan vide : primestone-distribution propose CANAL &quot;titre&quot;</li>}
        </ul>
      </section>
      <section className="mt-8">
        <h2 className="font-semibold">Canaux</h2>
        <ul className="mt-2 space-y-1 text-sm">
          {(channels ?? []).map((c) => (
            <li key={c.channel_id}>
              {c.name} <span className="text-xs text-zinc-500">· {c.platform} · {c.language} · statistiques : {c.stats_authorization} · {Object.entries(c.performance).map(([k, v]) => `${k} ${v}`).join(", ")}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
