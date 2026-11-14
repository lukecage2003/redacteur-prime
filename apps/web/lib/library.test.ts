import { describe, expect, it } from "vitest";
import { DOCUMENT_STATUS_LABELS, boxStyle, fetchAnalysis, fetchDocuments, pageImageUrl, renderProgress } from "./library";

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


describe("boxStyle", () => {
  it("convertit une boîte normalisée en pourcentages bornés", () => {
    expect(boxStyle({ x: 0.1, y: 0.25, width: 0.5, height: 1.2 })).toEqual({
      left: "10.00%",
      top: "25.00%",
      width: "50.00%",
      height: "100.00%",
    });
  });
});

describe("analyse de page", () => {
  it("renvoie null si l'API répond 404", async () => {
    const fake = (async () => new Response("", { status: 404 })) as typeof fetch;
    expect(await fetchAnalysis("d", 1, fake, "http://api.test")).toBeNull();
  });

  it("encode l'identifiant dans l'URL de l'image", () => {
    expect(pageImageUrl("a/b", 2, "http://api.test")).toBe("http://api.test/api/v1/library/documents/a%2Fb/pages/2/image");
  });
});
