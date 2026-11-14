import Link from "next/link";
import { notFound } from "next/navigation";
import { boxStyle, fetchAnalysis, fetchPanels, pageImageUrl } from "@/lib/library";
import { TEXT_KINDS } from "@/lib/transcription";
import { saveTranscription } from "./actions";

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
  searchParams,
}: {
  params: Promise<{ documentId: string; number: string }>;
  searchParams: Promise<{ saved?: string }>;
}) {
  const { documentId, number } = await params;
  const { saved } = await searchParams;
  const pageNumber = Number.parseInt(number, 10);
  if (!Number.isInteger(pageNumber) || pageNumber < 1) notFound();
  const api = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
  const analysis = await fetchAnalysis(documentId, pageNumber, fetch, api);
  // Sans analyse : cases détectées à la volée (gratuit) pour pouvoir transcrire case par case.
  const panels = analysis?.panels ?? (await fetchPanels(documentId, pageNumber, fetch, api)) ?? [];
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
          {panels.map((panel) => (
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
          <TranscriptionForm
            documentId={documentId}
            page={pageNumber}
            saved={saved === "1"}
            panels={panels.map((p) => p.index)}
            texts={analysis?.texts ?? []}
          />
        </section>
      </div>
    </main>
  );
}

const BLANK_ROWS = 3;

function TranscriptionForm({
  documentId,
  page,
  saved,
  panels,
  texts,
}: {
  documentId: string;
  page: number;
  saved: boolean;
  panels: number[];
  texts: { text: string; kind: string; panel_index: number | null; speaker: string | null; language: string | null }[];
}) {
  const rows = [...texts, ...Array.from({ length: BLANK_ROWS }, () => null)];
  const input = "w-full rounded border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";
  return (
    <details className="mt-6 rounded border border-zinc-200 p-3 dark:border-zinc-800" open={texts.length === 0}>
      <summary className="cursor-pointer text-sm font-medium">
        Transcrire / corriger (gratuit — une correction humaine fait foi)
      </summary>
      {saved && <p className="mt-2 text-xs text-emerald-700">Transcription enregistrée (nouvelle version).</p>}
      <form action={saveTranscription.bind(null, documentId, page)} className="mt-3 space-y-3">
        <input type="hidden" name="rows" value={rows.length} />
        {rows.map((row, i) => (
          <fieldset key={i} className="grid grid-cols-6 gap-2">
            <textarea
              name={`text_${i}`}
              defaultValue={row?.text ?? ""}
              placeholder="Texte exact, tel que lettré"
              rows={2}
              className={`${input} col-span-6`}
            />
            <select name={`kind_${i}`} defaultValue={row?.kind ?? "DIALOGUE"} className={`${input} col-span-2`}>
              {TEXT_KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
            <select name={`panel_${i}`} defaultValue={row?.panel_index ?? ""} className={`${input} col-span-1`}>
              <option value="">hors case</option>
              {panels.map((p) => (
                <option key={p} value={p}>
                  case {p}
                </option>
              ))}
            </select>
            <input name={`speaker_${i}`} defaultValue={row?.speaker ?? ""} placeholder="Locuteur" className={`${input} col-span-2`} />
            <input name={`language_${i}`} defaultValue={row?.language ?? ""} placeholder="fr" className={`${input} col-span-1`} />
          </fieldset>
        ))}
        <button type="submit" className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">
          Enregistrer la transcription
        </button>
      </form>
    </details>
  );
}
