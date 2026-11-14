/** Validation stricte des identifiants reçus du client avant tout appel serveur à l'API. */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: string): boolean {
  return UUID.test(value);
}

export function requireUuid(value: string): string {
  if (!isUuid(value)) throw new Error("identifiant de document invalide");
  return value.toLowerCase();
}

export function requirePageNumber(value: number): number {
  if (!Number.isInteger(value) || value < 1 || value > 100_000) throw new Error("numéro de page invalide");
  return value;
}
