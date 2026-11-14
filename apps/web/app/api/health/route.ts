// Sonde de vivacité Cloud Run pour le service web.
export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({ status: "ok" });
}
