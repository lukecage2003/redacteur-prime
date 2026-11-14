import Link from "next/link";
import { STATUS_LABELS, modulesByPhase } from "@/lib/modules";

export default function Home() {
  const modules = modulesByPhase();
  return (
    <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <header className="mb-8">
        <p className="text-sm font-medium uppercase tracking-widest text-amber-600">Primestone</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Editorial 2.0</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Intelligence éditoriale pour les comics : analyse documentaire, connaissances prouvées,
          storytelling bilingue.
        </p>
        <Link href="/library" className="mt-4 inline-block text-sm font-medium text-amber-700 hover:underline">
          Ouvrir la bibliothèque →
        </Link>
        <Link href="/knowledge" className="ml-4 mt-4 inline-block text-sm font-medium text-amber-700 hover:underline">
          Connaissances →
        </Link>
        <Link href="/editorial" className="ml-4 mt-4 inline-block text-sm font-medium text-amber-700 hover:underline">
          Rédaction →
        </Link>
        <Link href="/lab" className="ml-4 mt-4 inline-block text-sm font-medium text-amber-700 hover:underline">
          Laboratoire →
        </Link>
        <Link href="/market" className="ml-4 mt-4 inline-block text-sm font-medium text-amber-700 hover:underline">
          Marché →
        </Link>
        <Link href="/scripts" className="ml-4 mt-4 inline-block text-sm font-medium text-amber-700 hover:underline">
          Scripts →
        </Link>
      </header>
      <ul className="grid gap-3 sm:grid-cols-2">
        {modules.map((m) => (
          <li
            key={m.id}
            className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="flex items-baseline justify-between gap-2">
              <h2 className="font-semibold">{m.name}</h2>
              <span className="shrink-0 text-xs text-zinc-500">Phase {m.phase}</span>
            </div>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{m.summary}</p>
            <p className="mt-2 text-xs font-medium text-zinc-500">{STATUS_LABELS[m.status]}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
