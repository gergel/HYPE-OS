import { cookies } from "next/headers";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type UpcomingEvent = {
  id: number;
  nev: string;
  forgatas_datuma: string | null;
  helyszin: string | null;
};

export type RevenueMonth = {
  month: string;
  total: number;
};

export type DashboardAlerts = {
  lejart_utomunka: number;
  lejart_feladat: number;
};

export type DashboardSummary = {
  mai_forgatasok: number;
  aktiv_project_codeok: number;
  equipment_utkozesek: number;
  havi_bevetel: number;
  upcoming_events: UpcomingEvent[];
  revenue_trend: RevenueMonth[];
  alerts: DashboardAlerts;
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
  forgatas_datuma_vege: string | null;
  /** A forgatás napon belüli időpontja ("08:30:00"), ha meg van adva - a
   * naptárból is átjön (lásd backend services/google_calendar.py). */
  forgatas_kezdes_ido: string | null;
  forgatas_veg_ido: string | null;
  helyszin: string | null;
  allapot: string | null;
  /** Kiküldés után "Kiküldve", egyébként üres - ugyanez az előzetesnél is
   * (lásd backend/app/services/dispo.py). */
  diszpo: string | null;
  elozetes_diszpo_kuldes: string | null;
  resztvevok_email: string | null;
};

export type Employee = {
  id: number;
  full_name: string;
  tipus: string;
  email: string | null;
  telefon: string | null;
  is_active: boolean;
  role: string;
  has_password: boolean;
  elso_munkanap: string | null;
  utolso_munkanap: string | null;
  vallakozas_neve: string | null;
  vallakozas_szekhely: string | null;
  vallalkozas_adoszama: string | null;
  vallalkozas_kepviselo: string | null;
  nyilvantartasi_szam: string | null;
  megbizas_targya: string | null;
  plusz_afa: boolean | null;
};

export type EmployeeDocument = {
  id: number;
  employee_id: number;
  filename: string;
  url: string;
  content_type: string | null;
  created_at: string;
};

export type Rate = {
  id: number;
  employee_id: number;
  orabler: number | null;
  napibler: number | null;
  tulora: number | null;
  plusz_nap: number | null;
  havi_alap: number | null;
  elso_munkanap: string | null;
  utolso_munkanap: string | null;
  fotos_napi_ber: number | null;
  nev: string | null;
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
  kifizetes_modja: string | null;
  hozzaadas_a_kiadasokhoz: boolean | null;
};

export type Revenue = {
  id: number;
  project_code_id: number;
  bevetel_formaja: string | null;
  netto: number | null;
  brutto: number | null;
  penznem: string;
  fizetes_datuma: string | null;
  szamla_kiallitva_datuma: string | null;
};

export type Deliverable = {
  id: number;
  projekt_neve: string;
  allapot: string | null;
  hatarido: string | null;
  anyag_kikuldve: boolean;
  vago_employee_id: number | null;
  assigned_to_employee_id: number | null;
  project_id: number | null;
  vinyok: string[] | null;
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
  project_id: number | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  megbizas_targya: string | null;
  szerzodes_allapota: string | null;
  keltezes: string | null;
  alairva: boolean;
  netto_osszeg: number | null;
  teljesites_kezdete: string | null;
  teljesites_vege: string | null;
  plusz_afa: boolean | null;
  brutto_osszeg: number | null;
  szerzodes_file_url: string | null;
};

export type PendingClientContract = {
  project_code_id: number;
  projektkod: string;
  client_id: number;
  client_nev: string | null;
  existing_keretszerzodes_id: number | null;
};

export async function getPendingClientContracts(): Promise<PendingClientContract[]> {
  return (await apiGet<PendingClientContract[]>("/api/v1/megrendeloi-szerzodesek")) ?? [];
}

/** A backend GET végpontok mostantól bejelentkezést igényelnek (lásd
 * app/api/crud_router.py), ezért a szerver-oldali (SSR) lekérdezéseknek is
 * kell egy érvényes Bearer token - ezt a login-kor beállított cookie-ból
 * olvassuk (lásd lib/authFetch.ts setToken), mert a middleware/SSR nem éri
 * el a böngésző localStorage-át, csak a cookie-kat. */
async function authHeaders(): Promise<HeadersInit> {
  const token = (await cookies()).get("hype_os_token")?.value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store", headers: await authHeaders() });
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

export async function getProjects(limit = 5000, skip = 0): Promise<Project[]> {
  return (await apiGet<Project[]>(`/api/v1/projects?limit=${limit}&skip=${skip}`)) ?? [];
}

export async function getEmployees(limit = 5000): Promise<Employee[]> {
  return (await apiGet<Employee[]>(`/api/v1/crew?limit=${limit}`)) ?? [];
}

export async function getEmployeeDocuments(employeeId: number): Promise<EmployeeDocument[]> {
  return (await apiGet<EmployeeDocument[]>(`/api/v1/crew/${employeeId}/munkaszerzodesek`)) ?? [];
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

export async function getDeliverables(limit = 5000, skip = 0): Promise<Deliverable[]> {
  return (await apiGet<Deliverable[]>(`/api/v1/deliverables?limit=${limit}&skip=${skip}`)) ?? [];
}

export async function getContracts(limit = 5000): Promise<Contract[]> {
  return (await apiGet<Contract[]>(`/api/v1/contracts?limit=${limit}`)) ?? [];
}

export type PendingSubcontractorProject = {
  project_id: number;
  project_nev: string | null;
  forgatas_datuma: string | null;
  pending_count: number;
};

export type SubcontractorContractDraft = {
  szerzodes_allapota: string | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  vallalkozas_kepviseloje: string | null;
  vallalkozas_nyilvantartasi_szam: string | null;
  megbizas_targya: string | null;
  netto_osszeg: number | null;
  teljesites_kezdete: string | null;
  teljesites_vege: string | null;
  keltezes: string | null;
  plusz_afa: boolean | null;
};

export type PendingSubcontractorEmployee = {
  id: number;
  full_name: string;
  email: string | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  kepviselo: string | null;
  nyilvantartasi_szam: string | null;
  megbizas_targya: string | null;
  plusz_afa: boolean | null;
  draft: SubcontractorContractDraft | null;
};

export type PendingSubcontractorProjectDetail = {
  project_id: number;
  project_nev: string | null;
  forgatas_datuma: string | null;
  forgatas_datuma_vege: string | null;
  pending: PendingSubcontractorEmployee[];
};

export async function getPendingSubcontractorProjects(): Promise<PendingSubcontractorProject[]> {
  return (await apiGet<PendingSubcontractorProject[]>("/api/v1/alvallalkozoi-szerzodesek")) ?? [];
}

export async function getPendingSubcontractorsForProject(
  projectId: number,
): Promise<PendingSubcontractorProjectDetail | null> {
  return apiGet<PendingSubcontractorProjectDetail>(`/api/v1/alvallalkozoi-szerzodesek/${projectId}`);
}

export type PendingTigProject = {
  project_id: number;
  project_nev: string | null;
  forgatas_datuma: string | null;
  pending_count: number;
};

export type TigDraft = {
  allapot: string | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  megbizas_targya: string | null;
  netto_osszeg: number | null;
  /** A teljesítés ideje SZABAD SZÖVEG (nem dátum) - ez megy a dokumentumba. */
  teljesites_szoveg: string | null;
  teljesites_kezdete: string | null;
  teljesites_vege: string | null;
  keltezes: string | null;
  plusz_afa: boolean | null;
};

export type PendingTigEmployee = {
  id: number;
  full_name: string;
  email: string | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  megbizas_targya: string | null;
  plusz_afa: boolean | null;
  draft: TigDraft | null;
};

export type PendingTigProjectDetail = {
  project_id: number;
  project_nev: string | null;
  projektkod: string | null;
  forgatas_datuma: string | null;
  forgatas_datuma_vege: string | null;
  /** A teljesítés idejének alapértelmezett szövege (a forgatás dátumából) -
   * az űrlap ezzel indul, amíg nincs mentett bejegyzés. */
  teljesites_szoveg_alap: string;
  pending: PendingTigEmployee[];
  tig_ready: boolean;
};

export async function getPendingTigProjects(): Promise<PendingTigProject[]> {
  return (await apiGet<PendingTigProject[]>("/api/v1/teljesitesi-igazolasok")) ?? [];
}

export async function getPendingTigForProject(projectId: number): Promise<PendingTigProjectDetail | null> {
  return apiGet<PendingTigProjectDetail>(`/api/v1/teljesitesi-igazolasok/${projectId}`);
}

export type PerformanceCertificateInvoice = {
  id: number;
  filename: string;
  url: string;
  content_type: string | null;
  created_at: string;
};

export type PerformanceCertificate = {
  id: number;
  project_id: number;
  employee_id: number;
  allapot: string | null;
  file_url: string | null;
  ceg_neve: string | null;
  netto_osszeg: number | null;
  plusz_afa: boolean | null;
  brutto_osszeg: number | null;
  /** Egy TIG-hez több számla is tartozhat, egyenként törölhetően. */
  invoices: PerformanceCertificateInvoice[];
  szamla_kifizetve: boolean;
  expense_id: number | null;
};

export async function getAllTigForProject(projectId: number): Promise<PerformanceCertificate[]> {
  return (await apiGet<PerformanceCertificate[]>(`/api/v1/teljesitesi-igazolasok/${projectId}/all`)) ?? [];
}

export type InternalPerformanceCertificateInvoice = {
  id: number;
  filename: string;
  url: string;
  content_type: string | null;
  created_at: string;
};

export type InternalPerformanceCertificate = {
  id: number;
  employee_id: number;
  ev: number;
  honap: number;
  allapot: string | null;
  megjegyzes: string | null;
  netto_osszeg: number | null;
  plusz_afa: boolean | null;
  brutto_osszeg: number | null;
  megbizas_targya: string | null;
  teljesites_datuma: string | null;
  keltezes: string | null;
  /** A kiküldött TIG dokumentum Drive linkje. */
  file_url: string | null;
  /** A hónap betűvel ("május") - a Belsős TIG sehol nem írja ki számmal. */
  honap_nev: string;
  invoices: InternalPerformanceCertificateInvoice[];
  szamla_kifizetve: boolean;
  expense_id: number | null;
};

export type BelsosTigMonthEmployee = {
  id: number;
  full_name: string;
  email: string | null;
  /** A munkatárs adatlapjáról - ezzel indul a TIG űrlap, amíg nincs saját
   * (esetleg felülírt) értéke a hónap bejegyzésének. */
  megbizas_targya: string | null;
  plusz_afa: boolean | null;
  record: InternalPerformanceCertificate | null;
};

export async function getBelsosTigMonth(ev?: number, honap?: number): Promise<BelsosTigMonthEmployee[]> {
  const params = new URLSearchParams();
  if (ev) params.set("ev", String(ev));
  if (honap) params.set("honap", String(honap));
  const qs = params.toString();
  return (await apiGet<BelsosTigMonthEmployee[]>(`/api/v1/belsos-tig${qs ? `?${qs}` : ""}`)) ?? [];
}

/** Egy munkatárs összes belsős TIG-je, a legfrissebb hónappal elöl - a
 * személy adatlapján a "Belsős TIG-ek" szekciót tölti. */
export async function getBelsosTigForEmployee(employeeId: number): Promise<InternalPerformanceCertificate[]> {
  return (await apiGet<InternalPerformanceCertificate[]>(`/api/v1/belsos-tig/employee/${employeeId}`)) ?? [];
}

export type UtokovetesOverview = {
  project_id: number;
  project_nev: string | null;
  projektkod: string | null;
  forgatas_datuma: string | null;
  forgatas_datuma_vege: string | null;
  szerzodes_osszes: number;
  szerzodes_fuggo: number;
  tig_ready: boolean;
  tig_osszes: number;
  tig_fuggo: number;
  /** Kifizetés: a nem belsős stábtagok (külsős + keretszerződéses) közül
   * hánynak kell fizetni, és hány van még hátra (lásd backend
   * utokovetes_admin.py _kifizetes_state). */
  kifizetes_osszes: number;
  kifizetes_fuggo: number;
  /** Csak akkor igaz, ha a szerződések, a TIG-ek ÉS a kifizetések is mind
   * rendben vannak - ekkor a projekt teljesen le van zárva. */
  kesz: boolean;
  visszajelzes_darab: number;
};

export type PostShootFeedback = {
  id: number;
  project_id: number;
  erdemleges_tortent: string | null;
  technika_info: string | null;
  egyeb: string | null;
  werk_fotok: { url: string; filename: string }[] | null;
  created_at: string;
};

export type UtokovetesDetail = {
  project_id: number;
  project_nev: string | null;
  projektkod: string | null;
  forgatas_datuma: string | null;
  forgatas_datuma_vege: string | null;
  szerzodesek: { id: number; full_name: string; email: string | null; draft: SubcontractorContractDraft | null }[];
  tig_ready: boolean;
  teljesitesi_igazolasok: {
    id: number;
    full_name: string;
    email: string | null;
    draft: TigDraft | null;
    szamla_kifizetve: boolean;
    van_szamla: boolean;
  }[];
  kifizetes_osszes: number;
  kifizetes_fuggo: number;
  kesz: boolean;
  visszajelzesek: PostShootFeedback[];
};

export async function getUtokovetesOverview(): Promise<UtokovetesOverview[]> {
  return (await apiGet<UtokovetesOverview[]>("/api/v1/utokovetes")) ?? [];
}

export async function getUtokovetesDetail(projectId: number): Promise<UtokovetesDetail | null> {
  return apiGet<UtokovetesDetail>(`/api/v1/utokovetes/${projectId}`);
}

export async function getRates(limit = 5000): Promise<Rate[]> {
  return (await apiGet<Rate[]>(`/api/v1/rates?limit=${limit}`)) ?? [];
}

export type MonthlyFinance = { month: string; bevetel: number; kiadas: number };

export type OutstandingProject = {
  project_code_id: number;
  projektkod: string;
  ugyfel_nev: string | null;
  kintlevo_osszeg: number;
  legkorabbi_hatarido: string | null;
  lejart: boolean;
};

export type PaymentMethodBreakdown = { kifizetes_modja: string | null; osszeg: number };

export type FinanceSummary = {
  ytd_bevetel: number;
  ytd_kiadas: number;
  ytd_profit: number;
  osszes_kintlevoseg: number;
  kintlevo_projektek_szama: number;
  havi_trend: MonthlyFinance[];
  kintlevo_projektek: OutstandingProject[];
  ytd_kiadas_fizetesi_mod_szerint: PaymentMethodBreakdown[];
};

export async function getFinanceSummary(): Promise<FinanceSummary | null> {
  return apiGet<FinanceSummary>("/api/v1/finance/summary");
}

export type FieldVisibilityConfig = { employee_id: number; entity_type: string; visible_fields: string[] | null };

/** A bejelentkezett felhasználó saját mező-láthatósága egy entitástípushoz -
 * egyénenként állítható be a Beállítások oldalon (csak admin szerkesztheti).
 * Nincs config sor -> nincs szűrés, minden mező látszik. */
export async function getVisibleFields(entityType: string): Promise<string[] | null> {
  const res = await apiGet<{ visible_fields: string[] | null }>(`/api/v1/field-visibility/me/${entityType}`);
  return res?.visible_fields ?? null;
}

export type FieldTypeInfo = { type: string; options?: string[] };

/** {mezőnév: {type: "boolean"|"date"|"datetime"|"number"|"select"|"text", options?: [...]}}
 * egy entitástípushoz - kell, hogy egy éppen null értékű mezőt (pl. egy még be
 * nem pipált checkbox) a EditableDetailGrid a helyes input-típussal
 * jelenítsen meg, illetve hogy mely mezők jelenjenek meg legördülő (select)
 * listaként a lehetséges értékekkel. */
export async function getFieldTypes(entityType: string): Promise<Record<string, FieldTypeInfo>> {
  return (await apiGet<Record<string, FieldTypeInfo>>(`/api/v1/field-visibility/schema/${entityType}`)) ?? {};
}

/** Admin-nézet: MINDEN munkatárs összes mező-láthatósági beállítása egyetlen
 * lekérdezéssel (Beállítások oldal) - fontos, hogy egy hívás legyen munkatársanként
 * N hívás helyett, mert utóbbi (sok munkatárs esetén, párhuzamosan hívva) kimeríti
 * a backend DB connection pool-ját (QueuePool timeout, 500-as hibák). */
export async function getAllFieldVisibility(): Promise<FieldVisibilityConfig[]> {
  return (await apiGet<FieldVisibilityConfig[]>("/api/v1/field-visibility")) ?? [];
}

export type PageAccessConfig = { employee_id: number; page_permissions: Record<string, string[]> | null };

/** A bejelentkezett felhasználó saját oldal-hozzáférése - null = minden oldalt
 * lát. A middleware és a Sidebar is ez alapján szűr. */
export async function getMyPageAccess(): Promise<string[] | null> {
  const res = await apiGet<{ allowed_pages: string[] | null }>("/api/v1/user-access/me");
  return res?.allowed_pages ?? null;
}

/** A bejelentkezett felhasználó teljes {oldal_vagy_"oldal:fül": [művelet, ...]}
 * térképe - null = nincs korlátozás (mindent lát/szerkeszthet). A fül-szintű
 * nézési/szerkesztési jogosultság ugyanezt a dictet használja, "{page}:{tab_key}"
 * összetett kulcsokkal (lásd backend core/security.check_page_action,
 * models/detail_tab.py osztály-komment) - erre épül a részletnézetek
 * fül-szűrése (lásd DetailTabs, EditableDetailGrid readOnly módja). */
export async function getMyPagePermissions(): Promise<Record<string, string[]> | null> {
  const res = await apiGet<{ page_permissions: Record<string, string[]> | null }>("/api/v1/user-access/me");
  return res?.page_permissions ?? null;
}

export type DetailTab = {
  tab_key: string;
  label: string;
  icon: string | null;
  field_keys: string[];
};

/** Egy entitástípus admin által beállított fül-elrendezése (lásd
 * backend/app/services/detail_tabs.py) - a részletnézetek ez alapján
 * renderelik a füleket. Bejelentkezett felhasználó bárki lekérdezheti. */
export async function getDetailTabs(entityType: string): Promise<DetailTab[]> {
  return (await apiGet<DetailTab[]>(`/api/v1/detail-tabs/${entityType}`)) ?? [];
}

/** A részletnézet szekció-kártyáinak ("widgetek") mentett sorrendje - a
 * felhasználó húzással állítja be, és onnantól az adott entitástípus MINDEN
 * rekordjánál ez érvényes (lásd components/DetailSections.tsx). */
export async function getSectionOrder(entityType: string): Promise<string[]> {
  const res = await apiGet<{ section_keys: string[] }>(`/api/v1/detail-tabs/${entityType}/section-order`);
  return res?.section_keys ?? [];
}

export type DetailTabConfigByEntity = { entity_type: string; tabs: DetailTab[] };

/** Admin-nézet: MINDEN entitástípus fül-elrendezése egyszerre (Beállítások
 * oldal admin fül-szerkesztője tölti be egyben). */
export async function getAllDetailTabs(): Promise<DetailTabConfigByEntity[]> {
  return (await apiGet<DetailTabConfigByEntity[]>("/api/v1/detail-tabs")) ?? [];
}

/** Admin-nézet: az összes munkatárs oldal-hozzáférése (Beállítások oldal). */
export async function getAllPageAccess(): Promise<PageAccessConfig[]> {
  return (await apiGet<PageAccessConfig[]>("/api/v1/user-access")) ?? [];
}

export type CurrentUser = {
  id: number;
  full_name: string;
  email: string | null;
  role: string;
  is_active: boolean;
};

/** A bejelentkezett felhasználó saját adatai (TopBar üdvözlés/avatar,
 * kijelentkezés) - a tokenből derül ki (lásd auth/me, get_current_user). */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  return apiGet<CurrentUser>("/api/v1/auth/me");
}

/** A bejelentkezett felhasználó saját Dashboard widget-beállítása - null =
 * minden widget látszik. Tisztán megjelenítési preferencia, bárki
 * szabadon szerkesztheti a sajátját (lásd Dashboard oldal, testreszabás gomb). */
export async function getMyDashboardConfig(): Promise<string[] | null> {
  const res = await apiGet<{ visible_widgets: string[] | null }>("/api/v1/dashboard/config/me");
  return res?.visible_widgets ?? null;
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

/** Az Utómunka (Deliverable) oldal kapcsolatai - lásd services/deliverable_actions.py. */
export type AssignableEmployee = { id: number; full_name: string };

export async function getAssignableEmployees(): Promise<AssignableEmployee[]> {
  return (await apiGet<AssignableEmployee[]>("/api/v1/deliverables/assignable-employees")) ?? [];
}

export async function getVinyoOptions(): Promise<string[]> {
  const res = await apiGet<{ options: string[] }>("/api/v1/deliverables/vinyo-options");
  return res?.options ?? [];
}

export type DeliverableContact = { id: number; full_name: string; email: string | null };

export async function getDeliverableContacts(deliverableId: number): Promise<DeliverableContact[]> {
  return (await apiGet<DeliverableContact[]>(`/api/v1/deliverables/${deliverableId}/contacts`)) ?? [];
}

export type TimerEmployeeSummary = {
  employee_id: number;
  full_name: string;
  total_minutes: number;
  total_cost: number | null;
};

/** Épp futó időmérés - névvel, hogy a felületen ne csak egy csupasz óra
 * ketyegjen, hanem az is látszódjon, kinél fut. */
export type TimerRunningEntry = {
  employee_id: number;
  full_name: string;
  since: string;
};

export type TimerState = {
  my_running_since: string | null;
  running: TimerRunningEntry[];
  by_employee: TimerEmployeeSummary[];
  total_minutes: number;
  total_cost: number | null;
};

export type UtomunkaProjektIdo = {
  project_id: number | null;
  project_nev: string | null;
  projektkod: string | null;
  anyagok_szama: number;
  total_minutes: number;
  total_cost: number | null;
};

/** Melyik projekten mennyit dolgozott ez a vágó utómunkával, összesítve. */
export async function getUtomunkaIdo(employeeId: number): Promise<UtomunkaProjektIdo[]> {
  return (await apiGet<UtomunkaProjektIdo[]>(`/api/v1/crew/${employeeId}/utomunka-ido`)) ?? [];
}

export async function getTimerState(deliverableId: number): Promise<TimerState | null> {
  return apiGet<TimerState>(`/api/v1/deliverables/${deliverableId}/timer/state`);
}

export type DeliverableComment = {
  id: number;
  deliverable_id: number;
  employee_id: number;
  employee_name: string;
  body: string;
  created_at: string;
};

export async function getDeliverableComments(deliverableId: number): Promise<DeliverableComment[]> {
  return (await apiGet<DeliverableComment[]>(`/api/v1/deliverables/${deliverableId}/comments`)) ?? [];
}

export type NotificationItem = {
  id: number;
  kind: string;
  message: string;
  link: string;
  is_read: boolean;
  created_at: string;
};

export async function getNotifications(): Promise<NotificationItem[]> {
  return (await apiGet<NotificationItem[]>("/api/v1/notifications")) ?? [];
}

export type MyTaskItem = {
  id: number;
  title: string;
  hatarido: string | null;
  link: string;
};

export type MyTasksSummary = {
  deliverables: MyTaskItem[];
  tasks: MyTaskItem[];
  /** A másnapi forgatások diszpói, ha a felhasználó diszpó-felelős (lásd
   * backend models/dispo_responsible.py). */
  diszpok: MyTaskItem[];
};

/** Ki felel a diszpó kiküldéséért, oldalanként (gyártás / technika) - a
 * Beállítások oldalon szerkeszthető, és ez alapján kapják meg a felelősök a
 * másnapi diszpókat teendőként. */
export type DispoResponsibles = { gyartas: number[]; technika: number[] };

export async function getDispoResponsibles(): Promise<DispoResponsibles> {
  return (await apiGet<DispoResponsibles>("/api/v1/dispo-responsibles")) ?? { gyartas: [], technika: [] };
}

export async function getMyTasksSummary(): Promise<MyTasksSummary | null> {
  return apiGet<MyTasksSummary>("/api/v1/dashboard/my-tasks");
}

export type StocktakeItem = {
  id: number;
  equipment_id: number;
  equipment_nev: string;
  kategoria: string | null;
  track_mode: string;
  expected_qty: number | null;
  counted_qty: number | null;
  status: string | null;
};

export type StocktakeSession = {
  id: number;
  started_by_employee_id: number;
  started_by_name: string;
  created_at: string;
  completed_at: string | null;
  items: StocktakeItem[];
};

export type StocktakeSessionListItem = {
  id: number;
  started_by_name: string;
  created_at: string;
  completed_at: string | null;
  item_count: number;
};

export type StocktakeStatusGroup = {
  status: string;
  items: { equipment_id: number; nev: string }[];
};

export type StocktakeMissingStock = {
  equipment_id: number;
  nev: string;
  expected_qty: number;
  counted_qty: number;
  hiany: number;
};

export type StocktakeSummary = {
  problemas_statuszok: StocktakeStatusGroup[];
  hianyzo_keszletek: StocktakeMissingStock[];
};

export async function getStocktakeSessions(): Promise<StocktakeSessionListItem[]> {
  return (await apiGet<StocktakeSessionListItem[]>("/api/v1/stocktake/sessions")) ?? [];
}

export async function getStocktakeSession(sessionId: number): Promise<StocktakeSession | null> {
  return apiGet<StocktakeSession>(`/api/v1/stocktake/sessions/${sessionId}`);
}

export async function getStocktakeSummary(sessionId: number): Promise<StocktakeSummary | null> {
  return apiGet<StocktakeSummary>(`/api/v1/stocktake/sessions/${sessionId}/summary`);
}

/** Média Portál (ügyfél videó/kép átadó felület, /p/{slug}) admin adatai -
 * lásd backend/app/api/routes/portal_admin.py. Egy Portal mindig egy meglévő
 * HYPE OS Project-hez van kötve (1:1) - a cím/ügyfélnév a Project mezőire esik
 * vissza, hacsak nincs felülírva (title_override/client_name_override). */
export type PortalSummary = {
  id: number;
  slug: string;
  project_id: number | null;
  deliverable_id: number | null;
  title: string;
  client_name: string;
  cover_image_url: string;
  status: string;
  brand: string;
  project_date: string;
  expires_at: string | null;
  payment_mode: string;
  has_password: boolean;
  share_token: string | null;
};

export type PortalVideoItem = {
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
};

export type PortalImageItem = {
  id: number;
  title: string;
  folder_id: number | null;
  url: string;
  thumbnail_url: string;
};

export type PortalFolderItem = {
  id: number;
  name: string;
  sort_order: number;
};

export type PortalDetailData = PortalSummary & {
  description: string;
  share_token: string | null;
  title_override: string | null;
  client_name_override: string | null;
  project_date_override: string | null;
  videos: PortalVideoItem[];
  folders: PortalFolderItem[];
  images: PortalImageItem[];
};

export async function getPortals(): Promise<PortalSummary[]> {
  return (await apiGet<PortalSummary[]>("/api/v1/portal-admin")) ?? [];
}

export async function getPortalDetail(portalId: number): Promise<PortalDetailData | null> {
  return apiGet<PortalDetailData>(`/api/v1/portal-admin/${portalId}`);
}
