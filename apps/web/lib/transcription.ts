/** Saisie humaine d'une transcription (formulaire → corps de requête de l'API). */

export const TEXT_KINDS = ["DIALOGUE", "THOUGHT", "NARRATION", "SFX", "CAPTION", "OTHER"] as const;
export type TextKind = (typeof TEXT_KINDS)[number];

export interface HumanTextInput {
  text: string;
  kind: TextKind;
  panel_index: number | null;
  speaker: string | null;
  language: string | null;
}

const field = (form: FormData, name: string): string => {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
};

/** Lignes `text_i`, `kind_i`, `panel_i`, `speaker_i`, `language_i` ; les lignes vides sont ignorées. */
export function parseTranscriptionForm(form: FormData): HumanTextInput[] {
  const count = Number.parseInt(field(form, "rows"), 10) || 0;
  const texts: HumanTextInput[] = [];
  for (let i = 0; i < Math.min(count, 300); i++) {
    const text = field(form, `text_${i}`);
    if (!text) continue;
    const kind = field(form, `kind_${i}`) as TextKind;
    const panel = Number.parseInt(field(form, `panel_${i}`), 10);
    texts.push({
      text,
      kind: TEXT_KINDS.includes(kind) ? kind : "DIALOGUE",
      panel_index: Number.isInteger(panel) && panel >= 1 ? panel : null,
      speaker: field(form, `speaker_${i}`) || null,
      language: field(form, `language_${i}`) || null,
    });
  }
  return texts;
}
