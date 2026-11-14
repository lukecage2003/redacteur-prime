import { describe, expect, it } from "vitest";
import { MODULES, STATUS_LABELS, apiUrl, modulesByPhase } from "./modules";

describe("modules", () => {
  it("couvre les intelligences avec des identifiants uniques", () => {
    const ids = MODULES.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toEqual(expect.arrayContaining(["comic", "forensic", "knowledge", "voice"]));
  });

  it("trie par phase", () => {
    const phases = modulesByPhase().map((m) => m.phase);
    expect(phases).toEqual([...phases].sort((a, b) => a - b));
  });

  it("a un libellé pour chaque statut", () => {
    for (const m of MODULES) expect(STATUS_LABELS[m.status]).toBeTruthy();
  });

  it("ne déclare rien comme validé sans preuve", () => {
    expect(MODULES.filter((m) => m.status === "VALIDATED")).toEqual([]);
  });
});

describe("apiUrl", () => {
  it("construit une URL versionnée", () => {
    expect(apiUrl("health", "https://api.example.test/")).toBe("https://api.example.test/api/v1/health");
  });

  it("gère les barres obliques", () => {
    expect(apiUrl("/health/ready", "http://localhost:8000")).toBe("http://localhost:8000/api/v1/health/ready");
  });

  it("accepte une base relative vide", () => {
    expect(apiUrl("health", "")).toBe("/api/v1/health");
  });
});
