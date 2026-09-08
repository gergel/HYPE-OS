import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { getExportAccess } from "@/lib/portalApi";
import {
  getVideoDownloadUrl,
  getImageDownloadUrl,
  getImageFileProxyUrl,
} from "@/lib/portalApi";

/** Egy fájl letöltése blobként, KÉT lépcsőben: először a presigned R2 URL-ről
 * közvetlenül (gyors, nem terheli a backendet), és ha az elbukik - tipikusan
 * azért, mert a bucketen nincs CORS-szabály a portál originjére, ilyenkor a
 * böngésző fetch()-e azonnal hibát dob -, akkor a backend /file
 * proxy-végpontjáról (lásd portalApi.getVideoFileProxyUrl), ami a backend
 * saját CORS-beállításán át mindig elérhető. Enélkül a tömeges/ZIP letöltés
 * "a fájlok nem elérhetők" hibával halt el mindenkinél, amíg a bucket CORS be
 * nem volt állítva. A felhasználói megszakítást (AbortError) továbbdobjuk,
 * arra nem tartalék kell, hanem leállás. */
async function fetchBlobWithFallback(
  directUrl: Promise<string>,
  proxyUrl: string,
  signal?: AbortSignal,
): Promise<Blob> {
  try {
    const url = await directUrl;
    const res = await fetch(url, { mode: "cors", signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.blob();
  } catch (err) {
    if (signal?.aborted) throw err;
    const res = await fetch(proxyUrl, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.blob();
  }
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(seconds: number): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n < 10 ? 1 : 0)} ${units[i]}`;
}

function isMobileDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  const isTouchMobile = /Android|iPhone|iPad|iPod/i.test(ua);
  const nav = navigator as Navigator & { canShare?: (data: { files: File[] }) => boolean };
  return isTouchMobile && typeof nav.canShare === "function";
}

const SHARE_LIMIT = 100 * 1024 * 1024; // iOS Web Share kb. 100 MB-os fájlkorlát (galériába mentés)

// Letöltés: mobilon 100 MB alatt megosztás (galériába), felette natív letöltő.
// Gépen mindig a böngésző natív letöltője (streamel, nincs blob-várakozás).
export async function downloadVideo(videoId: number, mp4Url: string, filename: string, sizeBytes: number) {
  const nav = navigator as Navigator & {
    canShare?: (data: { files: File[] }) => boolean;
    share?: (data: { files?: File[]; title?: string }) => Promise<void>;
  };

  if (isMobileDevice() && nav.share) {
    try {
      const dlUrl = await getVideoDownloadUrl(videoId);
      let size = sizeBytes;
      if (!size || size <= 0) {
        try {
          const head = await fetch(dlUrl, { method: "HEAD", mode: "cors" });
          const len = head.headers.get("content-length");
          size = len ? parseInt(len, 10) : 0;
        } catch {
          size = 0;
        }
      }
      const knownSmall = size > 0 && size < SHARE_LIMIT;
      if (!knownSmall) {
        window.location.href = dlUrl;
        return;
      }
      const res = await fetch(dlUrl, { mode: "cors" });
      const blob = await res.blob();
      const file = new File([blob], filename, { type: blob.type || "video/mp4" });
      if (nav.canShare && nav.canShare({ files: [file] })) {
        await nav.share({ files: [file], title: filename });
        return;
      }
      window.location.href = dlUrl;
      return;
    } catch (err) {
      const e = err as { name?: string };
      if (e && e.name === "AbortError") return;
      try {
        const url = await getVideoDownloadUrl(videoId);
        window.location.href = url;
        return;
      } catch {
        window.open(mp4Url, "_blank");
        return;
      }
    }
  }

  try {
    const dlUrl = await getVideoDownloadUrl(videoId);
    const a = document.createElement("a");
    a.href = dlUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch {
    window.open(mp4Url, "_blank");
  }
}

export async function downloadImage(imageId: number, title?: string) {
  const url = await getImageDownloadUrl(imageId);

  if (!isMobileDevice()) {
    const a = document.createElement("a");
    a.href = url;
    a.download = title || "image";
    document.body.appendChild(a);
    a.click();
    a.remove();
    return;
  }

  const blob = await fetchBlobWithFallback(Promise.resolve(url), getImageFileProxyUrl(imageId));
  const ext = (blob.type.split("/")[1] || "jpg").split("+")[0];
  const filename = `${title || "image"}.${ext}`;
  const file = new File([blob], filename, { type: blob.type || "image/jpeg" });
  const nav = navigator as Navigator & {
    canShare?: (data: { files: File[] }) => boolean;
    share?: (data: { files: File[] }) => Promise<void>;
  };
  if (nav.canShare && nav.canShare({ files: [file] }) && nav.share) {
    try {
      await nav.share({ files: [file] });
      return;
    } catch {
      return;
    }
  }

  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
}

type ExportItem = { id: number; title: string; folder?: string | null };
type ExportJob = { id: string; state: string; bytes_done: number; total_bytes: number; error?: string; url?: string };

async function backgroundZip(filename: string, videos: ExportItem[], images: ExportItem[],
  onProgress?: (done: number, total: number) => void, signal?: AbortSignal) {
  const base = `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/public/portal-exports`;
  const access = getExportAccess();
  async function post(path: string, body: unknown): Promise<ExportJob> {
    const res = await fetch(base + path, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), signal });
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "A csomag nem készíthető el.");
    return data;
  }
  try {
    const created = await post("", { access, filename, videos, images });
    while (!signal?.aborted) {
      const job = await post(`/${created.id}/status`, access);
      onProgress?.(job.bytes_done, job.total_bytes || 1);
      if (job.state === "ready" && job.url) {
        // Native download streams directly from R2 to disk, never through a Blob.
        const a = document.createElement("a");
        a.href = job.url; a.download = `${filename}.zip`;
        document.body.appendChild(a); a.click(); a.remove();
        return;
      }
      if (job.state === "failed") throw new Error(job.error || "A csomag nem készült el.");
      if (job.state === "expired") throw new Error("A csomag lejárt. Kattints újra az elkészítéshez.");
      await new Promise<void>((resolve) => setTimeout(resolve, 2500));
    }
  } catch (err) {
    if (!signal?.aborted) alert(err instanceof Error ? err.message : "A letöltés nem sikerült.");
  }
}

export async function downloadImagesAll(images: ExportItem[], onProgress?: (done: number, total: number) => void, signal?: AbortSignal) {
  return backgroundZip("Fotók", [], images, onProgress, signal);
}

export async function downloadFolderZip(folderName: string, videos: ExportItem[], images: ExportItem[],
  onProgress?: (done: number, total: number) => void, signal?: AbortSignal) {
  return backgroundZip(folderName, videos, images, onProgress, signal);
}

export async function downloadEverythingZip(projectName: string, videos: ExportItem[], images: ExportItem[],
  onProgress?: (done: number, total: number) => void, signal?: AbortSignal) {
  return backgroundZip(projectName, videos, images, onProgress, signal);
}
