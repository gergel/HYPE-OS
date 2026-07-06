import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import JSZip from "jszip";
import { getVideoDownloadUrl, getImageDownloadUrl } from "@/lib/portalApi";

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

  const res = await fetch(url, { mode: "cors" });
  const blob = await res.blob();
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
) {
  if (isMobileDevice()) {
    let done = 0;
    for (const img of images) {
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
      const i = cursor++;
      const img = images[i];
      try {
        const url = await getImageDownloadUrl(img.id);
        const res = await fetch(url, { mode: "cors" });
        const blob = await res.blob();
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
