import Link from "next/link";
import { notFound } from "next/navigation";
import { boxStyle, fetchAnalysis, pageImageUrl } from "@/lib/library";

export const dynamic = "force-dynamic";

const KIND_LABELS = {
  DIALOGUE: "Dialogue",
  THOUGHT: "Pensée",
  NARRATION: "Narration",
  SFX: "Onomatopée",
  CAPTION: "Légende",
  OTHER: "Autre",
} as const;

export default async function PageView({
  params,
}: {
  params: Promise<{ documentId: string; number: string }>;
}) {
  const { documentId, number } = await params;
  const pageNumber = Number.parseInt(number, 10);
  if (!Number.isInteger(pageNumber) || pageNumber < 1) notFound();
  const analysis = await fetchAnalysis(
    documentId,
    pageNumber,
    fetch,
    process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL,
  );
  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <nav className="flex gap-4 text-sm">
        <Link href={`/library/${documentId}`} className="text-amber-700 hover:underline">
          ← Document
        </Link>
        {pageNumber > 1 && (
          <Link href={`/library/${documentId}/pages/${pageNumber - 1}`} className="hover:underline">
            Page précédente
          </Link>
        )}
        <Link href={`/library/${documentId}/pages/${pageNumber + 1}`} className="hover:underline">
          Page suivante
        </Link>
      </nav>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Page {pageNumber}</h1>
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="relative">
          {/* eslint-disable-next-line @next/next/no-img-element -- image servie par l'API */}
          <img
            src={pageImageUrl(documentId, pageNumber, process.env.NEXT_PUBLIC_API_BASE_URL)}
            alt={`Page ${pageNumber}`}
            className="w-full rounded border border-zinc-200 dark:border-zinc-800"
          />
          {analysis?.panels.map((panel) => (
            <div
              key={`p${panel.index}`}
              className="absolute border-2 border-amber-500/80"
              style={boxStyle(panel.bbox)}
            >
              <span className="absolute left-0 top-0 bg-amber-500 px-1 text-xs font-bold text-white">
                {panel.index}
              </span>
            </div>
          ))}
          {analysis?.texts.map((t) => (
            <div
              key={`t${t.order}`}
              className="absolute border border-sky-500/80 bg-sky-400/10"
              style={boxStyle(t.bbox)}
              title={t.text}
            />
          ))}
        </div>
        <section>
          {!analysis ? (
            <p className="text-sm text-zinc-500">
              Pas encore d&apos;analyse. Lancer : <code className="text-xs">primestone-vision analyze</code>.
            </p>
          ) : (
            <>
              <p className="text-xs text-zinc-500">
                {analysis.panels.length} case(s) · {analysis.texts.length} texte(s) · {analysis.provider} /{" "}
                {analysis.model} · {analysis.prompt_version} · {analysis.detector}
              </p>
              <ol className="mt-3 space-y-2 text-sm">
                {analysis.texts.map((t) => (
                  <li key={t.order} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                    <div className="text-xs text-zinc-500">
                      {KIND_LABELS[t.kind]} · case {t.panel_index ?? "—"}
                      {t.speaker ? ` · ${t.speaker} (${Math.round((t.speaker_confidence ?? 0) * 100)} %)` : ""}
                      {t.confidence < 0.8 ? " · ⚠ transcription incertaine" : ""}
                    </div>
                    <p className="mt-1">{t.text}</p>
                  </li>
                ))}
              </ol>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
