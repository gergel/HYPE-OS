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
