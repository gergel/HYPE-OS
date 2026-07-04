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
  adoszam: string | null;
  szekhely: string | null;
};

export type ProjectCode = {
  id: number;
  projektkod: string;
  client_id: number;
  esemeny_allapota: string | null;
  becsult_profit: number;
  osszes_koltseg: number;
  datum: string | null;
};

export type Project = {
  id: number;
  nev: string;
  project_code_id: number;
  forgatas_datuma: string | null;
  helyszin: string | null;
  allapot: string | null;
};

export type Employee = {
  id: number;
  full_name: string;
  tipus: string;
  email: string | null;
  telefon: string | null;
  is_active: boolean;
  role: string;
};

export type Equipment = {
  id: number;
  nev: string;
  serial_number: string | null;
  kategoria: string | null;
  allapot: string | null;
  track_mode: string;
  osszes_mennyiseg: number | null;
};

export type Campaign = {
  id: number;
  nev: string;
  kampany_statusza: string | null;
  hatarido: string | null;
  kesz: boolean;
};

export type Task = {
  id: number;
  feladat: string;
  allapot: string | null;
  hatarido: string | null;
  kategoria: string | null;
  checked: boolean;
};

export type Expense = {
  id: number;
  megnevezes: string;
  tipus: string | null;
  netto: number | null;
  brutto: number | null;
  penznem: string;
  kesz: boolean;
};

export type Revenue = {
  id: number;
  project_code_id: number;
  bevetel_formaja: string | null;
  netto: number | null;
  brutto: number | null;
  penznem: string;
};

export type Deliverable = {
  id: number;
  projekt_neve: string;
  allapot: string | null;
  hatarido: string | null;
  anyag_kikuldve: boolean;
  vago_employee_id: number | null;
};

export type JsonRecord = Record<string, unknown> & { id: number };

export type Contact = {
  id: number;
  client_id: number;
  full_name: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
};

export type Contract = {
  id: number;
  tipus: string;
  client_id: number | null;
  employee_id: number | null;
  ceg_neve: string | null;
  szerzodes_allapota: string | null;
  alairva: boolean;
};

export async function apiGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
    if (!res.ok) {
      console.error(`API hiba: GET ${path} -> HTTP ${res.status}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.error(`API elérhetetlen: GET ${path} ->`, err);
    return null;
  }
}

export async function getDashboardSummary(): Promise<DashboardSummary | null> {
  return apiGet<DashboardSummary>("/api/v1/dashboard/summary");
}

export async function getProjectCodes(limit = 5000): Promise<ProjectCode[]> {
  return (await apiGet<ProjectCode[]>(`/api/v1/project-codes?limit=${limit}`)) ?? [];
}

export async function getClients(limit = 5000): Promise<Client[]> {
  return (await apiGet<Client[]>(`/api/v1/clients?limit=${limit}`)) ?? [];
}

export async function getProjects(limit = 5000): Promise<Project[]> {
  return (await apiGet<Project[]>(`/api/v1/projects?limit=${limit}`)) ?? [];
}

export async function getEmployees(limit = 5000): Promise<Employee[]> {
  return (await apiGet<Employee[]>(`/api/v1/crew?limit=${limit}`)) ?? [];
}

export async function getEquipment(limit = 5000): Promise<Equipment[]> {
  return (await apiGet<Equipment[]>(`/api/v1/equipment?limit=${limit}`)) ?? [];
}

export async function getCampaigns(limit = 5000): Promise<Campaign[]> {
  return (await apiGet<Campaign[]>(`/api/v1/campaigns?limit=${limit}`)) ?? [];
}

export async function getTasks(limit = 5000): Promise<Task[]> {
  return (await apiGet<Task[]>(`/api/v1/tasks?limit=${limit}`)) ?? [];
}

export async function getExpenses(limit = 5000): Promise<Expense[]> {
  return (await apiGet<Expense[]>(`/api/v1/expenses?limit=${limit}`)) ?? [];
}

export async function getRevenues(limit = 5000): Promise<Revenue[]> {
  return (await apiGet<Revenue[]>(`/api/v1/revenues?limit=${limit}`)) ?? [];
}

export async function getDeliverables(limit = 5000): Promise<Deliverable[]> {
  return (await apiGet<Deliverable[]>(`/api/v1/deliverables?limit=${limit}`)) ?? [];
}

export async function getContracts(limit = 5000): Promise<Contract[]> {
  return (await apiGet<Contract[]>(`/api/v1/contracts?limit=${limit}`)) ?? [];
}

export type FieldVisibilityConfig = { entity_type: string; visible_fields: string[] | null };

/** A Beállítások oldalon konfigurált mező-láthatóság - melyik mezők jelenjenek
 * meg egy adott entitástípus (lásd ENTITY_PATHS kulcsok) részletnézetén.
 * Nincs config sor -> nincs szűrés, minden mező látszik. */
export async function getFieldVisibility(): Promise<FieldVisibilityConfig[]> {
  return (await apiGet<FieldVisibilityConfig[]>("/api/v1/field-visibility")) ?? [];
}

export async function getVisibleFields(entityType: string): Promise<string[] | null> {
  const all = await getFieldVisibility();
  return all.find((c) => c.entity_type === entityType)?.visible_fields ?? null;
}

/** {mezőnév: "boolean"|"date"|"datetime"|"number"|"text"} egy entitástípushoz -
 * kell, hogy egy éppen null értékű mezőt (pl. egy még be nem pipált checkbox)
 * a EditableDetailGrid a helyes input-típussal jelenítsen meg, mert a nyers
 * null értékből ez önmagában nem derülne ki. */
export async function getFieldTypes(entityType: string): Promise<Record<string, string>> {
  return (await apiGet<Record<string, string>>(`/api/v1/field-visibility/${entityType}/schema`)) ?? {};
}

/** Az egyes entitás-modulok API alap-útvonalai, a részletnézetekhez és a
 * kapcsolódó rekordok (foreign key szerinti szűrés) lekérdezéséhez. */
export const ENTITY_PATHS = {
  client: "/api/v1/clients",
  contact: "/api/v1/contacts",
  projectCode: "/api/v1/project-codes",
  project: "/api/v1/projects",
  employee: "/api/v1/crew",
  rate: "/api/v1/rates",
  equipment: "/api/v1/equipment",
  campaign: "/api/v1/campaigns",
  task: "/api/v1/tasks",
  expense: "/api/v1/expenses",
  revenue: "/api/v1/revenues",
  deliverable: "/api/v1/deliverables",
  timesheet: "/api/v1/timesheets",
  feedback: "/api/v1/feedback",
  contract: "/api/v1/contracts",
  assignment: "/api/v1/assignments",
} as const;

/** Egy rekord összes mezőjének lekérése (a részletnézetekhez) - nem szűkítjük
 * le típusra, mert a cél épp az, hogy minden Notionből átjött oszlopot lássunk. */
export async function getRecord(basePath: string, id: number): Promise<JsonRecord | null> {
  return apiGet<JsonRecord>(`${basePath}/${id}`);
}

/** Egy tetszőleges (bármelyik) rekord lekérése egy entitástípusból - a
 * Beállítások oldal mező-láthatóság szerkesztőjének kell, hogy fel tudja
 * sorolni, milyen mezői vannak az adott entitásnak (a rekord kulcsaiból). */
export async function getSampleRecord(basePath: string): Promise<JsonRecord | null> {
  const rows = await apiGet<JsonRecord[]>(`${basePath}?limit=1`);
  if (!rows || rows.length === 0) return null;
  // A lista végpont egyes entitásoknál (pl. Project) szándékosan szűkebb sémát ad
  // vissza teljesítmény miatt (lásd list_read_schema) - az egyedi GET viszont
  // mindig a teljes sémát, ezért azt kérjük le, hogy minden mező felsorolható legyen.
  return getRecord(basePath, rows[0].id);
}

/** Kapcsolódó rekordok lekérése egy foreign key oszlop szerint szűrve, pl.
 * getRelated(ENTITY_PATHS.project, { project_code_id: 5 }) -> az adott
 * Project Code összes Projektje. A backend generikus CRUD router bármelyik
 * valódi oszlop szerinti query paramot elfogadja. */
export async function getRelated(
  basePath: string,
  params: Record<string, number | string>,
  limit = 5000,
): Promise<JsonRecord[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  for (const [key, value] of Object.entries(params)) query.set(key, String(value));
  return (await apiGet<JsonRecord[]>(`${basePath}?${query.toString()}`)) ?? [];
}

export async function getContactsByClient(clientId: number): Promise<Contact[]> {
  return (await getRelated(ENTITY_PATHS.contact, { client_id: clientId })) as unknown as Contact[];
}

/** Több rekord lekérése id lista alapján (many-to-many kapcsolatokhoz, pl. egy
 * Projekthez rendelt Equipment-ek - ott nincs egyetlen foreign key oszlop, amivel
 * getRelated szűrhetne, csak egy id-lista a rekordon). */
export async function getRecordsByIds(basePath: string, ids: number[]): Promise<JsonRecord[]> {
  const records = await Promise.all(ids.map((id) => getRecord(basePath, id)));
  return records.filter((r): r is JsonRecord => r !== null);
}

export function formatHuf(value: number | null): string {
  if (value === null) return "–";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(".0", "")}M Ft`;
  if (Math.abs(value) >= 1_000) return `${Math.round(value / 1_000)}k Ft`;
  return `${value} Ft`;
}

export function formatDate(value: string | null): string {
  if (!value) return "–";
  return value.slice(0, 10);
}
