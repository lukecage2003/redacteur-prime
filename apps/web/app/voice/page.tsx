import Link from "next/link";
import VoiceAssistant from "./VoiceAssistant";

export const dynamic = "force-dynamic";

export default function VoicePage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <Link href="/" className="text-sm text-amber-700 hover:underline">
        ← Accueil
      </Link>
      <h1 className="mt-2 text-2xl font-bold tracking-tight">Assistant vocal</h1>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Réponses tirées des pages transcrites, citées et vérifiées avant d&apos;être dites. Sans source, l&apos;assistant dit qu&apos;il ne sait pas.
      </p>
      <VoiceAssistant apiBase={process.env.NEXT_PUBLIC_API_BASE_URL ?? ""} />
    </main>
  );
}
