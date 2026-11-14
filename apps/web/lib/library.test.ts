import { describe, expect, it } from "vitest";
import { DOCUMENT_STATUS_LABELS, fetchDocuments, renderProgress } from "./library";

describe("renderProgress", () => {
  it("calcule un pourcentage borné", () => {
    expect(renderProgress({ page_count: 20, pages_rendered: 5 })).toBe(25);
    expect(renderProgress({ page_count: 3, pages_rendered: 3 })).toBe(100);
    expect(renderProgress({ page_count: null, pages_rendered: 0 })).toBe(0);
  });
});

describe("fetchDocuments", () => {
  it("renvoie les documents", async () => {
    const fake = (async () => new Response(JSON.stringify([{ id: "1" }]), { status: 200 })) as typeof fetch;
    const result = await fetchDocuments(fake, "http://api.test");
    expect(result).toEqual({ ok: true, documents: [{ id: "1" }] });
  });

  it("signale une erreur HTTP", async () => {
    const fake = (async () => new Response("", { status: 503 })) as typeof fetch;
    expect(await fetchDocuments(fake, "http://api.test")).toEqual({ ok: false, error: "API indisponible (HTTP 503)" });
  });

  it("signale une API injoignable", async () => {
    const fake = (async () => {
      throw new TypeError("network");
    }) as typeof fetch;
    expect(await fetchDocuments(fake, "http://api.test")).toEqual({ ok: false, error: "API injoignable" });
  });
});

it("a un libellé pour chaque statut", () => {
  expect(Object.keys(DOCUMENT_STATUS_LABELS)).toHaveLength(6);
});
