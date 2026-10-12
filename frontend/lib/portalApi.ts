/** A Média Portál PUBLIKUS (bejelentkezés nélküli) API kliense - a
 * Hype-repo-main (különálló client-portál projekt) lib/api.ts public
 * függvényeinek 1:1 portja, a HYPE OS backend /api/v1/public/portal
 * végpontjaira mutatva. Szándékosan KÜLÖN fájl a lib/api.ts-től: az utóbbi
 * cookie-ból/localStorage-ból olvasott Bearer tokennel hitelesít (HYPE OS
 * alkalmazottaknak), ez itt viszont sosem küld Authorization headert - a
 * valódi ügyfelek, akiknek a portál linket küldjük, nem HYPE OS
 * alkalmazottak. */

export interface PortalVideo {
  id: number;
  title: string;
  folder_id: number | null;
  mp4_url: string;
  hls_url: string;
  thumbnail_url: string;
  duration_seconds: number;
  width: number;
  height: number;
  resolution_label: string;
  aspect_ratio_label: string;
  size_bytes: number;
  status: string;
  sort_order: number;
  /** Csak belső ellenőrzésre - az ügyfél nem látja; a belsős néző rejtett-
   * jelöléssel igen (lásd backend portal_public._serialize). */
  rejtett?: boolean;
}

export interface PortalFolder {
  id: number;
  name: string;
  sort_order: number;
  /** Rejtett mappa - az ügyfél nem látja; a belsős néző jelöléssel igen. */
  rejtett?: boolean;
  /** Szülő mappa (null = főszint) - mappán belüli mappa. */
  parent_folder_id?: number | null;
}

export interface PortalImage {
  id: number;
  title: string;
  folder_id: number | null;
  url: string;
  thumbnail_url: string;
  /** Rejtett kép - az ügyfél nem látja (rejtett mappába a feltöltő linken
   * érkező kép automatikusan ezt kapja, csak admin veheti le). */
  rejtett?: boolean;
}

export interface PublicPortal {
  slug: string;
  title: string;
  client_name: string;
  description: string;
  cover_image_url: string;
  brand: string;
  project_date: string;
  expires_at: string | null;
  payment_mode: string;
  videos: PortalVideo[];
  folders: PortalFolder[];
  images: PortalImage[];
}

export type ExportAccess = { slug?: string; authorization?: string; belsos_token?: string; share?: string; part?: string };
let exportAccess: ExportAccess = {};
export function getExportAccess(): ExportAccess { return { ...exportAccess }; }

const BASE = `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/public/portal`;

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Sikertelen kérés (${res.status})`);
  }
  return res.json();
}

export async function getPublicProject(slug: string, token?: string, belsosToken?: string | null) {
  exportAccess = { slug, authorization: token, belsos_token: belsosToken || undefined };
  const reszek = [
    token ? `authorization=${encodeURIComponent(token)}` : null,
    // A BELSŐS (bejelentkezett, portál-jogú) néző HYPE OS tokenje: vele a
    // rejtett videók/mappák is jönnek, rejtett-jelöléssel.
    belsosToken ? `belsos_token=${encodeURIComponent(belsosToken)}` : null,
  ].filter(Boolean);
  const q = reszek.length > 0 ? `?${reszek.join("&")}` : "";
  return req<{
    locked: boolean;
    expired?: boolean;
    project?: PublicPortal;
    title?: string;
    cover_image_url?: string;
    brand?: string;
    contact_email?: string;
    payment_mode?: string;
  }>(`/${slug}${q}`);
}

export async function unlockProject(slug: string, password: string) {
  return req<{ token: string }>(`/${slug}/unlock`, {
    method: "POST",
    body: JSON.stringify({ password }),
  });
}

export async function getByShare(token: string) {
  exportAccess = { share: token };
  return req<{
    locked: boolean;
    expired?: boolean;
    project?: PublicPortal;
    title?: string;
    brand?: string;
    contact_email?: string;
    payment_mode?: string;
  }>(`/share/${token}`);
}

export async function getVideoDownloadUrl(videoId: number): Promise<string> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/public/portal-videos/${videoId}/download`);
  if (!res.ok) throw new Error(`Sikertelen kérés (${res.status})`);
  const data: { url: string } = await res.json();
  return data.url;
}

export async function getImageDownloadUrl(imageId: number): Promise<string> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/public/portal-images/${imageId}/download`);
  if (!res.ok) throw new Error(`Sikertelen kérés (${res.status})`);
  const data: { url: string } = await res.json();
  return data.url;
}

/** A fájl BACKENDEN átfolyatott letöltési URL-je - tartalék arra az esetre,
 * amikor a presigned R2 URL-t a böngésző nem tudja fetch()-elni, mert a
 * bucketen nincs CORS-szabály a portál originjére (lásd backend
 * routes/portal_public.py /file végpontjai és portalUtils.ts
 * fetchFileWithFallback). */
export function getVideoFileProxyUrl(videoId: number): string {
  return `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/public/portal-videos/${videoId}/file`;
}

export function getImageFileProxyUrl(imageId: number): string {
  return `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/public/portal-images/${imageId}/file`;
}

/** A vevő számlázási adatai - ezekből állítja ki a rendszer a számlát a
 * sikeres fizetés után (lásd backend services/portal_szamlazz.py). */
export type PortalBilling = {
  type: "individual" | "company";
  name: string;
  zip: string;
  city: string;
  address: string;
  /** Csak cégnél. */
  tax_number: string;
  email: string;
};

export async function startPayment(
  slug: string,
  packageCode: string,
  billing: PortalBilling,
): Promise<string> {
  const data = await req<{ gateway_url: string }>(`/${slug}/pay`, {
    method: "POST",
    body: JSON.stringify({ package: packageCode, billing }),
  });
  return data.gateway_url;
}

// ─── Feltöltő link és rész-megosztás (a felhasználó kérése) ────────────────

export type FeltoltesFajl = {
  tipus: "video" | "kep";
  id: number;
  title: string;
  folder_id: number | null;
  status: string;
  thumbnail_url: string | null;
  size_bytes: number;
  created_at: string | null;
};

export type FeltoltesAdatok = {
  title: string;
  brand: string;
  csak_mappa: boolean;
  folders: {
    id: number;
    name: string;
    /** A SAJÁT feltöltések száma ebben a mappában (a máséból semmi nem látszik). */
    video_db: number;
    kep_db: number;
    /** Rejtett (ágban lévő) mappa: ide minden feltöltés automatikusan rejtett
     * lesz, és ezt a feltöltő nem tudja felülbírálni (a szerver kényszeríti). */
    rejtett?: boolean;
    /** Ezt a mappát ez a böngésző hozta létre (törölhető). */
    sajat?: boolean;
  }[];
  /** A SAJÁT feltöltések (a felhasználó kérése: mindenki csak azt látja, amit
   * ő töltött fel, és abból törölhet). */
  fajlok: FeltoltesFajl[];
};

/** A feltöltő BÖNGÉSZŐ azonosítója (a felhasználó kérése: mindenki a saját
 * feltöltéseit lássa és törölhesse). Egyszer keletkezik, és a böngészőben
 * marad; a szerver csak a lenyomatát tárolja. Ha a tároló nem érhető el
 * (privát mód), az oldal életére szól. */
let memoriaKulcs: string | null = null;
export function feltoltoKulcs(): string {
  const TAROLO = "hype-feltolto-kulcs";
  try {
    const meglevo = window.localStorage.getItem(TAROLO);
    if (meglevo && /^[A-Za-z0-9_-]{16,128}$/.test(meglevo)) return meglevo;
  } catch {
    // privát mód / tiltott tároló - lent a memóriában tartjuk
  }
  if (!memoriaKulcs) {
    memoriaKulcs =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID().replaceAll("-", "")
        : Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
  }
  try {
    window.localStorage.setItem(TAROLO, memoriaKulcs);
  } catch {
    // marad a memóriában
  }
  return memoriaKulcs;
}

function feltoltoFejlec(): Record<string, string> {
  return { "X-Feltolto-Kulcs": feltoltoKulcs() };
}

export async function getFeltoltesAdatok(token: string) {
  return req<FeltoltesAdatok>(`/feltoltes/${token}`, { headers: feltoltoFejlec() });
}

export async function feltoltesMappa(token: string, name: string) {
  return req<{ id: number; name: string }>(`/feltoltes/${token}/mappa`, {
    method: "POST",
    body: JSON.stringify({ name }),
    headers: feltoltoFejlec(),
  });
}

/** Egy fájl feltöltése HALADÁSJELZÉSSEL és megszakíthatóan (a felhasználó
 * kérése: több feltöltés mehessen párhuzamosan, mappánként). */
export function feltoltesFajl(
  token: string,
  file: File,
  folderId: number | null,
  haladas?: (szazalek: number) => void,
): { kesz: Promise<{ ok: boolean; hiba?: string; megszakitva?: boolean }>; megszakit: () => void } {
  const xhr = new XMLHttpRequest();
  const kesz = new Promise<{ ok: boolean; hiba?: string; megszakitva?: boolean }>((resolve) => {
    const fd = new FormData();
    fd.append("file", file);
    if (folderId != null) fd.append("folder_id", String(folderId));
    const vegpont = file.type.startsWith("image/") ? "kep" : "video";
    xhr.open("POST", `${BASE}/feltoltes/${token}/${vegpont}`);
    for (const [k, v] of Object.entries(feltoltoFejlec())) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && haladas) haladas(Math.min(99, Math.round((e.loaded / e.total) * 100)));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        haladas?.(100);
        resolve({ ok: true });
        return;
      }
      let hiba = `Sikertelen feltöltés (${xhr.status})`;
      try {
        hiba = JSON.parse(xhr.responseText).detail || hiba;
      } catch {
        // nem JSON válasz
      }
      resolve({ ok: false, hiba });
    };
    xhr.onerror = () => resolve({ ok: false, hiba: "Hálózati hiba a feltöltés közben." });
    xhr.onabort = () => resolve({ ok: false, megszakitva: true, hiba: "Megszakítva." });
    xhr.send(fd);
  });
  return { kesz, megszakit: () => xhr.abort() };
}

/** A SAJÁT feltöltés (vagy saját mappa) törlése. */
export async function feltoltesTorles(token: string, mit: "video" | "kep" | "mappa", id: number) {
  const res = await fetch(`${BASE}/feltoltes/${token}/${mit}/${id}`, { method: "DELETE", headers: feltoltoFejlec() });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Sikertelen törlés (${res.status})`);
  }
}

export async function getMegosztas(token: string) {
  exportAccess = { part: token };
  return req<{ tipus: "mappa" | "video"; project: PublicPortal }>(`/megosztas/${token}`);
}

/** Mappa vagy videó megosztó linkjének kérése a PORTÁL-NÉZETBŐL (nem admin) -
 * jelszavas portálnál a feloldó token is megy, hogy a link-készítés ne
 * kerülje meg a jelszót. */
export async function mintReszletLink(
  slug: string,
  cel: { folderId?: number; videoId?: number },
  authToken?: string | null,
): Promise<string> {
  const valasz = await req<{ url: string }>(`/${slug}/reszlet-link`, {
    method: "POST",
    body: JSON.stringify({
      folder_id: cel.folderId ?? null,
      video_id: cel.videoId ?? null,
      authorization: authToken ?? null,
    }),
  });
  return valasz.url;
}
