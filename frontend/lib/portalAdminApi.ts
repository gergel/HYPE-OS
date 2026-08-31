/** Média Portál admin API kliens - a Hype-repo-main (különálló client-portál
 * projekt) lib/api.ts admin függvényeinek 1:1 portja, a HYPE OS
 * bejelentkezést használó authFetch-csel (nincs külön admin login/token),
 * és a portal_admin.py végpontjaira mutatva. Int id-kat használ (nem UUID
 * stringet, mint az eredeti), mert egy Portal a HYPE OS saját (int PK-s)
 * Project-jéhez van kötve. */
"use client";

import { authFetch, getToken } from "@/lib/authFetch";
import type { PortalDetailData, PortalFolderItem, PortalImageItem, PortalSummary, PortalVideoItem } from "@/lib/api";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Sikertelen kérés (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function listPortals(): Promise<PortalSummary[]> {
  return req<PortalSummary[]>("/api/v1/portal-admin");
}

export async function createPortal(projectId: number, password?: string): Promise<PortalSummary> {
  return req<PortalSummary>("/api/v1/portal-admin", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, password: password || undefined }),
  });
}

export async function createManualPortal(
  title: string,
  clientName?: string,
  projectDate?: string,
  password?: string,
): Promise<PortalSummary> {
  return req<PortalSummary>("/api/v1/portal-admin", {
    method: "POST",
    body: JSON.stringify({
      title,
      client_name: clientName || undefined,
      project_date: projectDate || undefined,
      password: password || undefined,
    }),
  });
}

export async function createPortalFromDeliverable(
  deliverableId: number,
  opts?: {
    password?: string;
    /** A forgatás dátuma "ÉÉÉÉ.HH.NN" formában - csak akkor kell, ha az
     * utómunkához nincs forgatás kötve (a backend olyankor e nélkül 400-zal
     * utasítja el a létrehozást). */
    forgatasDatum?: string;
  }
): Promise<PortalSummary> {
  return req<PortalSummary>(`/api/v1/portal-admin/from-deliverable/${deliverableId}`, {
    method: "POST",
    body: JSON.stringify({
      password: opts?.password || undefined,
      forgatas_datum: opts?.forgatasDatum || undefined,
    }),
  });
}

export async function deletePortal(id: number): Promise<void> {
  return req(`/api/v1/portal-admin/${id}`, { method: "DELETE" });
}

export async function getPortalDetail(id: number): Promise<PortalDetailData> {
  return req<PortalDetailData>(`/api/v1/portal-admin/${id}`);
}

export async function updatePortal(id: number, data: Record<string, unknown>): Promise<PortalSummary> {
  return req<PortalSummary>(`/api/v1/portal-admin/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function regenShare(id: number): Promise<{ url: string; token: string }> {
  return req(`/api/v1/portal-admin/${id}/share`, { method: "POST" });
}

export async function reorderVideos(portalId: number, orderedIds: number[]): Promise<void> {
  return req(`/api/v1/portal-admin/${portalId}/videos/reorder`, {
    method: "POST",
    body: JSON.stringify({ ordered_ids: orderedIds }),
  });
}

export async function createFolder(portalId: number, name: string): Promise<PortalFolderItem> {
  return req<PortalFolderItem>(`/api/v1/portal-admin/${portalId}/folders`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function updateFolder(folderId: number, data: Record<string, unknown>): Promise<PortalFolderItem> {
  return req<PortalFolderItem>(`/api/v1/portal-admin/folders/${folderId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteFolder(folderId: number): Promise<void> {
  return req(`/api/v1/portal-admin/folders/${folderId}`, { method: "DELETE" });
}

export async function uploadImage(
  portalId: number,
  file: File,
  folderId?: number | null,
  signal?: AbortSignal,
): Promise<PortalImageItem> {
  const fd = new FormData();
  fd.append("file", file);
  if (folderId) fd.append("folder_id", String(folderId));
  const res = await authFetch(`/api/v1/portal-admin/${portalId}/images`, { method: "POST", body: fd, signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Kép feltöltése sikertelen (${res.status})`);
  }
  return res.json();
}

export async function deleteImage(imageId: number): Promise<void> {
  return req(`/api/v1/portal-admin/images/${imageId}`, { method: "DELETE" });
}

export async function setImageFolder(imageId: number, folderId: number | null): Promise<void> {
  return req(`/api/v1/portal-admin/images/${imageId}`, {
    method: "PATCH",
    body: JSON.stringify({ folder_id: folderId, set_folder: true }),
  });
}

export async function renameVideo(videoId: number, title: string): Promise<PortalVideoItem> {
  return req<PortalVideoItem>(`/api/v1/portal-admin/videos/${videoId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function setVideoFolder(videoId: number, folderId: number | null): Promise<void> {
  return req(`/api/v1/portal-admin/videos/${videoId}`, {
    method: "PATCH",
    body: JSON.stringify({ folder_id: folderId }),
  });
}

export async function uploadCover(portalId: number, file: File): Promise<{ cover_image_url: string }> {
  const fd = new FormData();
  fd.append("file", file);
  return req(`/api/v1/portal-admin/${portalId}/cover`, { method: "POST", body: fd });
}

export async function deleteCover(portalId: number): Promise<{ cover_image_url: string }> {
  return req(`/api/v1/portal-admin/${portalId}/cover`, { method: "DELETE" });
}

export async function replaceVideo(videoId: number, file: File): Promise<PortalVideoItem> {
  const fd = new FormData();
  fd.append("file", file);
  return req<PortalVideoItem>(`/api/v1/portal-admin/videos/${videoId}/replace`, { method: "POST", body: fd });
}

export async function deleteVideo(videoId: number): Promise<void> {
  return req(`/api/v1/portal-admin/videos/${videoId}`, { method: "DELETE" });
}

export async function videoDownloadUrl(videoId: number): Promise<string> {
  const data = await req<{ url: string }>(`/api/v1/portal-admin/videos/${videoId}/download-url`);
  return data.url;
}

export type PendingDeletionPortal = {
  id: number;
  title: string;
  client_name: string;
  expires_at: string;
  video_count: number;
  image_count: number;
};

export async function getPendingDeletion(): Promise<PendingDeletionPortal[]> {
  return req<PendingDeletionPortal[]>("/api/v1/portal-admin/maintenance/pending-deletion");
}

export async function purgePortalFiles(portalId: number): Promise<void> {
  return req(`/api/v1/portal-admin/maintenance/${portalId}/purge-files`, { method: "POST" });
}

export async function syncNotion(): Promise<{ synced?: number; created?: number; skipped?: number; error?: string }> {
  return req("/api/v1/portal-admin/notion/sync", { method: "POST" });
}

// ---- Multipart videó feltöltés (közvetlenül R2-be, valós haladásjelzéssel) ----

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders(): Record<string, string> {
  // Ugyanabból a cookie-ból, mint minden más kliens-oldali hívás - a gördülő
  // munkamenet megújíthatja a tokent, a localStorage-ban pedig a régi maradna.
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function uploadPart(url: string, blob: Blob, onPartProgress?: (loaded: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onPartProgress) onPartProgress(e.loaded);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const etag = xhr.getResponseHeader("ETag");
        if (!etag) {
          reject(new Error("Hiányzó ETag - ellenőrizd az R2 CORS ExposeHeaders beállítást"));
          return;
        }
        resolve(etag);
      } else {
        reject(new Error(`Darab feltöltése sikertelen (${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error("Darab feltöltése sikertelen"));
    xhr.send(blob);
  });
}

export async function uploadVideo(
  portalId: number,
  file: File,
  title: string,
  onProgress?: (percent: number) => void,
): Promise<PortalVideoItem> {
  const PART_SIZE = 100 * 1024 * 1024;
  const headers = { "Content-Type": "application/json", ...authHeaders() };

  const initRes = await fetch(`${API_BASE_URL}/api/v1/portal-admin/${portalId}/videos/multipart/init`, {
    method: "POST",
    headers,
    body: JSON.stringify({ filename: file.name, content_type: file.type || "video/mp4", title }),
  });
  if (!initRes.ok) throw new Error("Feltöltés indítása sikertelen");
  const { video_id, upload_id, key } = await initRes.json();

  try {
    const totalParts = Math.ceil(file.size / PART_SIZE);
    const parts: { PartNumber: number; ETag: string }[] = [];
    let uploadedBytes = 0;

    for (let partNumber = 1; partNumber <= totalParts; partNumber++) {
      const start = (partNumber - 1) * PART_SIZE;
      const end = Math.min(start + PART_SIZE, file.size);
      const blob = file.slice(start, end);

      const signRes = await fetch(`${API_BASE_URL}/api/v1/portal-admin/videos/multipart/sign-part`, {
        method: "POST",
        headers,
        body: JSON.stringify({ upload_id, key, part_number: partNumber }),
      });
      if (!signRes.ok) throw new Error("Darab aláírása sikertelen");
      const { url } = await signRes.json();

      const etag = await uploadPart(url, blob, (partLoaded) => {
        if (onProgress) {
          const pct = Math.round(((uploadedBytes + partLoaded) / file.size) * 100);
          onProgress(Math.min(pct, 99));
        }
      });
      uploadedBytes += blob.size;
      parts.push({ PartNumber: partNumber, ETag: etag });
    }

    const completeRes = await fetch(`${API_BASE_URL}/api/v1/portal-admin/videos/multipart/complete`, {
      method: "POST",
      headers,
      body: JSON.stringify({ upload_id, key, video_id, parts }),
    });
    if (!completeRes.ok) throw new Error("Feltöltés lezárása sikertelen");
    if (onProgress) onProgress(100);
    return completeRes.json();
  } catch (err) {
    await fetch(`${API_BASE_URL}/api/v1/portal-admin/videos/multipart/abort`, {
      method: "POST",
      headers,
      body: JSON.stringify({ upload_id, key, video_id }),
    }).catch(() => {});
    throw err;
  }
}

// ─── Feltöltő link és rész-megosztás (a felhasználó kérése) ────────────────

export async function createFeltoltoLink(portalId: number, folderId: number | null): Promise<{ url: string }> {
  return req<{ url: string; token: string }>(`/api/v1/portal-admin/${portalId}/feltolto-link`, {
    method: "POST",
    body: JSON.stringify({ folder_id: folderId }),
  });
}

export async function createFolderShareLink(folderId: number): Promise<{ url: string }> {
  return req<{ url: string; token: string }>(`/api/v1/portal-admin/folders/${folderId}/share-link`, {
    method: "POST",
  });
}

export async function createVideoShareLink(videoId: number): Promise<{ url: string }> {
  return req<{ url: string; token: string }>(`/api/v1/portal-admin/videos/${videoId}/share-link`, {
    method: "POST",
  });
}
