"use client";

import { useEffect, useRef, useState } from "react";
import { encodeWav, PERSONALITIES, toBase64, voiceSocketUrl } from "@/lib/voice";

type Line = { who: "vous" | "assistant" | "système"; text: string };

export default function VoiceAssistant({ apiBase }: { apiBase: string }) {
  const socket = useRef<WebSocket | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const queue = useRef<string[]>([]);
  const recorder = useRef<{ ctx: AudioContext; stream: MediaStream; chunks: Float32Array[] } | null>(null);
  const [personality, setPersonality] = useState("research");
  const [lines, setLines] = useState<Line[]>([]);
  const [ready, setReady] = useState(false);
  const [recording, setRecording] = useState(false);
  const add = (line: Line) => setLines((l) => [...l, line]);

  const playNext = () => {
    const next = queue.current.shift();
    if (!next || !audio.current) return;
    audio.current.src = `data:audio/wav;base64,${next}`;
    void audio.current.play().catch(() => undefined);
  };

  const stopSpeech = () => {
    queue.current = [];
    audio.current?.pause();
    socket.current?.send(JSON.stringify({ type: "interrupt" }));
  };

  useEffect(() => {
    const ws = new WebSocket(voiceSocketUrl(apiBase, window.location));
    socket.current = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: "start", personality, language: "fr" }));
    ws.onmessage = (event) => {
      const msg = JSON.parse(String(event.data));
      if (msg.type === "ready") setReady(true);
      else if (msg.type === "transcript") add({ who: "vous", text: msg.text });
      else if (msg.type === "answer") add({ who: "assistant", text: `${msg.text}  (${msg.fact_check.verdict})` });
      else if (msg.type === "sentence" && msg.audio) {
        queue.current.push(msg.audio);
        if (audio.current?.paused) playNext();
      } else if (msg.type === "error") add({ who: "système", text: msg.detail });
    };
    ws.onclose = () => setReady(false);
    return () => ws.close();
  }, [apiBase, personality]);

  const ask = (form: FormData) => {
    const text = String(form.get("text") ?? "").trim();
    if (!text || !socket.current) return;
    stopSpeech();
    add({ who: "vous", text });
    socket.current.send(JSON.stringify({ type: "text", text }));
  };

  const startRecording = async () => {
    stopSpeech(); // parler coupe la réponse en cours
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    const chunks: Float32Array[] = [];
    processor.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    source.connect(processor);
    processor.connect(ctx.destination);
    recorder.current = { ctx, stream, chunks };
    setRecording(true);
  };

  const stopRecording = async () => {
    const rec = recorder.current;
    if (!rec) return;
    rec.stream.getTracks().forEach((t) => t.stop());
    const total = rec.chunks.reduce((n, c) => n + c.length, 0);
    const samples = new Float32Array(total);
    let offset = 0;
    for (const c of rec.chunks) {
      samples.set(c, offset);
      offset += c.length;
    }
    const wav = encodeWav(samples, rec.ctx.sampleRate);
    await rec.ctx.close();
    recorder.current = null;
    setRecording(false);
    socket.current?.send(JSON.stringify({ type: "audio", wav: toBase64(wav) }));
  };

  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="personality">Personnalité</label>
        <select id="personality" value={personality} onChange={(e) => setPersonality(e.target.value)} className="rounded border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900">
          {PERSONALITIES.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
            </option>
          ))}
        </select>
        <span className={ready ? "text-emerald-700" : "text-zinc-500"}>{ready ? "connecté" : "connexion…"}</span>
      </div>
      <ol className="min-h-40 space-y-2 rounded border border-zinc-200 p-3 text-sm dark:border-zinc-800">
        {lines.map((l, i) => (
          <li key={i}>
            <strong>{l.who} :</strong> {l.text}
          </li>
        ))}
      </ol>
      <form action={ask} className="flex gap-2">
        <input name="text" placeholder="Posez une question (mode texte)" className="w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <button className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white">Envoyer</button>
      </form>
      <div className="flex gap-2">
        <button
          type="button"
          onPointerDown={() => void startRecording()}
          onPointerUp={() => void stopRecording()}
          className={`rounded px-3 py-1.5 text-sm font-medium ${recording ? "bg-red-600 text-white" : "border border-amber-600 text-amber-700"}`}
        >
          {recording ? "Relâchez pour envoyer" : "Maintenir pour parler"}
        </button>
        <button type="button" onClick={stopSpeech} className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700">
          Interrompre
        </button>
      </div>
      <audio ref={audio} onEnded={playNext} hidden />
    </div>
  );
}
