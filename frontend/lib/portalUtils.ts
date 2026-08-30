import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import JSZip from "jszip";
import {
  getVideoDownloadUrl,
  getImageDownloadUrl,
  getVideoFileProxyUrl,
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

export async function downloadImagesAll(
  images: { id: number; title: string }[],
  onProgress?: (done: number, total: number) => void,
  signal?: AbortSignal,
) {
  if (isMobileDevice()) {
    let done = 0;
    for (const img of images) {
      if (signal?.aborted) return;
      await downloadImage(img.id, img.title);
      done++;
      if (onProgress) onProgress(done, images.length);
    }
    return;
  }

  const zip = new JSZip();
  const total = images.length;
  let done = 0;
  const CONCURRENCY = 5;
  let cursor = 0;

  async function worker() {
    while (cursor < images.length) {
      if (signal?.aborted) return;
      const i = cursor++;
      const img = images[i];
      try {
        const blob = await fetchBlobWithFallback(getImageDownloadUrl(img.id), getImageFileProxyUrl(img.id), signal);
        const ext = (blob.type.split("/")[1] || "jpg").split("+")[0];
        const safeTitle = (img.title || `image-${i + 1}`).replace(/[^\w.-]+/g, "_");
        zip.file(`${safeTitle}.${ext}`, blob, { compression: "STORE" });
      } catch {
        // egy hibás kép kimarad
      }
      done++;
      if (onProgress) onProgress(done, total);
    }
  }

  const workers = Array.from({ length: Math.min(CONCURRENCY, images.length) }, () => worker());
  await Promise.all(workers);
  if (signal?.aborted) return;

  const content = await zip.generateAsync({ type: "blob", compression: "STORE" });
  const blobUrl = URL.createObjectURL(content);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = "photos.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
}

async function finalizeZip(zip: JSZip, filename: string) {
  const content = await zip.generateAsync({ type: "blob", compression: "STORE" });
  const blobUrl = URL.createObjectURL(content);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
}

// EGY mappa (videók + fotók) egyetlen ZIP-be - a mappa-kártyán lévő "Mappa
// letöltése" gomb hívja.
export async function downloadFolderZip(
  folderName: string,
  videos: { id: number; title: string }[],
  images: { id: number; title: string }[],
  onProgress?: (done: number, total: number) => void,
  signal?: AbortSignal,
) {
  const total = videos.length + images.length;
  let done = 0;
  let added = 0;
  const safeFolder = (folderName || "mappa").replace(/[^\w.-]+/g, "_");

  const zip = new JSZip();

  const IMG_CONCURRENCY = 5;
  let imgCursor = 0;
  async function imgWorker() {
    while (imgCursor < images.length) {
      if (signal?.aborted) return;
      const i = imgCursor++;
      const img = images[i];
      try {
        const blob = await fetchBlobWithFallback(getImageDownloadUrl(img.id), getImageFileProxyUrl(img.id), signal);
        const ext = (blob.type.split("/")[1] || "jpg").split("+")[0];
        const safe = (img.title || `kep-${i + 1}`).replace(/[^\w.-]+/g, "_");
        zip.file(`${safe}.${ext}`, blob, { compression: "STORE" });
        added++;
      } catch (err) {
        console.error("[zip] kép kimaradt:", img.id, err);
      }
      done++;
      if (onProgress) onProgress(done, total);
    }
  }
  await Promise.all(Array.from({ length: Math.min(IMG_CONCURRENCY, images.length) }, () => imgWorker()));

  // Videók egyesével (nagyok - párhuzamosan elfogyna a memória).
  for (let i = 0; i < videos.length; i++) {
    if (signal?.aborted) return;
    const v = videos[i];
    try {
      const blob = await fetchBlobWithFallback(getVideoDownloadUrl(v.id), getVideoFileProxyUrl(v.id), signal);
      const safe = (v.title || `video-${i + 1}`).replace(/[^\w.-]+/g, "_");
      zip.file(`${safe}.mp4`, blob, { compression: "STORE" });
      added++;
    } catch (err) {
      console.error("[zip] videó kimaradt:", v.id, err);
    }
    done++;
    if (onProgress) onProgress(done, total);
  }

  if (signal?.aborted) return;
  if (added === 0) {
    alert("A letöltés nem sikerült (a fájlok nem elérhetők). Próbáld újra később.");
    return;
  }
  await finalizeZip(zip, `${safeFolder}.zip`);
}

// A TELJES projekt egy ZIP-be, a ZIP-en belül megtartva a mappaszerkezetet -
// a "folder" mező adja meg, melyik almappába kerüljön a fájl (null = gyökér).
export async function downloadEverythingZip(
  projectName: string,
  videos: { id: number; title: string; folder?: string | null }[],
  images: { id: number; title: string; folder?: string | null }[],
  onProgress?: (done: number, total: number) => void,
  signal?: AbortSignal,
) {
  const zip = new JSZip();
  const total = videos.length + images.length;
  let done = 0;
  let added = 0;

  const usedNames = new Set<string>();
  function uniquePath(folder: string | null | undefined, base: string, ext: string): string {
    const dir = folder ? `${folder.replace(/[^\w.-]+/g, "_")}/` : "";
    let name = `${dir}${base}.${ext}`;
    let n = 1;
    while (usedNames.has(name)) {
      name = `${dir}${base}-${n}.${ext}`;
      n++;
    }
    usedNames.add(name);
    return name;
  }

  const IMG_CONCURRENCY = 5;
  let imgCursor = 0;
  async function imgWorker() {
    while (imgCursor < images.length) {
      if (signal?.aborted) return;
      const i = imgCursor++;
      const img = images[i];
      try {
        const blob = await fetchBlobWithFallback(getImageDownloadUrl(img.id), getImageFileProxyUrl(img.id), signal);
        const ext = (blob.type.split("/")[1] || "jpg").split("+")[0];
        const base = (img.title || `kep-${i + 1}`).replace(/[^\w.-]+/g, "_");
        zip.file(uniquePath(img.folder, base, ext), blob, { compression: "STORE" });
        added++;
      } catch (err) {
        console.error("[zip] kép kimaradt:", img.id, err);
      }
      done++;
      if (onProgress) onProgress(done, total);
    }
  }
  await Promise.all(Array.from({ length: Math.min(IMG_CONCURRENCY, images.length) }, () => imgWorker()));

  for (let i = 0; i < videos.length; i++) {
    if (signal?.aborted) return;
    const v = videos[i];
    try {
      const blob = await fetchBlobWithFallback(getVideoDownloadUrl(v.id), getVideoFileProxyUrl(v.id), signal);
      const base = (v.title || `video-${i + 1}`).replace(/[^\w.-]+/g, "_");
      zip.file(uniquePath(v.folder, base, "mp4"), blob, { compression: "STORE" });
      added++;
    } catch (err) {
      console.error("[zip] videó kimaradt:", v.id, err);
    }
    done++;
    if (onProgress) onProgress(done, total);
  }

  if (signal?.aborted) return;
  if (added === 0) {
    alert("A letöltés nem sikerült (a fájlok nem elérhetők). Próbáld újra később.");
    return;
  }
  const safeProject = (projectName || "anyagok").replace(/[^\w.-]+/g, "_");
  await finalizeZip(zip, `${safeProject}.zip`);
}
