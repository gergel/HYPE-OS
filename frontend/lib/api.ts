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
  /** Meeting / helyszínbejárás, nem forgatás - nincs mit diszponálni. A
   * naptár-szinkron a lila esemény-szín alapján állítja be (lásd backend
   * services/google_calendar.py), de kézzel is átállítható. */
  nem_diszponalando: boolean;
  /** A naptáresemény színe magyar néven, ha kapott egyet ("Lila", "Zöld"…). */
  naptar_szin: string | null;
  /** Ha ez a sor egy több napos forgatásból LEVÁLASZTOTT nap, itt az eredeti
   * projekt azonosítója - arra a napra már ez a diszponálandó, nem az egész. */
  feldarabolas_szulo_id: number | null;
};

export type Employee = {
  id: number;
  full_name: string;
  tipus: string;
  email: string | null;
  telefon: string | null;
  is_active: boolean;
  /** Az elsődleges szerepkör; a továbbiak a tovabbi_szerepkorok listában. */
  role: string;
  tovabbi_szerepkorok?: string[] | null;
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

/** Egy rekordhoz csatolt fájl (szerződés / TIG / számla / egyéb). A tartalom
 * mindig az R2 tárhelyen van, itt csak a hivatkozás (lásd backend
 * services/attachments.py). */
export type DocumentAttachment = {
  id: number;
  entity_type: string;
  entity_id: number;
  kategoria: "szerzodes" | "tig" | "szamla" | "diszpo" | "egyeb";
  filename: string;
  url: string;
  content_type: string | null;
  meret_bajt: number | null;
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
  /** A feltöltött KIMENŐ (megrendelői) számla - ebből áll össze a havi
   * számla-csomag kimenő oldala (lásd SzamlaCsomagLetoltes). */
  szamla_filename: string | null;
  szamla_file_url: string | null;
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
  /** Mikor állították le UTOLJÁRA a vágás időmérőjét. Notion importnál a
   * 'Timesheet Public' End Date mezőjéből jön, a rendszeren belül a timer
   * leállítása írja. */
  vagas_leallitva: string | null;
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

/** Egy keretszerződés érvényességi időszaka (lásd backend
 * models/contract.py ContractPeriod). A nyitott vég azt jelenti: "azóta is
 * él", a nyitott kezdet azt, hogy "a kezdetektől". */
export type ContractPeriod = {
  id: number;
  contract_id: number;
  kezdet: string | null;
  veg: string | null;
  megjegyzes: string | null;
};

export type Contract = {
  id: number;
  tipus: string;
  client_id: number | null;
  employee_id: number | null;
  /** Keretszerződés köthető CÉGGEL is: az embereket küldő vállalkozással
   * (lásd backend models/vallalkozas.py) - ilyenkor employee_id üres. */
  vallalkozas_id: number | null;
  project_id: number | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  megbizas_targya: string | null;
  szerzodes_allapota: string | null;
  keltezes: string | null;
  alairva: boolean;
  /** Álló keretszerződés (true) vagy eseti megbízási szerződés (false) -
   * lásd backend models/contract.py Contract.keretszerzodes. */
  keretszerzodes: boolean;
  /** Be van-e kapcsolva a keretszerződés (kézi kapcsoló). */
  aktiv: boolean;
  /** Mettől meddig élt - üres lista = időbeli korlát nélkül érvényes. */
  idoszakok: ContractPeriod[];
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

export async function getAttachments(entityType: string, entityId: number): Promise<DocumentAttachment[]> {
  return (await apiGet<DocumentAttachment[]>(`/api/v1/csatolmanyok/${entityType}/${entityId}`)) ?? [];
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
  /** A teljesítés ideje SZABAD SZÖVEG (a régi, dátumpáros szerződéseknél a
   * két dátumból képzett szöveg - lásd backend _teljesites_szovege). */
  teljesites_szoveg: string | null;
  keltezes: string | null;
  plusz_afa: boolean | null;
  /** Mire szól a szerződés: kinek a munkájára, melyik projekten. Több tétel
   * akkor, ha egy fél több ember munkájáról vagy több forgatásról szerződik
   * egyben (lásd backend models/contract.py ContractTetel). */
  tetelek: TigTetel[];
};

/** Egy stábtag, akinek a munkáját egy szerződés/TIG lefedi. */
export type LefedettEmber = {
  id: number;
  full_name: string;
};

/** Egy SZÁMLÁZÓ FÉL, akitől szerződés kell egy projekten. Nem feltétlenül egy
 * ember: lehet cég is, és egy fél több stábtag munkáját is fedheti (lásd
 * backend services/szamlazo.py). */
export type PendingSubcontractorEmployee = {
  /** Az ember azonosítója; cégnél 0. A műveletek a `szamlazo` kulccsal mennek. */
  id: number;
  /** "e12" (ember) vagy "v3" (vállalkozás) - ez megy az útvonalba. */
  szamlazo: string;
  full_name: string;
  /** "Ladányi Máté (Balla Berci helyett is)" */
  cimke: string;
  /** A projekten hozzá tartozó stábtagok - a szerződés alap-tétellistája. */
  lefedettek: TigTetel[];
  vallalkozas_id: number | null;
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
  /** A teljesítés idejének előtöltése a forgatás dátumából. */
  teljesites_szoveg_alap: string;
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

/** Egy projekthez MÁR elkészült (vagy kihagyott) eseti szerződés - a függő
 * listáról a kiküldött szerződés eltűnik, ezért kell külön lekérni, hogy a
 * kész papír (és a linkje) is látszódjon. */
export type ElkeszultSzerzodes = {
  contract_id: number;
  /** Cég nevére szóló szerződésnél 0 - a címzés a `szamlazo` kulccsal megy. */
  employee_id: number;
  szamlazo: string;
  full_name: string;
  szerzodes_allapota: string | null;
  netto_osszeg: number | null;
  keltezes: string | null;
  szerzodes_file_url: string | null;
  /** Visszaérkezett-e a MEGBÍZOTT által aláírt példány, és hol van. Amíg
   * nincs meg, a projekt "aláírt szerződésre vár" az utókövetésben. */
  alairva: boolean;
  alairt_file_url: string | null;
  /** Miért hagytuk ki, vagy hol van a máshol készült papír. */
  kihagyas_oka: string | null;
};

export async function getAllContractsForProject(projectId: number): Promise<ElkeszultSzerzodes[]> {
  return (await apiGet<ElkeszultSzerzodes[]>(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/all`)) ?? [];
}

/** Egy sor az "Eseti szerződések" listáján: a szerződés, mellette az EMBER és
 * a PROJEKT, amihez tartozik (lásd backend routes/eseti_szerzodesek.py). */
export type EsetiSzerzodes = {
  id: number;
  employee_id: number | null;
  employee_nev: string | null;
  employee_tipus: string | null;
  /** Cég nevére szóló szerződésnél a számlázó vállalkozás. */
  vallalkozas_id: number | null;
  vallalkozas_nev: string | null;
  /** Kiknek a munkáját fedi ez az egy szerződés a projekten. */
  lefedettek: string[];
  project_id: number | null;
  project_nev: string | null;
  projektkod: string | null;
  forgatas_datuma: string | null;
  ceg_neve: string | null;
  megbizas_targya: string | null;
  szerzodes_allapota: string | null;
  /** Miért hagytuk ki - csak a kihagyottaknál van kitöltve. */
  kihagyas_oka: string | null;
  netto_osszeg: number | null;
  brutto_osszeg: number | null;
  plusz_afa: boolean | null;
  teljesites_szoveg: string | null;
  keltezes: string | null;
  alairva: boolean;
  szerzodes_file_url: string | null;
};

/** Egy sor az "Összes külsős TIG" listán - a KIHAGYOTTAK is benne vannak, az
 * indokukkal együtt (lásd backend routes/kulsos_tigek.py). */
export type KulsosTig = {
  id: number;
  employee_id: number | null;
  employee_nev: string | null;
  vallalkozas_id: number | null;
  vallalkozas_nev: string | null;
  /** Kinek a munkáját igazolja - egynél több, ha a fél mások nevében is számláz. */
  lefedettek: string[];
  project_id: number | null;
  project_nev: string | null;
  projektkod: string | null;
  forgatas_datuma: string | null;
  /** Hány projekt munkáját igazolja összesen (1 = csak a sajátját). */
  projektek_szama: number;
  allapot: string | null;
  kihagyas_oka: string | null;
  megbizas_targya: string | null;
  netto_osszeg: number | null;
  brutto_osszeg: number | null;
  plusz_afa: boolean | null;
  teljesites_szoveg: string | null;
  keltezes: string | null;
  file_url: string | null;
  szamla_db: number;
  szamla_kifizetve: boolean;
};

/** Egy TIG teljes adatlapja - a listasor mezőin FELÜL a papírra kerülő adatok,
 * a tételek és a feltöltött számlák (lásd backend get_kulsos_tig). */
export type KulsosTigReszlet = KulsosTig & {
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  email: string | null;
  tetelek: {
    project_id: number;
    project_nev: string | null;
    projektkod: string | null;
    forgatas_datuma: string | null;
    employee_id: number;
    employee_nev: string | null;
    netto_osszeg: number | null;
    megnevezes: string | null;
  }[];
  szamlak: { id: number; filename: string; url: string }[];
};

export async function getKulsosTigek(): Promise<KulsosTig[]> {
  return (await apiGet<KulsosTig[]>("/api/v1/kulsos-tigek")) ?? [];
}

export async function getEsetiSzerzodesek(): Promise<EsetiSzerzodes[]> {
  return (await apiGet<EsetiSzerzodes[]>("/api/v1/eseti-szerzodesek")) ?? [];
}

/** Egy belsős munkatárs időszakai: mettől meddig volt belsős. Ettől függ,
 * mely hónapokra vár a rendszer havi TIG-et (lásd backend
 * services/belsos_idoszak.py). */
export type BelsosIdoszak = {
  id: number;
  employee_id: number;
  kezdet: string | null;
  veg: string | null;
  megjegyzes: string | null;
};

/** Egy munkatárs belsős időszakai - a saját adatlapján szerkeszthető. */
export type EmployeeBelsosIdoszakok = {
  employee_id: number;
  full_name: string;
  /** "megbizas" = havonta számláz, kell havi TIG. "alkalmazott" = bejelentett,
   * a bérét bérszámfejtés fizeti - tőle nincs TIG, csak a fizetését kell
   * beírni (lásd backend models/employee.py BelsosJogviszony). */
  jogviszony: string;
  idoszakok: BelsosIdoszak[];
  /** Visszaesési adat, ha nincs egyetlen időszak sem: ilyenkor a munkanapok
   * döntik el, mely hónapokra várunk TIG-et. */
  elso_munkanap: string | null;
  utolso_munkanap: string | null;
};

export async function getBelsosIdoszakok(employeeId: number): Promise<EmployeeBelsosIdoszakok | null> {
  return apiGet<EmployeeBelsosIdoszakok>(`/api/v1/belsos-idoszakok/${employeeId}`);
}

/** Egy SZÁMLÁZÓ CÉG - az a fél, aki a munkáról a számlát kiállítja, amikor nem
 * maga az ember számláz (lásd backend models/vallalkozas.py). */
export type Vallalkozas = {
  id: number;
  nev: string;
  szekhely: string | null;
  adoszam: string | null;
  kepviselo: string | null;
  nyilvantartasi_szam: string | null;
  email: string | null;
  megbizas_targya: string | null;
  plusz_afa: boolean | null;
  megjegyzes: string | null;
  aktiv: boolean;
  tagok: {
    employee_id: number;
    full_name: string;
    tipus: string | null;
    kezdet: string | null;
    veg: string | null;
    megjegyzes: string | null;
  }[];
  /** Van-e MA élő keretszerződése - ettől függ, kell-e eseti szerződés a tőle
   * jövő emberektől. */
  van_ervenyes_keretszerzodes: boolean;
  keretszerzodes_id: number | null;
};

export async function getVallalkozasok(): Promise<Vallalkozas[]> {
  return (await apiGet<Vallalkozas[]>("/api/v1/vallalkozasok")) ?? [];
}

export async function getVallalkozas(id: number): Promise<Vallalkozas | null> {
  return apiGet<Vallalkozas>(`/api/v1/vallalkozasok/${id}`);
}

/** Egy projekt egy stábtagjánál: ki számláz a munkájáért. */
export type ProjektSzamlazoSor = {
  employee_id: number;
  full_name: string;
  tipus: string | null;
  /** "e12" vagy "v3" - saját magánál "e{employee_id}". */
  szamlazo: string;
  szamlazo_nev: string;
  /** Igaz, ha nem ő maga számláz. */
  felulirva: boolean;
  /** Projekt kiadásként van elszámolva, nem résztvevőként - ilyenkor nem kell
   * tőle sem szerződés, sem TIG (lásd backend models/project_szamlazo.py). */
  kiadaskent_elszamolva: boolean;
  /** Hova és miért került a kiadásba - a jelöléshez kötelező megadni. */
  kiadas_megjegyzes: string | null;
  megjegyzes: string | null;
  javaslatok: { szamlazo: string; nev: string; forras: string }[];
};

/** Egy ember, aki EZEN a projekten számlázó fél lehet. A listát a szerver
 * állítja össze: a "belsős-e" kérdés időszakos, és csak ott van hozzá adat
 * (lásd backend project_szamlazok._valaszthato_emberek). */
export type ValaszthatoSzamlazoFel = { szamlazo: string; nev: string };

export type ProjektSzamlazoNezet = {
  project_id: number;
  project_nev: string | null;
  sorok: ProjektSzamlazoSor[];
  valaszthato_emberek: ValaszthatoSzamlazoFel[];
};

export async function getProjektSzamlazok(projectId: number): Promise<ProjektSzamlazoNezet | null> {
  return apiGet<ProjektSzamlazoNezet>(`/api/v1/projekt-szamlazok/${projectId}`);
}

export type PendingTigProject = {
  project_id: number;
  project_nev: string | null;
  forgatas_datuma: string | null;
  pending_count: number;
};

/** Egy TIG-tétel: kinek a munkáját, melyik projekten igazolja. Egy TIG több
 * ember és több projekt munkáját is fedheti (lásd backend
 * models/performance_certificate.py PerformanceCertificateTetel). */
export type TigTetel = {
  project_id: number;
  project_nev: string | null;
  projektkod: string | null;
  forgatas_datuma: string | null;
  employee_id: number;
  employee_nev: string | null;
  /** Opcionális: nem mindig tudható, egy összevont számlából mi kié. */
  netto_osszeg: number | null;
  megnevezes: string | null;
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
  tetelek: TigTetel[];
};

/** Egy SZÁMLÁZÓ FÉL, akitől TIG kell egy projekten (ember vagy cég). */
export type PendingTigEmployee = {
  /** Az ember azonosítója; cégnél 0. */
  id: number;
  szamlazo: string;
  full_name: string;
  cimke: string;
  /** A projekten hozzá tartozó stábtagok - a TIG alap-tétellistája. */
  lefedettek: TigTetel[];
  vallalkozas_id: number | null;
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

/** Mi mindent tehetünk MÉG rá erre a TIG-re: a fél összes olyan munkája, amiről
 * még nincs papír - más projektekről is. Ez az "egy ember egyben küld be több
 * projektet" eset felülete. */
export async function getNyitottTigTetelek(projectId: number, szamlazo: string): Promise<TigTetel[]> {
  return (
    (await apiGet<TigTetel[]>(`/api/v1/teljesitesi-igazolasok/${projectId}/${szamlazo}/nyitott-tetelek`)) ?? []
  );
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
  /** A számlázó fél: ember VAGY vállalkozás. */
  employee_id: number | null;
  vallalkozas_id: number | null;
  tetelek: { id: number; project_id: number; employee_id: number; netto_osszeg: number | null; megnevezes: string | null }[];
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
  /** Melyik saját cégéről számlázza ezt a hónapot (üres = saját nevében). */
  vallalkozas_id: number | null;
  megjegyzes: string | null;
  netto_osszeg: number | null;
  plusz_afa: boolean | null;
  brutto_osszeg: number | null;
  megbizas_targya: string | null;
  teljesites_datuma: string | null;
  keltezes: string | null;
  /** A számla fizetési határideje és a tényleges utalás napja - a Notionban
   * vezetett belsős TIG-eknél ez a két dátum is megvan. */
  fizetesi_hatarido: string | null;
  utalas_datuma: string | null;
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
  /** A SAJÁT nevére szóló TIG-re kerülő adatok (amikor nem cégről számláz) -
   * a kiküldés előtti áttekintő ezekkel mutatja, mi megy ki a papírra. */
  szekhely: string | null;
  adoszam: string | null;
  /** Kell-e tőle havi TIG. Bejelentett alkalmazottnál NEM: nála a havi teendő
   * csak a fizetés beírása (lásd backend models/employee.py BelsosJogviszony). */
  kell_tig: boolean;
  /** "megbizas" | "alkalmazott" */
  jogviszony: string;
  record: InternalPerformanceCertificate | null;
  /** A munkatárs cégei erre a hónapra - a TIG készítésekor ebből lehet
   * választani, melyikről számlázza (az adatlapján vezethetők fel). */
  cegek: BelsosTigCeg[];
  /** A hónapra érvényes cég - ezzel indul az űrlap, ha még nincs kézzel
   * választva. Több érvényes cégnél üres: olyankor dönteni kell. */
  javasolt_vallalkozas_id: number | null;
  /** A hónap tételei (alapbér + extrák), amikből a TIG összege összeáll -
   * a munkatárs adatlapján vihetők fel (lásd HaviKoltsegek). */
  tetelek: HaviTetel[];
};

/** Egy felajánlható cég a havi TIG-hez. */
export type BelsosTigCeg = {
  vallalkozas_id: number;
  nev: string;
  /** Ami a cég nevére szóló TIG-re rákerül - a kiküldés előtti áttekintő
   * ebből mutatja, mi megy ki a papírra. */
  szekhely: string | null;
  adoszam: string | null;
  kezdet: string | null;
  veg: string | null;
  /** Erre a hónapra érvényes-e az időszaka. */
  ervenyes: boolean;
};

/** Egy ember konkrét hiányossága egy hónapban - ebből derül ki, kinek mit
 * kell még elkészítenie. */
export type BelsosTigTeendo = {
  employee_id: number;
  full_name: string;
  allapot: string | null;
  hianyzik: string;
};

/** Egy hónap "mappája" a Belsős TIG havi áttekintésén. */
export type BelsosTigHonap = {
  ev: number;
  honap: number;
  honap_szoveg: string;
  /** A hónap TIG-jeinek teljesítési (és így leadási) határideje. */
  hatarido: string;
  keses: boolean;
  /** nincs_elkezdve | folyamatban | tig_kesz | lezarva */
  allapot: string;
  osszes: number;
  kesz: number;
  kihagyva: number;
  hianyzo: number;
  brutto_osszesen: number | null;
  teendok: BelsosTigTeendo[];
};

export async function getBelsosTigAttekintes(honapok = 12): Promise<BelsosTigHonap[]> {
  return (await apiGet<BelsosTigHonap[]>(`/api/v1/belsos-tig/attekintes?honapok=${honapok}`)) ?? [];
}

/** Egy belsős, akinél nincs megadva, mettől meddig volt az. */
export type BelsosIdoszakHianyzik = {
  employee_id: number;
  full_name: string;
  /** Mettől soroljuk be a nyomai alapján; üres, ha semmilyen nyoma nincs. */
  nyom_kezdet: string | null;
};

export async function getBelsosIdoszakHianyzik(): Promise<BelsosIdoszakHianyzik[]> {
  return (await apiGet<BelsosIdoszakHianyzik[]>("/api/v1/belsos-tig/idoszak-hianyzik")) ?? [];
}

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
  /** Hány kiküldött szerződést várunk még vissza ALÁÍRVA - a kiküldés
   * önmagában nem zárja le az ügyet (lásd backend
   * subcontractor_contracts.alairasra_varo_csoportok). */
  alairas_varo: number;
  /** Kifizetés: a nem belsős stábtagok (külsős + keretszerződéses) közül
   * hánynak kell fizetni, és hány van még hátra (lásd backend
   * utokovetes_admin.py _kifizetes_state). */
  kifizetes_osszes: number;
  kifizetes_fuggo: number;
  /** Csak akkor igaz, ha a szerződések, az aláírt példányok, a TIG-ek ÉS a
   * kifizetések is mind rendben vannak - ekkor a projekt teljesen le van zárva. */
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
  /** A sorok SZÁMLÁZÓ FELENKÉNT állnak, nem emberenként: egy fél több stábtag
   * munkájáról is szerződhet/igazolhat egyben (lásd backend
   * services/szamlazo.py). A `cimke` ezt írja ki emberi nyelven. */
  szerzodesek: {
    id: number;
    szamlazo: string;
    full_name: string;
    cimke: string;
    lefedettek: LefedettEmber[];
    email: string | null;
    draft: SubcontractorContractDraft | null;
  }[];
  tig_ready: boolean;
  /** Hány kiküldött szerződést várunk még vissza aláírva. */
  alairas_varo: number;
  teljesitesi_igazolasok: {
    id: number;
    szamlazo: string;
    full_name: string;
    cimke: string;
    lefedettek: LefedettEmber[];
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

export type FieldTypeInfo = {
  type: string;
  options?: string[];
  /** Select mezőnél: a listán kívüli, ÚJ érték is megadható helyben (lásd
   * backend entity_registry.NYITOTT_SELECT_MEZOK). */
  allow_new?: boolean;
};

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

/** Egy mező az entitáson - lehet valódi (Notionből áthozott) DB-oszlop vagy
 * admin által létrehozott saját mező (lásd backend entity_fields.py). */
export type EntityField = {
  name: string;
  label: string;
  type: string;
  options: string[] | null;
  /** Saját mező - csak ezek törölhetők véglegesen. */
  custom: boolean;
  /** Eltávolítva a rendszerből (visszahozható). */
  removed: boolean;
  /** Az eltávolításkor az adatait is kiürítettük. */
  data_wiped: boolean;
  removable: boolean;
  reason: string | null;
};

export async function getEntityFields(entityType: string): Promise<EntityField[]> {
  const data = await apiGet<{ entity_type: string; fields: EntityField[] }>(`/api/v1/entity-fields/${entityType}`);
  return data?.fields ?? [];
}

export type PageAccessConfig = {
  employee_id: number;
  page_permissions: Record<string, string[]> | null;
  /** Ha ki van töltve, a felhasználó CSAK ezeket az utómunka-anyagokat látja
   * (külsős vágó fiókja) - null esetén mindet. */
  lathato_deliverable_idk: number[] | null;
};

/** A bejelentkezett felhasználó saját oldal-hozzáférése - null = minden oldalt
 * lát. A middleware és a Sidebar is ez alapján szűr. */
export async function getMyPageAccess(): Promise<string[] | null> {
  const res = await apiGet<{ allowed_pages: string[] | null }>("/api/v1/user-access/me");
  return res?.allowed_pages ?? null;
}

/** Ha nem null, a bejelentkezett felhasználó CSAK ezeket az utómunka-anyagokat
 * láthatja (külsős vágó fiókja) - ilyenkor a felület is leszűkül: a Dashboard
 * a saját anyagát adja teendőként, más oldal nem érhető el (lásd
 * middleware.ts és components/dashboard/KorlatozottDashboard.tsx). */
export async function getMyAnyagKorlat(): Promise<number[] | null> {
  const res = await apiGet<{ lathato_deliverable_idk: number[] | null }>("/api/v1/user-access/me");
  return res?.lathato_deliverable_idk ?? null;
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
  /** Az elsődleges szerepkör. Több is lehet - lásd tovabbi_szerepkorok, és a
   * lib/permissions.ts szerepkorei() segédfüggvényét. */
  role: string;
  tovabbi_szerepkorok?: string[] | null;
  is_active: boolean;
  /** A felület témája ehhez az emberhez ("sotet" / "vilagos"). null = még nem
   * választott, olyankor a sötét alap érvényes (lásd lib/tema.ts). */
  tema?: string | null;
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

// A tényleges megvalósítás a függőség nélküli lib/penz.ts-ben van (kliens-
// komponensek is használják) - itt csak újraexportáljuk, hogy a meglévő
// szerver-oldali hívók importja változatlan maradjon.
export { formatHuf } from "@/lib/penz";

export function formatDate(value: string | null): string {
  if (!value) return "–";
  return value.slice(0, 10);
}

/** Az Utómunka (Deliverable) oldal kapcsolatai - lásd services/deliverable_actions.py. */
export type AssignableEmployee = { id: number; full_name: string };

export async function getAssignableEmployees(): Promise<AssignableEmployee[]> {
  return (await apiGet<AssignableEmployee[]>("/api/v1/deliverables/assignable-employees")) ?? [];
}

/** Egy utalásra váró számla (kiadás vagy TIG) - lásd backend
 * routes/finance.py utalasra_varo. */
export type UtalasraVaroTetel = {
  /** "expense:12" / "kulsos_tig:3" / "belsos_tig:7" - a ZIP-kéréshez. */
  kulcs: string;
  tipus: string;
  megnevezes: string;
  kinek: string | null;
  osszeg: number | null;
  penznem: string;
  hatarido: string | null;
  szamla_db: number;
  link: string | null;
  /** Megjött-e a tétel fedezete (kifizette-e a megrendelő a projektkódot):
   * "fedezett" | "reszben" | "var" | "nincs_projektkod" - lásd backend
   * routes/finance.py _fedezettseg. */
  fedezettseg: string;
  projektkodok: string[];
  fedezetlen_projektkodok: string[];
};

export async function getUtalasraVaro(): Promise<UtalasraVaroTetel[]> {
  return (await apiGet<UtalasraVaroTetel[]>("/api/v1/finance/utalasra-varo")) ?? [];
}

/** Egy utómunka-állapot megjelenése a táblán (lásd backend
 * models/deliverable_status.py). */
export type AllapotBeallitas = {
  allapot: string;
  sorrend: number;
  /** "#rrggbb" vagy null - az oszlop és a kártyái halvány színe. */
  szin: string | null;
  /** Elkészültnek számít: ilyenkor nem lesz belőle lejárt határidő. */
  kesz_allapot: boolean;
};

export async function getAllapotBeallitasok(): Promise<AllapotBeallitas[]> {
  return (await apiGet<AllapotBeallitas[]>("/api/v1/deliverables/allapot-beallitasok")) ?? [];
}

/** Mely mezők látszódjanak a Vágó nézet kártyáin (üres = alapértelmezés:
 * határidő + kiosztott ember). */
export async function getKartyaMezok(): Promise<string[]> {
  const res = await apiGet<{ kartya_mezok: string[] }>("/api/v1/deliverables/kartya-mezok");
  return res?.kartya_mezok ?? [];
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
  /** A mérés indításakor rögzített órabér - ebből számolja a felület a még
   * futó mérés költségét is. Üres, ha a felhasználó nem láthat forintokat. */
  orabere: number | null;
};

export type TimerState = {
  my_running_since: string | null;
  running: TimerRunningEntry[];
  by_employee: TimerEmployeeSummary[];
  total_minutes: number;
  total_cost: number | null;
  /** Munkaidő-sor azonosítója -> a sor költsége. A rögzített összeg gyakran
   * hiányzik (importált mérések), ilyenkor a szerver az időből és az
   * órabérből számolja - lásd deliverable_actions.sor_koltsege. */
  sor_koltsegek: Record<number, number>;
};

export type UtomunkaProjektIdo = {
  project_id: number | null;
  project_nev: string | null;
  projektkod: string | null;
  anyagok_szama: number;
  total_minutes: number;
  total_cost: number | null;
};

export type UtomunkaHonapIdo = {
  ev: number;
  honap: number;
  honap_szoveg: string;
  total_minutes: number;
  total_cost: number | null;
  projektek: UtomunkaProjektIdo[];
};

/** Mennyit vágott ez a munkatárs hónapokra bontva, hónapon belül projektenként. */
/** Egy anyag, amin a munkatárs VALAHA dolgozott (futott rajta az időmérője). */
export type VagottAnyag = {
  id: number;
  projekt_neve: string;
  allapot: string | null;
  projektkod: string | null;
  utoljara: string | null;
  osszes_perc: number;
};

export async function getVagottAnyagok(employeeId: number): Promise<VagottAnyag[]> {
  return (await apiGet<VagottAnyag[]>(`/api/v1/crew/${employeeId}/vagott-anyagok`)) ?? [];
}

/** Egy havi juttatás-tétel: az alapbér vagy egy hozzáadódó extra. */
export type HaviTetel = {
  id: number;
  employee_id: number;
  ev: number;
  honap: number;
  /** alapber | extra | levonando. A "levonando" összege POZITÍV, az előjelet
   * a típus adja (lásd backend models/employee_monthly_item.elojeles_osszeg). */
  tipus: "alapber" | "extra" | "levonando";
  megnevezes: string;
  osszeg: number;
  project_code_id: number | null;
  projektkod: string | null;
  datum: string | null;
  megjegyzes: string | null;
  /** Ha ugyanez a költség pénzügyi kiadás-sorként is szerepel (Notionból
   * mindkettőként bejön), akkor annak az azonosítója - így nem írjuk ki
   * kétszer ugyanazt az összeget. */
  expense_id: number | null;
};

/** Egy munkatárs EGY hónapja teljes egészében - ezt nyitja meg a hónap saját
 * oldala (/belsos-tig/[employeeId]/[ev]/[honap]). */
export type HonapReszletek = {
  employee_id: number;
  full_name: string;
  ev: number;
  honap: number;
  honap_nev: string;
  record: InternalPerformanceCertificate | null;
  tetelek: HaviTetel[];
  alapber: number;
  extra: number;
  /** A levonandó tételek összege POZITÍVAN - az `osszesen`-ből már levonva. */
  levonas: number;
  osszesen: number;
};

export async function getHonapReszletek(
  employeeId: number,
  ev: number,
  honap: number,
): Promise<HonapReszletek | null> {
  return apiGet<HonapReszletek>(`/api/v1/belsos-tig/${employeeId}/${ev}/${honap}/reszletek`);
}

export type HaviKoltseg = {
  ev: number;
  honap: number;
  honap_nev: string;
  tig_id: number | null;
  allapot: string | null;
  netto_osszeg: number | null;
  brutto_osszeg: number | null;
  alapber: number;
  extra: number;
  /** A levonandó tételek összege POZITÍVAN - a nettó összegből már levonva. */
  levonas: number;
  tetelek: HaviTetel[];
};

export type EvesKoltseg = {
  ev: number;
  osszesen: number;
  honapok: HaviKoltseg[];
};

/** Mibe került nekünk ez az ember - évekre csoportosítva, évente összesítve. */
export async function getEmployeeKoltsegek(employeeId: number): Promise<EvesKoltseg[]> {
  return (await apiGet<EvesKoltseg[]>(`/api/v1/belsos-tig/employee/${employeeId}/koltsegek`)) ?? [];
}

export async function getHaviTetelek(employeeId: number, ev: number, honap: number): Promise<HaviTetel[]> {
  return (await apiGet<HaviTetel[]>(`/api/v1/belsos-tig/${employeeId}/${ev}/${honap}/tetelek`)) ?? [];
}

export async function getUtomunkaIdo(employeeId: number): Promise<UtomunkaHonapIdo[]> {
  return (await apiGet<UtomunkaHonapIdo[]>(`/api/v1/crew/${employeeId}/utomunka-ido`)) ?? [];
}

/** Egy projekt, amin a munkatárs részt vett - forgatáson, vágáson vagy
 * mindkettőn (lásd backend routes/crew.py get_reszvetel). */
export type ReszvetelSor = {
  project_id: number;
  project_nev: string | null;
  forgatas_datuma: string | null;
  projektkod: string | null;
  allapot: string | null;
  stabtag: boolean;
  vagott: boolean;
  vagas_percek: number;
  anyagok_szama: number;
};

export async function getReszvetel(employeeId: number): Promise<ReszvetelSor[]> {
  return (await apiGet<ReszvetelSor[]>(`/api/v1/crew/${employeeId}/reszvetel`)) ?? [];
}

/** Egy külsős munkatárs egy projekten végzett munkája: mennyiért csinálta, és
 * hol vannak a hozzá tartozó papírok (szerződés / TIG / számla). */
export type MunkaDokumentum = { cimke: string; url: string };

export type KulsosProjektMunka = {
  project_id: number | null;
  project_nev: string | null;
  forgatas_datuma: string | null;
  projektkod: string | null;
  megbizas_targya: string | null;
  netto: number | null;
  brutto: number | null;
  tig_allapot: string | null;
  szamla_kifizetve: boolean;
  dokumentumok: MunkaDokumentum[];
  /** Nincs erre a projektre külön szerződés, mert álló keretszerződése van. */
  keretszerzodessel: boolean;
};

export type KulsosMunkakOsszesites = {
  projektek: KulsosProjektMunka[];
  osszes_netto: number;
  osszes_brutto: number;
  keretszerzodes_id: number | null;
  keretszerzodes_url: string | null;
};

/** Miken és mennyiért vett részt egy külsős - a TIG-ekből és az eseti
 * szerződésekből összegyűjtve (lásd backend routes/crew.py kulsos_munkak). */
export async function getKulsosMunkak(employeeId: number): Promise<KulsosMunkakOsszesites | null> {
  return apiGet<KulsosMunkakOsszesites>(`/api/v1/crew/${employeeId}/munkak`);
}

export async function getTimerState(deliverableId: number): Promise<TimerState | null> {
  return apiGet<TimerState>(`/api/v1/deliverables/${deliverableId}/timer/state`);
}

/** Egy projekt teljes utómunka-ideje és -költsége, VÁGÓNKÉNT bontva - a
 * szerver számolja, hogy a projekten és az anyagon ugyanaz az összeg álljon
 * (lásd backend routes/projects.py utomunka_osszesites). */
export type ProjektUtomunkaOsszesites = {
  total_minutes: number;
  total_cost: number | null;
  by_employee: TimerEmployeeSummary[];
  /** Az ÉPP FUTÓ mérések - ezeket a felület számolja tovább másodpercenként. */
  futok: { since: string; orabere: number | null }[];
};

export async function getProjektUtomunkaOsszesites(
  projectId: number,
): Promise<ProjektUtomunkaOsszesites | null> {
  return apiGet<ProjektUtomunkaOsszesites>(`/api/v1/projects/${projectId}/utomunka-osszesites`);
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
  /** Melyik "mappába" tartozik a teendő (pl. "Belsős TIG") - a papírozás
   * listáját ez alapján csoportosítja a dashboard (lásd PapirozasFolders). */
  csoport?: string | null;
};

export type MyTasksSummary = {
  deliverables: MyTaskItem[];
  tasks: MyTaskItem[];
  /** A másnapi forgatások diszpói, ha a felhasználó diszpó-felelős (lásd
   * backend models/dispo_responsible.py). */
  diszpok: MyTaskItem[];
  /** A projektek papírozása (belsős/külsős TIG, alvállalkozói és megrendelői
   * szerződés) - csak az Adminisztráció szerepkörűeknek jön vissza (lásd
   * backend routes/dashboard.py _papirozas_tasks). */
  papirozas: MyTaskItem[];
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

// ─────────────────────────────────────────────────────────────────────────────
// Visszatérő kötelezettségek (E-Rezsi, biztosítások) és céges autók
//
// Egy modell szolgálja ki mindkét oldalt: az E-Rezsi az "elofizetes" típusú
// sorokat mutatja, a Biztosítások a többit, az autó lapja pedig a hozzá kötött
// határidőket (lásd backend models/kotelezettseg.py).
// ─────────────────────────────────────────────────────────────────────────────

/** Egy konkrét forduló: ide kerül, hogy PONTOSAN mennyibe került, és ide
 * tölthető fel a számla. */
export type KotelezettsegIdoszak = {
  id: number;
  kotelezettseg_id: number;
  esedekesseg: string;
  /** A ténylegesen levont összeg NETTÓBAN. */
  osszeg: number | null;
  plusz_afa: boolean;
  /** Nettó + áfa - a backend számolja, nem tárolt mező. */
  brutto: number | null;
  penznem: string;
  huf_osszeg: number | null;
  fizetve: boolean;
  megjegyzes: string | null;
  szamla_db: number;
  /** A feltöltött számlák - a darabszám mellett maguk a fájlok, hogy a
   * felületen meg lehessen nyitni és törölni őket. */
  szamlak: DocumentAttachment[];
  /** "Összeg nincs beírva" / "Számla hiányzik", null = kész. */
  hianyzik: string | null;
};

export type Kotelezettseg = {
  id: number;
  nev: string;
  csomag: string | null;
  /** elofizetes | biztositas | forgalmi | berlet | egyeb */
  tipus: string;
  /** havi | eves | egyszeri */
  ciklus: string;
  fordulo_nap: number | null;
  fordulo_honap: number | null;
  kovetkezo_fordulo: string | null;
  kezdet: string | null;
  osztaly: string | null;
  felelos_id: number | null;
  felelos_nev: string | null;
  auto_id: number | null;
  aktiv: boolean;
  /** "Átutalás" | "Készpénz" | "Bankkártya" */
  fizetesi_mod: string | null;
  /** Nettó ár ciklusonként; a bruttót a backend számolja. */
  ar_osszeg: number | null;
  ar_plusz_afa: boolean;
  ar_brutto: number | null;
  ar_penznem: string;
  huf_becsles_honap: number | null;
  huf_becsles_ev: number | null;
  szamla_forras: string | null;
  kartya: string | null;
  megjegyzes: string | null;
  ertesites_napokkal: number;
  kovetkezo_esedekesseg: string | null;
  napok_hatra: number | null;
  /** inaktiv | lejart | hamarosan | rendben | nincs_datum */
  allapot: string;
  nyitott_idoszakok: number;
  /** Hány papír (kötvény, szerződés) van feltöltve magához a kötelezettséghez. */
  papir_db: number;
  idoszakok: KotelezettsegIdoszak[];
};

export async function getKotelezettsegek(params?: { tipus?: string; autoId?: number }): Promise<Kotelezettseg[]> {
  const qs = new URLSearchParams();
  if (params?.tipus) qs.set("tipus", params.tipus);
  if (params?.autoId != null) qs.set("auto_id", String(params.autoId));
  const suffix = qs.toString() ? `?${qs}` : "";
  return (await apiGet<Kotelezettseg[]>(`/api/v1/kotelezettsegek${suffix}`)) ?? [];
}

export type AutoKiadas = {
  id: number;
  megnevezes: string;
  datum: string | null;
  /** Nettó, és a belőle számolt bruttó (`osszeg`) - a Pénzügy a bruttóval számol. */
  netto: number | null;
  plusz_afa: boolean;
  osszeg: number | null;
  penznem: string;
  fizetesi_mod: string | null;
  megjegyzes: string | null;
  kesz: boolean;
  dokumentum_db: number;
};

export type AutoHatarido = {
  id: number;
  nev: string;
  tipus: string;
  kovetkezo_esedekesseg: string | null;
  napok_hatra: number | null;
  allapot: string;
};

export type Auto = {
  id: number;
  rendszam: string;
  megnevezes: string | null;
  tipus: string | null;
  evjarat: number | null;
  km_ora: number | null;
  felelos_id: number | null;
  felelos_nev: string | null;
  aktiv: boolean;
  megjegyzes: string | null;
  hataridok: AutoHatarido[];
  kiadasok: AutoKiadas[];
  koltseg_osszesen: number;
  /** lejart | hamarosan | rendben | nincs */
  hatarido_allapot: string;
};

export async function getAutok(): Promise<Auto[]> {
  return (await apiGet<Auto[]>("/api/v1/autok")) ?? [];
}

// ─────────────────────────────────────────────────────────────────────────────
// Megrendelői kontaktok
//
// Maga az adat a Notion "Megrendelői kontaktok" táblájából jön, és a /contacts
// CRUD végponton szerkeszthető - ez a lista csak összefogja őket az ügyfelük
// nevével és azzal, hány anyagnál van beállítva a kiküldésük.
// ─────────────────────────────────────────────────────────────────────────────

export type MegrendeloiKontakt = {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  client_id: number;
  client_nev: string | null;
  /** Hány utómunka-anyagnál van beállítva, hogy neki is ki kell küldeni. */
  anyagok_szama: number;
};

export async function getMegrendeloiKontaktok(): Promise<MegrendeloiKontakt[]> {
  return (await apiGet<MegrendeloiKontakt[]>("/api/v1/megrendeloi-kontaktok")) ?? [];
}

// ─────────────────────────────────────────────────────────────────────────────
// Vágói visszajelzések
//
// Amit a vágó ír a leforgatott anyagról: három pontszám (1-10) és a szöveges
// rész. A gyűjtő nézet mindegyikhez odateszi, mihez tartozik - anyag, forgatás,
// és kik voltak ott (lásd backend routes/vagoi_visszajelzesek.py).
// ─────────────────────────────────────────────────────────────────────────────

export type VisszajelzesResztvevo = { id: number; full_name: string; email: string | null };

export type VagoiVisszajelzes = {
  id: number;
  letrehozva: string;
  visszajelzo_id: number | null;
  visszajelzo_nev: string | null;
  nyersanyag_felhasznalhatosaga: number | null;
  technikai_helyesseg: number | null;
  kreativ_kepivilag: number | null;
  atlag: number | null;
  megjegyzes: string | null;
  deliverable_id: number;
  deliverable_nev: string | null;
  kesz_anyag_url: string | null;
  project_id: number | null;
  project_nev: string | null;
  forgatas_datuma: string | null;
  resztvevok: VisszajelzesResztvevo[];
  diszpora_kikuldve: string | null;
  /** "uj" | "kikuldve" | "nem_kuldjuk" */
  allapot: string;
  kikuldheto: boolean;
  /** Ha nem küldhető ki, ez mondja meg, miért. */
  kikuldes_akadalya: string | null;
};

/** Egy munkatárs cégei (a VallalkozasTag tagságok az ember felől nézve). */
export type EmberCeg = {
  /** A TAGSÁG azonosítója, nem a cégé - ezzel szerkeszthető a sor. */
  id: number;
  vallalkozas_id: number;
  nev: string;
  aktiv: boolean;
  kezdet: string | null;
  veg: string | null;
  megjegyzes: string | null;
};

export async function getEmberCegei(employeeId: number): Promise<EmberCeg[]> {
  return (await apiGet<EmberCeg[]>(`/api/v1/vallalkozasok/ember/${employeeId}`)) ?? [];
}

export async function getVagoiVisszajelzesek(deliverableId?: number): Promise<VagoiVisszajelzes[]> {
  const qs = deliverableId != null ? `?deliverable_id=${deliverableId}` : "";
  return (await apiGet<VagoiVisszajelzes[]>(`/api/v1/vagoi-visszajelzesek${qs}`)) ?? [];
}

// ─────────────────────────────────────────────────────────────────────────────
// Krumpello - önálló pénzügy (lásd backend routes/krumpello.py)
// ─────────────────────────────────────────────────────────────────────────────

/** Egy nap kassza-zárása. Naponta pontosan egy sor. */
export type KrumpelloNap = {
  id: number;
  datum: string;
  brutto_kp: number | null;
  brutto_kartya: number | null;
  netto_kp: number | null;
  netto_kartya: number | null;
  borravalo_kp: number | null;
  borravalo_kartya: number | null;
  /** Számla nélküli bevétel aznap. */
  extra: number | null;
  megjegyzes: string | null;
  brutto_osszesen: number;
  netto_osszesen: number;
  borravalo_osszesen: number;
};

/** "utalas" | "keszpenz" | "extra" - melyik kasszából ment ki a pénz. */
export type KrumpelloForras = "utalas" | "keszpenz" | "extra";

export type KrumpelloKiadas = {
  id: number;
  forras: KrumpelloForras;
  kedvezmenyezett: string;
  datum: string | null;
  megnevezes: string | null;
  netto: number | null;
  afa: number | null;
  brutto: number | null;
  megjegyzes: string | null;
};

export type KrumpelloDolgozo = {
  id: number;
  nev: string;
  alap_orabar: number | null;
  aktiv: boolean;
  megjegyzes: string | null;
  employee_id: number | null;
  ora_osszesen: number;
  fizetes_osszesen: number;
  borravalo_osszesen: number;
  utolso_nap: string | null;
};

export type KrumpelloMunkaora = {
  id: number;
  dolgozo_id: number;
  dolgozo_nev: string;
  datum: string;
  ora: number | null;
  orabar: number | null;
  fizetes: number | null;
  borravalo: number | null;
  megjegyzes: string | null;
};

export type KrumpelloOsszesito = {
  bevetel: {
    brutto_kp: number;
    brutto_kartya: number;
    brutto: number;
    netto_kp: number;
    netto_kartya: number;
    netto: number;
    borravalo_kp: number;
    borravalo_kartya: number;
    borravalo: number;
    extra: number;
  };
  kiadas_utalas: { netto: number; afa: number; brutto: number };
  kiadas_keszpenz: { netto: number; afa: number; brutto: number };
  kiadas_extra: number;
  szamla_egyenleg_netto: number;
  szamla_egyenleg_brutto: number;
  keszpenz_egyenleg_netto: number;
  keszpenz_egyenleg_brutto: number;
  extra_bevetel: number;
  /** Extra bevétel − extra kiadás. Negatív = több számlázatlan pénz ment ki. */
  extra_egyenleg: number;
  munkaora: number;
  munkaber: number;
  munkaber_borravalo: number;
};

function krumpelloIdoszak(tol?: string, ig?: string): string {
  const p = new URLSearchParams();
  if (tol) p.set("tol", tol);
  if (ig) p.set("ig", ig);
  const qs = p.toString();
  return qs ? `?${qs}` : "";
}

export async function getKrumpelloOsszesito(tol?: string, ig?: string): Promise<KrumpelloOsszesito | null> {
  return apiGet<KrumpelloOsszesito>(`/api/v1/krumpello/osszesito${krumpelloIdoszak(tol, ig)}`);
}

export async function getKrumpelloNapok(tol?: string, ig?: string): Promise<KrumpelloNap[]> {
  return (await apiGet<KrumpelloNap[]>(`/api/v1/krumpello/napok${krumpelloIdoszak(tol, ig)}`)) ?? [];
}

export async function getKrumpelloKiadasok(tol?: string, ig?: string): Promise<KrumpelloKiadas[]> {
  return (await apiGet<KrumpelloKiadas[]>(`/api/v1/krumpello/kiadasok${krumpelloIdoszak(tol, ig)}`)) ?? [];
}

export async function getKrumpelloDolgozok(tol?: string, ig?: string): Promise<KrumpelloDolgozo[]> {
  return (await apiGet<KrumpelloDolgozo[]>(`/api/v1/krumpello/dolgozok${krumpelloIdoszak(tol, ig)}`)) ?? [];
}

export async function getKrumpelloMunkaorak(tol?: string, ig?: string): Promise<KrumpelloMunkaora[]> {
  return (await apiGet<KrumpelloMunkaora[]>(`/api/v1/krumpello/munkaorak${krumpelloIdoszak(tol, ig)}`)) ?? [];
}

/** Látja-e a bejelentkezett ember a Krumpellót? A HYPE OS fejlécében ülő
 * kapcsoló ezt kérdezi - jog nélkül a kapcsoló meg sem jelenik. */
export async function getKrumpelloHozzaferes(): Promise<boolean> {
  const res = await apiGet<{ van_hozzaferes: boolean }>("/api/v1/krumpello/hozzaferes");
  return res?.van_hozzaferes ?? false;
}
