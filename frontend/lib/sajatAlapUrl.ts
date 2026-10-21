import { headers } from "next/headers";

/** Az OLDAL SAJÁT abszolút alap-URL-je a kérés fejléceiből - az og:image-hez
 * abszolút cím kell (a Messenger/Facebook robotja relatívot nem tölt be), és
 * nincs külön env a frontend címére. Csak szerver-komponensből hívható. */
export async function sajatAlapUrl(): Promise<string> {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  return `${proto}://${host}`;
}
