import { describe, expect, it } from "vitest";
import { parseTranscriptionForm } from "./transcription";

function form(entries: Record<string, string>): FormData {
  const data = new FormData();
  for (const [k, v] of Object.entries(entries)) data.set(k, v);
  return data;
}

describe("parseTranscriptionForm", () => {
  it("ignore les lignes vides et normalise les champs", () => {
    const parsed = parseTranscriptionForm(
      form({
        rows: "3",
        text_0: "  Je suis Batman.  ",
        kind_0: "DIALOGUE",
        panel_0: "2",
        speaker_0: " Batman ",
        language_0: "fr",
        text_1: "   ",
        text_2: "BOUM",
        kind_2: "SFX",
        panel_2: "",
      }),
    );
    expect(parsed).toEqual([
      { text: "Je suis Batman.", kind: "DIALOGUE", panel_index: 2, speaker: "Batman", language: "fr" },
      { text: "BOUM", kind: "SFX", panel_index: null, speaker: null, language: null },
    ]);
  });

  it("refuse un type inconnu et une case invalide", () => {
    const [entry] = parseTranscriptionForm(form({ rows: "1", text_0: "x", kind_0: "HACK", panel_0: "-3" }));
    expect(entry).toMatchObject({ kind: "DIALOGUE", panel_index: null });
  });

  it("borne le nombre de lignes", () => {
    expect(parseTranscriptionForm(form({ rows: "abc", text_0: "x" }))).toEqual([]);
  });
});
