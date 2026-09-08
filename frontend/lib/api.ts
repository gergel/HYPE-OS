const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type DashboardSummary = {
  mai_forgatasok: number;
  aktiv_project_codeok: number;
  equipment_utkozesek: number;
  havi_bevetel: number;
};

export type Client = {
  id: number;
  nev: string;
};

export type ProjectCode = {
  id: number;
  projektkod: string;
  client_id: number;
  esemeny_allapota: string | null;
  becsult_profit: number;
};

export async function apiGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function getDashboardSummary(): Promise<DashboardSummary | null> {
  return apiGet<DashboardSummary>("/api/v1/dashboard/summary");
}

export async function getProjectCodes(limit = 5): Promise<ProjectCode[]> {
  return (await apiGet<ProjectCode[]>(`/api/v1/project-codes?limit=${limit}`)) ?? [];
}

export async function getClients(limit = 100): Promise<Client[]> {
  return (await apiGet<Client[]>(`/api/v1/clients?limit=${limit}`)) ?? [];
}

export function formatHuf(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(".0", "")}M Ft`;
  if (Math.abs(value) >= 1_000) return `${Math.round(value / 1_000)}k Ft`;
  return `${value} Ft`;
}

// --- Galéria ZIP64 export -------------------------------------------------------

export type ExportStatus = "queued" | "running" | "ready" | "failed" | "expired";

export type GalleryExport = {
  public_id: string;
  project_id: number;
  status: ExportStatus;
  source_fingerprint: string;
  file_count: number;
  files_done: number;
  total_source_bytes: number;
  expected_archive_bytes: number;
  bytes_done: number;
  progress_percent: number;
  filename: string | null;
  object_size: number | null;
  object_etag: string | null;
  archive_sha256: string | null;
  attempts: number;
  max_attempts: number;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  ready_at: string | null;
  expires_at: string | null;
};

export type GalleryPlan = {
  project_id: number;
  source_fingerprint: string;
  file_count: number;
  total_source_bytes: number;
  expected_archive_bytes: number;
};

export type GalleryExportState = {
  plan: GalleryPlan | null;
  job: GalleryExport | null;
  unavailable_reason: string | null;
};

export type DownloadTicket = {
  url: string;
  expires_at: string;
  filename: string;
  size: number;
  etag: string;
  sha256: string | null;
  direct: boolean;
};

export class ApiError extends Error {
  status: number;
  code: string | null;
  constructor(status: number, code: string | null, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem("hype_os_token");
  } catch {
    return null;
  }
}

async function authFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    let code: string | null = null;
    let message = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail && typeof data.detail === "object") {
        code = data.detail.code ?? null;
        message = data.detail.message ?? message;
      } else if (typeof data?.detail === "string") {
        message = data.detail;
      }
    } catch {
      /* nem JSON válasz */
    }
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}

export function getGalleryExportState(projectId: number): Promise<GalleryExportState> {
  return authFetch<GalleryExportState>(`/api/v1/projects/${projectId}/gallery-export`);
}

export function createGalleryExport(projectId: number): Promise<GalleryExport> {
  return authFetch<GalleryExport>(`/api/v1/projects/${projectId}/gallery-export`, { method: "POST" });
}

export function getGalleryExport(publicId: string): Promise<GalleryExport> {
  return authFetch<GalleryExport>(`/api/v1/gallery-exports/${publicId}`);
}

export function createDownloadUrl(publicId: string): Promise<DownloadTicket> {
  return authFetch<DownloadTicket>(`/api/v1/gallery-exports/${publicId}/download-url`, { method: "POST" });
}

export function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "–";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let index = 0;
  let amount = value;
  while (amount >= 1000 && index < units.length - 1) {
    amount /= 1000;
    index += 1;
  }
  const digits = index === 0 ? 0 : amount >= 100 ? 0 : amount >= 10 ? 1 : 2;
  return `${amount.toFixed(digits)} ${units[index]}`;
}
