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
}

export interface PortalFolder {
  id: number;
  name: string;
  sort_order: number;
}

export interface PortalImage {
  id: number;
  title: string;
  folder_id: number | null;
  url: string;
  thumbnail_url: string;
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

export async function getPublicProject(slug: string, token?: string) {
  const q = token ? `?authorization=${encodeURIComponent(token)}` : "";
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
