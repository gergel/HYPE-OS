/** A KIKÜLDHETŐ portál-link összeállítása.
 *
 * A publikus portál (/p/{slug}) saját, ügyfeleknek szóló domainen fut
 * (hypeclient.com), miközben a HYPE OS admin felület a saját, eddigi domainjén
 * marad. Emiatt egy portál-linket NEM lehet a böngésző aktuális origin-jéből
 * összerakni: az admin gépén az az admin domain volna, és pont azt a linket
 * küldenénk ki az ügyfélnek, amit nem szabad.
 *
 * NEXT_PUBLIC_PORTAL_BASE_URL nélkül a régi viselkedés marad (az aktuális
 * origin) - így egy egydomaines telepítés és a fejlesztői környezet
 * változtatás nélkül működik. */
export function portalBaseUrl(): string {
  const beallitott = process.env.NEXT_PUBLIC_PORTAL_BASE_URL?.trim();
  if (beallitott) return beallitott.replace(/\/+$/, "");
  // Szerveren (SSR) nincs origin - ilyenkor relatív linket adunk vissza, ami
  // href-ként jó, és a kliensen úgyis felülíródik.
  return typeof window === "undefined" ? "" : window.location.origin;
}

/** Egy portál teljes, kiküldhető URL-je - megosztó tokennel, ha van. */
export function portalUrl(slug: string, shareToken?: string | null): string {
  const query = shareToken ? `?share=${encodeURIComponent(shareToken)}` : "";
  return `${portalBaseUrl()}/p/${slug}${query}`;
}
