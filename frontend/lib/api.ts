import { cookies } from "next/headers";
import type { HataridoAllas } from "@/lib/hatarido";

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

/** A bejelentkezett felhasználó megnyerte az előző havi vágói játékot - a
 * dashboard a kihirdetéstől 5 napig ünneplő kártyát mutat neki ebből. */
export type VagoiJatekNyertes = {
  ev: number;
  honap: number;
  honap_nev: string;
  pont: number;
  nyeremeny: string | null;
  kep_url: string | null;
};

export type DashboardSummary = {
  mai_forgatasok: number;
  aktiv_project_codeok: number;
  equipment_utkozesek: number;
  havi_bevetel: number;
  upcoming_events: UpcomingEvent[];
  revenue_trend: RevenueMonth[];
  alerts: DashboardAlerts;
  vagoi_jatek_nyertes: VagoiJatekNyertes | null;
  /** Admin vagy, és a folyó hónap vágói-játék nyereménye még nincs kihirdetve. */
  vagoi_jatek_nyeremeny_bekeres: boolean;
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
  /** Bevétel, összes költség (kiadások + utómunka) és a kettő különbsége -
   * a backend számolja (lásd models/project_code.py). */
  bevetel: number;
  /** Devizás munkánál: MIBŐL lett a fenti forint. A bevétel mindenhol forint,
   * de egy át NEM váltott összeg ugyanúgy néz ki, mint egy szokásos forintos -
   * ezért írjuk ki mellé az eredetit (lásd backend
   * models/project_code.bevetel_deviza). Az árfolyam hiányozhat: olyankor
   * nincs forintos bevétel, és épp ezt kell látni. */
  bevetel_deviza: { penznem: string; netto: number; arfolyam: number | null } | null;
  becsult_profit: number;
  osszes_koltseg: number;
  /** Az összes költség négy része (az összegük pontosan az osszes_koltseg):
   * a külsős közreműködők kifizetései, minden más kiadás-sor, a vágás
   * (utómunka) és a belsősök napidíja. Az utóbbinak egyedül nincs
   * kiadás-sora a Pénzügyekben (a havi bér a hónap végén megy be egyben). */
  kulsos_koltseg: number;
  egyeb_kiadas: number;
  vagas_koltseg: number;
  belsos_munka_koltseg: number;
  datum: string | null;
  /** ELMARADT az esemény (az állapota szerint) - ilyenkor semmilyen papírt
   * nem kérünk rá: se szerződést, se TIG-et, se számlát. Ami nem történt meg,
   * arról nincs mit igazolni (lásd backend
   * models/project_code.esemeny_elmaradt). */
  elmaradt: boolean;
  /** MIÉRT ennyi a vállalási ár (pl. "beszámítva X fizetésébe"). Egy
   * magyarázat nélküli 0 Ft a legfélrevezetőbb: nem látszik, elfelejtették-e
   * beírni vagy tényleg így volt. */
  vallalasi_ar_magyarazat: string | null;
  /** Hol tart a papírozás és a pénz: kell-e egyáltalán papír, van-e lezárt
   * eseti szerződés és TIG, megérkezett-e a bevétel (lásd backend
   * models/project_code.py). */
  papir_kell: boolean;
  /** Fedi-e élő megrendelői keretszerződés: ilyenkor eseti szerződés nem
   * kell, csak TIG. */
  keret_fedi: boolean;
  /** KIVEL van a keretszerződés - a puszta "keretszerződés alatt" nem
   * ellenőrizhető (lásd backend models/project_code.keretszerzodes_neve). */
  keretszerzodes_neve: string | null;
  szerzodes_kell: boolean;
  szerzodes_kesz: boolean;
  tig_kesz: boolean;
  /** KÉSZ, de NINCS papírja: tudatosan kihagytuk. A `szerzodes_kesz` ilyenkor
   * is igaz (a "Kihagyva" lezárt állapot) - de a listának külön kell mondania,
   * mert a "Szerződés megvan" egy kihagyott szerződésre olyan állítás, amit
   * később senki nem tud igazolni (lásd backend
   * models/project_code.szerzodes_kihagyva). */
  szerzodes_kihagyva: boolean;
  tig_kihagyva: boolean;
  /** KÉSZNEK számít, de csak azért, mert ki van küldve - aláírva még nem
   * jött vissza, és semmilyen más úton nincs lezárva (lásd backend
   * models/project_code.szerzodes_kikuldve_varjuk). */
  szerzodes_kikuldve_varjuk: boolean;
  tig_kikuldve_varjuk: boolean;
  /** Lesz-e SZÁMLA erről a munkáról. Ahol nincs (kihagytuk, papír nélkül van
   * elszámolva, vagy elmaradt), ott a kihagyott szerződés és TIG nem
   * hiányosság, hanem következmény - nincs is mihez elkészíteni őket (lásd
   * backend services/megrendeloi_szamla.szamlat_varunk). */
  szamla_kell: boolean;
  bevetel_kifizetve: boolean;
  /** MENNYI IDŐ van a kifizetésig, vagy mennyivel csúszott - a
   * LEGSÜRGŐSEBB feltöltött számla szerint (lásd lib/hatarido.ts). Fizetési
   * határidő nélkül null. */
  hatarido_allas: HataridoAllas | null;
  /** UGYANEZ, MINDEGYIK feltöltött számlához külön - osztott számlázásnál
   * (több számla egy projektkódon) ebből látszik mindegyik saját állapota. */
  szamla_hataridok: HataridoAllas[];
  /** Mire szólt a projekt, hol volt, és mit jegyeztek fel a dátumához. */
  project_nev: string | null;
  helyszin: string | null;
  datum_megjegyzes: string | null;
};

export type Project = {
  id: number;
  nev: string;
  project_code_id: number;
  forgatas_datuma: string | null;
  forgatas_datuma_vege: string | null;
  /** A forgatás TÉNYLEGES (megjelenítendő) záró napja - a backend számítja a
   * kézi értékből és a forrásonkénti (naptár/Notion) tükör-mezőkből, lásd
   * backend schemas/project.veg_datum. A felület mindenhol EZT használja a
   * több naposság eldöntésére, ne a nyers forgatas_datuma_vege-t. */
  veg_datum: string | null;
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
  /** Belsős napidíj: mennyibe kerül a cégnek egy munkanapja. A projekt
   * önköltségébe számít bele (lásd backend services/belsos_koltseg.py), de
   * NEM lesz belőle kiadás-sor. Vágóknál nincs jelentése: ők órabérben
   * dolgoznak. */
  napi_dij: number | null;
  /** Hány napra van szerződve egy HÓNAPBAN (belsős). Ennyi nap van benne a
   * havi bérében; ami e fölött van, az a plusz nap díján számol a projektek
   * önköltségébe (lásd backend services/munkanap_szamlalo.py). Üresen: nincs
   * korlát. */
  szerzodott_napok: number | null;
  /** A szerződött napokon FELÜLI nap napidíja. Üresen a plusz nap is a rendes
   * napidíjon számol. */
  plusz_nap_napi_dij: number | null;
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
  /** Mi ez a fájl. A "gyartas" a projekt Gyártás komment dobozáé (lásd
   * backend services/attachments.KATEGORIAK). */
  kategoria: "szerzodes" | "tig" | "szamla" | "diszpo" | "gyartas" | "egyeb";
  filename: string;
  url: string;
  content_type: string | null;
  meret_bajt: number | null;
  created_at: string;
  /** Csak "szamla" kategóriánál értelmezett - lásd
   * components/DokumentumFeltoltes.tsx fizetesiAllapot módja. */
  fizetesi_hatarido: string | null;
  kifizetve_datuma: string | null;
  /** Ennek a KONKRÉT számlának a nettó összege (ha meg lett adva) - lásd
   * backend services/megrendeloi_szamla.jelold_szamlat_kifizetettnek. */
  netto: number | null;
  plusz_afa: boolean | null;
  bevetelbe_ne_keruljon: boolean;
  bevetel_kihagyas_oka: string | null;
  /** Kifizetve, de nem valódi tranzakcióval (beszámítás, valakinek a
   * fizetéséből levonva…) - ilyenkor `kifizetve_datuma` üres marad. */
  tranzakcio_nelkul_lezarva: boolean;
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

export type HypeTodoItem = {
  id: number;
  feladat: string;
  allapot: string | null;
  leiras: string | null;
  kategoria: string | null;
  hatarido: string | null;
  csatolando_link: string | null;
  letrehozas_idopontja: string | null;
  aki_felvezette_id: number | null;
  ellenorzes_felelos_id: number | null;
  aki_ellenorizte_id: number | null;
  felelos_employee_ids: number[];
};

export type AgiTodoItem = {
  id: number;
  feladat: string;
  allapot: string | null;
  ugyfel: string | null;
  hatarido: string | null;
  leiras: string | null;
  kovetkezo_lepes: string | null;
  csatolt_link: string | null;
};

export type FloraFeladat = {
  id: number;
  megnevezes: string;
  allapot: string | null;
  cimke: string | null;
  hatarido: string | null;
  kesz_anyag_linkje: string | null;
  leiras: string | null;
  letrehozas_idopontja: string | null;
  felelos_id: number | null;
  felvezette_id: number | null;
};

export type Expense = {
  id: number;
  /** A felületen "Cégnév": kinek fizettünk (lásd backend models/finance). */
  megnevezes: string;
  /** A felületen "Megnevezés": mire ment a kiadás. */
  kiadas_leiras: string | null;
  /** "+ÁFA" jelölés ("igen" = van) és a százaléka - a bruttót a szerver
   * számolja belőlük (lásd backend routes/finance._afa_brutto). */
  plusz_afa: string | null;
  afa_szazalek: number | null;
  tipus: string | null;
  netto: number | null;
  brutto: number | null;
  penznem: string;
  kesz: boolean;
  kifizetes_modja: string | null;
  hozzaadas_a_kiadasokhoz: boolean | null;
  /** MIBŐL lett a forint összeg. A `netto`/`brutto` MINDIG forint - ha a
   * tételt euróban/dollárban vezették fel, itt marad meg, hogyan (lásd backend
   * services/penznem.py). `null` = eredetileg is forint volt. */
  eredeti_penznem: string | null;
  eredeti_netto: number | null;
  eredeti_brutto: number | null;
  arfolyam: number | null;
};

export type Revenue = {
  id: number;
  project_code_id: number;
  bevetel_formaja: string | null;
  /** Beleszámít-e az ÉVES bevételbe (null = igen). A "nem volt tranzakció"
   * formájú sorok e mező nélkül is kimaradnak - lásd bevetelBeleszamit(). */
  beleszamit_a_bevetelekbe: boolean | null;
  netto: number | null;
  brutto: number | null;
  penznem: string;
  /** HOGYAN jött be a pénz (Készpénz / Átutalás) - ebből számol a kassza
   * egyenlege (lásd backend services/fizetesi_mod.py). */
  fizetes_modja: string | null;
  fizetes_datuma: string | null;
  szamla_kiallitva_datuma: string | null;
  /** MIBŐL lett a forint összeg. A `netto`/`brutto` MINDIG forint - ha a
   * tételt euróban/dollárban vezették fel, itt marad meg, hogyan (lásd backend
   * services/penznem.py). `null` = eredetileg is forint volt. */
  eredeti_penznem: string | null;
  eredeti_netto: number | null;
  eredeti_brutto: number | null;
  arfolyam: number | null;

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
  /** Kikre van kiosztva - TÖBB ember is lehet (a kanonikus forrás, lásd
   * backend models/deliverable.kiosztottak; az assigned_to_employee_id csak
   * az első kiosztott tükre). */
  kiosztott_employee_ids: number[];
  kiosztott_nevek: string[];
  project_id: number | null;
  vinyok: string[] | null;
  /** A vinyó-nézet keresőjéhez - a lista-séma is hozza őket. */
  projektkod_szoveg?: string | null;
  esemeny_neve?: string | null;
  /** A vinyó-nézet kártya-címkéje: az archiválás állapota. */
  archivalas?: string | null;
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

/** Egy projektkód annyira, amennyi egy címkéhez/választóhoz kell.
 *
 * A teljes ProjectCode lista minden kódra kiszámolja a költségeket, a
 * profitot és a papír-állást (forgatások, stáb, utómunka, mérések, kiadások,
 * TIG-ek) - 800 kódnál ez másodpercek és fél megabájt. A legtöbb oldalnak
 * ebből egyetlen dolog kell: melyik id melyik kódot jelenti. */
export type ProjectCodeOption = Pick<
  ProjectCode,
  "id" | "projektkod" | "project_nev" | "client_id" | "esemeny_allapota"
>;

/** A projektkódok CSAK a nevükkel (lásd backend /project-codes/valaszthato).
 * Ezt használja minden oldal, ami nem a projektkód-listát mutatja. */
export async function getProjectCodeOptions(): Promise<ProjectCodeOption[]> {
  return (await apiGet<ProjectCodeOption[]>("/api/v1/project-codes/valaszthato")) ?? [];
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

export async function getHypeTodoItems(limit = 5000): Promise<HypeTodoItem[]> {
  return (await apiGet<HypeTodoItem[]>(`/api/v1/hype-todo?limit=${limit}`)) ?? [];
}

export async function getFloraFeladatok(limit = 5000): Promise<FloraFeladat[]> {
  return (await apiGet<FloraFeladat[]>(`/api/v1/flora?limit=${limit}`)) ?? [];
}

/** Egy hozzászólás egy FLÓRA feladat oldalán - ugyanaz a chat-minta, mint az
 * Utómunkánál; a Notion-import a kártyák Notion-beli kommentjeit is ide
 * hozza (lásd backend routes/flora.py, notion_import/importers_wave4.py). */
export type FloraKomment = {
  id: number;
  flora_feladat_id: number;
  employee_id: number;
  employee_name: string;
  body: string;
  created_at: string;
};

export async function getFloraKommentek(floraId: number): Promise<FloraKomment[]> {
  return (await apiGet<FloraKomment[]>(`/api/v1/flora/${floraId}/comments`)) ?? [];
}

/** Egy hozzászólás egy HYPE TO-DO feladat oldalán (lásd backend
 * routes/hype_todo.py) - a Notion-import a Notion-beli kommenteket is ide
 * hozza. */
export type HypeTodoKomment = {
  id: number;
  hype_todo_id: number;
  employee_id: number;
  employee_name: string;
  body: string;
  created_at: string;
};

export async function getHypeTodoKommentek(todoId: number): Promise<HypeTodoKomment[]> {
  return (await apiGet<HypeTodoKomment[]>(`/api/v1/hype-todo/${todoId}/comments`)) ?? [];
}

export async function getAgiTodoItems(limit = 5000): Promise<AgiTodoItem[]> {
  return (await apiGet<AgiTodoItem[]>(`/api/v1/agi-todo?limit=${limit}`)) ?? [];
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

/** Egy KONKRÉT dokumentum, amit aláírva visszavárunk: maga a keretszerződés
 * vagy annak egy módosítása. Azért dokumentumonként külön, mert mindegyik
 * külön papír, külön aláírással - egyetlen "aláírásra vár" jelölésből sosem
 * derülne ki, melyiket várjuk. */
export type VartAlairas = {
  fajta: string;
  /** A módosítás azonosítója (a keretszerződésnél null) - ide kell feltölteni. */
  modositas_id: number | null;
  keltezes: string | null;
  kikuldve: string | null;
  file_url: string | null;
};

export type KeretAlairasAllapot = {
  contract_id: number;
  szerzodes_alairva: boolean;
  szerzodes_kikuldve: boolean;
  modositas_db: number;
  varunk: VartAlairas[];
};

export type KeretModositas = {
  id: number;
  contract_id: number;
  keltezes: string | null;
  allapot: string | null;
  file_url: string | null;
  alairt_file_url: string | null;
  email: string | null;
  megbizas_targya: string | null;
  szerzodes_letrejotte: string | null;
  kikuldve: string | null;
  kikuldte: string | null;
  level_szoveg: string | null;
  megjegyzes: string | null;
};

/** MINDEN álló keretszerződés aláírás-állapota, egy hívásban - a
 * Keretszerződések oldal soronként ebből írja ki, mit várunk még. */
export async function getKeretAlairasAllapot(): Promise<KeretAlairasAllapot[]> {
  return (await apiGet<KeretAlairasAllapot[]>("/api/v1/contracts/keretszerzodesek/alairas-allapot")) ?? [];
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
  /** MELYIK projekteket fedi ez az egy papír - egy szerződés több forgatási
   * napra is szólhat. Egynél több elemnél a felület kiírja, hogy közös. */
  projektek: string[];
};

export async function getAllContractsForProject(projectId: number): Promise<ElkeszultSzerzodes[]> {
  return (await apiGet<ElkeszultSzerzodes[]>(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/all`)) ?? [];
}

// ─── PROJEKTKÓD-SZINTŰ alvállalkozói szerződés (forgatás nélkül) ───────────
//
// Ugyanaz a papír-életciklus, mint a forgatáshoz kötött szerződésnél, csak a
// projektkódhoz kötve (lásd backend subcontractor_contracts.py "projektkód-
// szintű ág") - annak, aki egy projekt-kiadáson alvállalkozóként van
// megjelölve, de nincs hozzá konkrét forgatás (tisztán ügynökségi feladat).

export type PendingSubcontractorProjectCode = {
  project_code_id: number;
  projektkod: string;
  project_nev: string | null;
  pending_count: number;
};

/** Egyszerűbb, mint PendingSubcontractorEmployee: nincs "lefedettek" tétel-
 * lista, mert egy projektkódon mindenki önmagáért számláz. */
export type PendingSubcontractorProjectCodeEmployee = {
  id: number;
  szamlazo: string;
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

export type PendingSubcontractorProjectCodeDetail = {
  project_code_id: number;
  projektkod: string;
  project_nev: string | null;
  pending: PendingSubcontractorProjectCodeEmployee[];
};

export async function getPendingSubcontractorProjectCodes(): Promise<PendingSubcontractorProjectCode[]> {
  return (await apiGet<PendingSubcontractorProjectCode[]>("/api/v1/alvallalkozoi-szerzodesek/projektkodok")) ?? [];
}

export async function getPendingSubcontractorsForProjectCode(
  projectCodeId: number,
): Promise<PendingSubcontractorProjectCodeDetail | null> {
  return apiGet<PendingSubcontractorProjectCodeDetail>(
    `/api/v1/alvallalkozoi-szerzodesek/projektkodok/${projectCodeId}`,
  );
}

export async function getAllContractsForProjectCode(projectCodeId: number): Promise<ElkeszultSzerzodes[]> {
  return (
    (await apiGet<ElkeszultSzerzodes[]>(`/api/v1/alvallalkozoi-szerzodesek/projektkodok/${projectCodeId}/all`)) ?? []
  );
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
  /** Mennyiért vállalja ezt a napot (nettó), és mi van benne - a diszpó
   * írásakor, a stábtag felvételekor lebeszélt díj. Ebből nyílik meg a
   * szerződés és a TIG piszkozata (lásd backend services/megbeszelt_dij.py). */
  megbeszelt_dij: number | null;
  dij_megjegyzes: string | null;
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

/** Egy projektkód TÉTELES költségbontása (lásd backend
 * services/projektkod_bontas.py). A fejléc négy összege megmondja, mennyi ment
 * el; ez azt, hogy mire. */
export type ProjektkodBontas = {
  projektek: {
    id: number;
    nev: string | null;
    forgatas_datuma: string | null;
    kulsos_koltseg: number;
    belsos_koltseg: number;
    vagas_koltseg: number;
    osszesen: number;
  }[];
  utomunkak: {
    id: number;
    nev: string | null;
    project_id: number | null;
    vago_nev: string | null;
    /** Mennyi ideig vágtuk - a munkaidő-sorokból. */
    percek: number;
    koltseg: number;
  }[];
  kiadasok: {
    id: number;
    megnevezes: string | null;
    kinek: string | null;
    datum: string | null;
    netto: number | null;
    osszeg: number;
    kifizetve: boolean;
    /** Melyik fejléc-részbe számít: "kulsos" vagy "egyeb". */
    resz: string;
  }[];
};

export async function getProjektkodBontas(projectCodeId: number): Promise<ProjektkodBontas | null> {
  return apiGet<ProjektkodBontas>(`/api/v1/project-codes/${projectCodeId}/bontas`);
}

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
  /** A fél ESETI SZERZŐDÉSE ezen a projekten - ugyanarról a munkáról szól,
   * ezért amit oda beírtak (megbízás tárgya, összeg, teljesítés ideje), azzal
   * indul a TIG űrlapja. Előtöltés, nem kényszer: minden mező szerkeszthető. */
  szerzodes: TigSzerzodesElotoltes | null;
};

/** Amit a fél eseti szerződéséből átveszünk a TIG-hez. */
export type TigSzerzodesElotoltes = {
  allapot: string | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  megbizas_targya: string | null;
  netto_osszeg: number | null;
  teljesites_szoveg: string | null;
  plusz_afa: boolean | null;
  tetelek: TigTetel[];
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
  /** Akikről még NEM készíthető TIG (nincs meg az eseti szerződésük) - de
   * KIHAGYNI már most is lehet őket: a három lépés kihagyása független
   * egymástól (lásd backend skip_tig). */
  szerzodesre_varo: PendingTigEmployee[];
};

export async function getPendingTigProjects(): Promise<PendingTigProject[]> {
  return (await apiGet<PendingTigProject[]>("/api/v1/teljesitesi-igazolasok")) ?? [];
}

export async function getPendingTigForProject(projectId: number): Promise<PendingTigProjectDetail | null> {
  return apiGet<PendingTigProjectDetail>(`/api/v1/teljesitesi-igazolasok/${projectId}`);
}

// ─── PROJEKTKÓD-SZINTŰ TIG (forgatás nélkül) ────────────────────────────────
// Lásd a szerződés-oldal azonos című szakaszát fentebb - ugyanaz a minta.

export type PendingTigProjectCode = {
  project_code_id: number;
  projektkod: string;
  project_nev: string | null;
  pending_count: number;
};

export type PendingTigProjectCodeEmployee = {
  id: number;
  szamlazo: string;
  full_name: string;
  email: string | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  megbizas_targya: string | null;
  plusz_afa: boolean | null;
  draft: TigDraft | null;
  szerzodes: TigSzerzodesElotoltes | null;
};

export type PendingTigProjectCodeDetail = {
  project_code_id: number;
  projektkod: string;
  project_nev: string | null;
  pending: PendingTigProjectCodeEmployee[];
  tig_ready: boolean;
  szerzodesre_varo: PendingTigProjectCodeEmployee[];
};

export async function getPendingTigProjectCodes(): Promise<PendingTigProjectCode[]> {
  return (await apiGet<PendingTigProjectCode[]>("/api/v1/teljesitesi-igazolasok/projektkodok")) ?? [];
}

export async function getPendingTigForProjectCode(projectCodeId: number): Promise<PendingTigProjectCodeDetail | null> {
  return apiGet<PendingTigProjectCodeDetail>(`/api/v1/teljesitesi-igazolasok/projektkodok/${projectCodeId}`);
}

export async function getAllTigForProjectCode(projectCodeId: number): Promise<PerformanceCertificate[]> {
  return (
    (await apiGet<PerformanceCertificate[]>(`/api/v1/teljesitesi-igazolasok/projektkodok/${projectCodeId}/all`)) ?? []
  );
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
  /** A projektkód-szintű (forgatás nélküli) ágon `project_id` üres, helyette
   * `project_code_id` mutatja, melyik projektkódhoz tartozik a TIG - lásd
   * getAllTigForProjectCode. */
  project_id: number | null;
  project_code_id: number | null;
  /** A számlázó fél: ember VAGY vállalkozás. */
  employee_id: number | null;
  vallalkozas_id: number | null;
  /** Kinek a munkáját, MELYIK projekten igazolja. Egy papír több forgatást is
   * fedhet (több nap egy számlán) - a projekt adatai ezért itt is kellenek. */
  tetelek: {
    id: number;
    project_id: number;
    employee_id: number;
    netto_osszeg: number | null;
    megnevezes: string | null;
    project_nev: string | null;
    projektkod: string | null;
    forgatas_datuma: string | null;
  }[];
  allapot: string | null;
  /** Miért hagytuk ki, ha a fenti `allapot` "Kihagyva". */
  kihagyas_oka: string | null;
  file_url: string | null;
  ceg_neve: string | null;
  netto_osszeg: number | null;
  plusz_afa: boolean | null;
  brutto_osszeg: number | null;
  /** Egy TIG-hez több számla is tartozhat, egyenként törölhetően. */
  invoices: PerformanceCertificateInvoice[];
  /** A számla két dátuma: meddig kell fizetni (a feltöltéskor adjuk meg), és
   * mikor utaltuk el ténylegesen (a kifizetve jelöléskor). */
  fizetesi_hatarido: string | null;
  utalas_datuma: string | null;
  szamla_kifizetve: boolean;
  /** A számla-lépés kihagyva: nem várunk se számlát, se kifizetést - és hogy
   * miért (lásd backend routes/performance_certificates.skip_szamla). */
  szamla_kihagyva: boolean;
  szamla_kihagyas_oka: string | null;
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
    /** A SZÁMLA-lépés kihagyva: ide nem jön se számla, se kifizetés. */
    szamla_kihagyva: boolean;
    /** Készíthető-e már TIG erről a félről (megvan a szerződése, vagy keret
     * fedi). Ahol nem, ott csak a KIHAGYÁS érhető el. */
    tig_keszitheto: boolean;
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

/** Egy projektkód, amin FORGATÁS NÉLKÜL van alvállalkozói kiadás - lásd
 * backend utokovetes_admin.py "projektkód-szintű ág". Ugyanazok a mezők,
 * mint UtokovetesOverview-én (szándékosan azonos nevekkel - lásd
 * lib/utokovetesProjektkod.ts). */
export type UtokovetesOverviewProjectCode = {
  project_code_id: number;
  projektkod: string;
  project_nev: string | null;
  szerzodes_osszes: number;
  szerzodes_fuggo: number;
  tig_ready: boolean;
  tig_osszes: number;
  tig_fuggo: number;
  alairas_varo: number;
  kifizetes_osszes: number;
  kifizetes_fuggo: number;
  kesz: boolean;
};

export async function getUtokovetesOverviewProjectCodes(): Promise<UtokovetesOverviewProjectCode[]> {
  return (await apiGet<UtokovetesOverviewProjectCode[]>("/api/v1/utokovetes/projektkodok")) ?? [];
}

export async function getRates(limit = 5000): Promise<Rate[]> {
  return (await apiGet<Rate[]>(`/api/v1/rates?limit=${limit}`)) ?? [];
}

export type MonthlyFinance = { month: string; bevetel: number; kiadas: number };

export type OutstandingProject = {
  project_code_id: number;
  projektkod: string;
  /** A MUNKA neve (nem az ügyfélé) - lásd backend routes/finance.py. */
  projekt_nev: string | null;
  kintlevo_osszeg: number;
  legkorabbi_hatarido: string | null;
  lejart: boolean;
};

export type PaymentMethodBreakdown = { kifizetes_modja: string | null; osszeg: number };

/** Az összegek NETTÓBAN (lásd backend services/elszamolas.py) - a `_brutto`
 * végű mezők a tájékoztató bruttó értékek. */
export type FinanceSummary = {
  ytd_bevetel: number;
  ytd_kiadas: number;
  ytd_profit: number;
  ytd_bevetel_brutto: number;
  ytd_kiadas_brutto: number;
  osszes_kintlevoseg: number;
  kintlevo_projektek_szama: number;
  havi_trend: MonthlyFinance[];
  kintlevo_projektek: OutstandingProject[];
  ytd_kiadas_fizetesi_mod_szerint: PaymentMethodBreakdown[];
  kassza: Kassza;
};

/** Egy hónap készpénz-mozgása és a hónap végi egyenleg. */
export type KasszaHavi = { month: string; be: number; ki: number; egyenleg: number };

/** Mennyi készpénz van a kasszában - BRUTTÓBAN, mert egy doboz pénz nem tud
 * nettó lenni (lásd backend services/fizetesi_mod.py). */
export type Kassza = {
  egyenleg: number;
  osszes_be: number;
  osszes_ki: number;
  idei_be: number;
  idei_ki: number;
  /** Az idei készpénzes kiadás kettéosztva: van-e mögötte SZÁMLA (lásd backend
   * services/bizonylat.py). A számla nélküli készpénzes kiadás a könyvelésben
   * nem elszámolható költség - az a szám teendő, nem statisztika. */
  idei_ki_szamlaval: number;
  idei_ki_szamla_nelkul: number;
  idei_ki_szamlaval_db: number;
  idei_ki_szamla_nelkul_db: number;
  havi: KasszaHavi[];
  /** Hány KIFIZETETT tételen nincs megjelölve a fizetési mód - amíg ez nem
   * nulla, az egyenleg csak közelítés. */
  jeloletlen_kiadas: number;
  jeloletlen_bevetel: number;
};

export async function getFinanceSummary(): Promise<FinanceSummary | null> {
  return apiGet<FinanceSummary>("/api/v1/finance/summary");
}

/** Egy készpénz-mozgás a KP forgalom naplóban (lásd backend
 * services/kassza.py). */
export type KpNaploSor = {
  /** A FORRÁS rekord azonosítója - a `forras` mezővel együtt azonosít. */
  id: number;
  /** kiadas | bevetel | kp_forgalom */
  forras: string;
  datum: string | null;
  megnevezes: string;
  projektkod: string | null;
  be: number;
  ki: number;
  /** A kassza egyenlege EZ UTÁN a sor után, időrendben számolva. */
  egyenleg: number;
  /** Van-e mögötte SZÁMLA - ez dönti el, a legális vagy a fekete oldalra
   * kerül-e. */
  van_szamla: boolean;
  /** ÁTVEZETÉS: a saját pénzünk mozgatása bankszámla és kassza közt
   * (ATM-felvétel). A kassza egyenlegébe beleszámít, a legális/fekete
   * bontásba nem. */
  atvezetes: boolean;
  href: string | null;
  /** A NYERS irány-mező - csak "kp_forgalom" forrásnál van értéke (bevetel /
   * kiadas / fedezet). */
  forgalom: string | null;
  /** Feltöltött bizonylat(ok) - csak "kp_forgalom" forrásnál lehet. */
  csatolmanyok: DocumentAttachment[];
  /** A "Projekt kiadás" mező NYERS azonosítója - csak "kp_forgalom"
   * forrásnál van értéke. */
  project_code_id: number | null;
  /** Devizás felvezetés nyoma - csak "kp_forgalom" forrásnál lehet. */
  penznem: string | null;
  arfolyam: number | null;
  eredeti_penznem: string | null;
  eredeti_osszeg: number | null;
};

/** Egy időszak készpénz-képe: a négy sarok, amiből minden más kijön. */
export type KpOsszesites = {
  be_szamlaval: number;
  be_szamla_nelkul: number;
  ki_szamlaval: number;
  ki_szamla_nelkul: number;
  be_szamlaval_db: number;
  be_szamla_nelkul_db: number;
  ki_szamlaval_db: number;
  ki_szamla_nelkul_db: number;
  /** ÁTVEZETÉS (ATM-felvétel): a be/ki végösszegben benne van, a
   * legális/fekete bontásban külön áll. */
  be_atvezetes: number;
  ki_atvezetes: number;
  be_atvezetes_db: number;
  ki_atvezetes_db: number;
  be: number;
  ki: number;
  egyenleg: number;
  /** Amennyi számla nélküli költés NINCS lefedve számla nélküli bevétellel. */
  fekete_egyenleg: number;
};

export type KpNaplo = {
  sorok: KpNaploSor[];
  osszes: KpOsszesites;
  idei: KpOsszesites;
  /** Hány KP forgalom sor maradt ki, mert egy kiadáshoz kötődik. */
  kp_forgalom_kiadashoz_kotve: number;
  /** Hány készpénzes Bevétel/Kiadás maradt ki, mert Notionből importált (már
   * megvan a saját, kézzel felvitt KP forgalom párja). */
  notion_eredetu_kimaradt: number;
  jeloletlen_kiadas: number;
  jeloletlen_bevetel: number;
};

export async function getKpNaplo(): Promise<KpNaplo | null> {
  return apiGet<KpNaplo>("/api/v1/finance/kp-naplo");
}

/** A Notionből örökölt "KP forgalom" tábla egy sora - a készpénz-mozgások
 * kézzel vezetett nyilvántartása (lásd backend models/finance.KpForgalom). */
export type KpForgalom = {
  id: number;
  megnevezes: string | null;
  /** Az IRÁNY: "bevetel" vagy "kiadas". Importált soron gyakran üres - ott a
   * `forintban_notion` ELŐJELE döntött. Kézzel átírva viszont ez a mérvadó. */
  forgalom: string | null;
  osszeg: number | null;
  penznem: string;
  /** Devizás felvezetés: forinttól eltérő pénznemnél kötelező (lásd backend
   * services/penznem.py) - az `osszeg` mezőbe már a forint kerül. */
  arfolyam: number | null;
  /** MIBŐL lett a forint összeg - devizás felvezetésnél. */
  eredeti_penznem: string | null;
  eredeti_osszeg: number | null;
  /** Van-e mögötte SZÁMLA - kézzel állítható (legördülő), nem a feltöltött
   * fájlból derül ki. Csak ha igaz, jelenik meg a fájlfeltöltés lehetősége. */
  van_szamla: boolean;
  legalis: string | null;
  kiadas_datuma: string | null;
  expense_id: number | null;
  /** Melyik projekthez tartozik - önálló hivatkozás ("Projekt kiadás"), nem
   * az expense_id-hoz kötött duplikátum-elkerülés. */
  project_code_id: number | null;
  /** A Notion "Forintban" formulájának előjeles értéke (kiadáson negatív). */
  forintban_notion: number | null;
  /** A sor összege és iránya, ahogy a kassza számol vele. */
  forintban: number | null;
  kiadas_e: boolean;
  /** ATM-felvétel: a kasszába érkezik, de se a legális, se a fekete oldalra
   *  nem kerül - és az irányát sem az előjel adja, hanem ez a szabály. */
  atvezetes_e: boolean;
};

export async function getKpForgalmak(limit = 5000): Promise<KpForgalom[]> {
  return (await apiGet<KpForgalom[]>(`/api/v1/kp-forgalom?limit=${limit}`)) ?? [];
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

/** Mely munkatárs-id-k látják EGYÁLTALÁN a megadott oldalt - egy munkatárs-
 * választó (pl. "Felelős") szűréséhez, hogy csak olyat lehessen kiválasztani,
 * aki ténylegesen hozzáfér ahhoz az oldalhoz, ahol a rá kiosztott sor
 * megjelenik (lásd backend routes/user_access.py "lathatjak" végpontja). */
export async function getLathatjakAzOldalt(oldal: string): Promise<number[]> {
  const res = await apiGet<{ employee_ids: number[] }>(`/api/v1/user-access/lathatjak?oldal=${encodeURIComponent(oldal)}`);
  return res?.employee_ids ?? [];
}

/** A fenti három lekérdezés EGYBEN - a TopBar-nak kell mindhárom a mobil
 * navigációs fiókhoz (lásd components/MobileNav.tsx), és mivel a TopBar-t
 * minden oldal maga hordozza (nem az (app)/layout.tsx adja át propként),
 * egyetlen híváson keresztül olcsóbb, mint a fenti hármat külön hívni. */
export async function getMyAccess(): Promise<{
  allowedPages: string[] | null;
  pagePermissions: Record<string, string[]> | null;
  anyagKorlat: number[] | null;
}> {
  const res = await apiGet<{
    allowed_pages: string[] | null;
    page_permissions: Record<string, string[]> | null;
    lathato_deliverable_idk: number[] | null;
  }>("/api/v1/user-access/me");
  return {
    allowedPages: res?.allowed_pages ?? null,
    pagePermissions: res?.page_permissions ?? null,
    anyagKorlat: res?.lathato_deliverable_idk ?? null,
  };
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
  /** VÉDETT RENDSZERGAZDA: sosem inaktív, mindig mindenhez hozzáfér, és a
   * hozzáférése nem is korlátozható (lásd backend
   * core/security.vedett_rendszergazda). A felület ebből tudja, hogy neki
   * minden gombot mutasson, és hogy a Beállítások oldalon ne kínálja fel a
   * korlátozását. */
  vedett_admin?: boolean;
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
  hypeTodo: "/api/v1/hype-todo",
  floraFeladat: "/api/v1/flora",
  agiTodo: "/api/v1/agi-todo",
  expense: "/api/v1/expenses",
  revenue: "/api/v1/revenues",
  deliverable: "/api/v1/deliverables",
  timesheet: "/api/v1/timesheets",
  feedback: "/api/v1/feedback",
  contract: "/api/v1/contracts",
  assignment: "/api/v1/assignments",
  kpForgalom: "/api/v1/kp-forgalom",
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
 * getRelated szűrhetne, csak egy id-lista a rekordon).
 *
 * KÖTEGELVE megy (?ids=1,2,3 - lásd backend crud_router), NEM rekordonként
 * külön kéréssel: a korábbi, párhuzamos darabonkénti lekérés egy sok-
 * forgatásos eszköz adatlapjánál több száz egyidejű HTTP-kérést jelentett,
 * ami kimerítette a szerver adatbázis-kapcsolatait, és az egész rendszert
 * megakasztotta. */
export async function getRecordsByIds(basePath: string, ids: number[]): Promise<JsonRecord[]> {
  if (ids.length === 0) return [];
  // Adagokban, hogy az URL ne nőhessen a határok fölé.
  const adagok: number[][] = [];
  for (let i = 0; i < ids.length; i += 200) adagok.push(ids.slice(i, i + 200));
  const valaszok = await Promise.all(
    adagok.map((adag) => apiGet<JsonRecord[]>(`${basePath}?ids=${adag.join(",")}&limit=${adag.length}`)),
  );
  return valaszok.flatMap((v) => v ?? []);
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
  /** AUTOMATIKUS KIOSZTÁS: az ebbe az állapotba kerülő anyag ezekre az
   * emberekre osztódik ki (üres/null = nincs szabály). */
  auto_kiosztott_employee_ids?: number[] | null;
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
  /** A hozzászóláshoz mellékelt fájlok (entity_type: "deliverableComment"). */
  attachments: DocumentAttachment[];
};

export async function getDeliverableComments(deliverableId: number): Promise<DeliverableComment[]> {
  return (await apiGet<DeliverableComment[]>(`/api/v1/deliverables/${deliverableId}/comments`)) ?? [];
}

/** Ugyanaz a hozzászólás-minta, mint az Utómunkánál - lásd
 * components/projektkod/CommentsSection.tsx. */
export type ProjectCodeComment = {
  id: number;
  project_code_id: number;
  employee_id: number;
  employee_name: string;
  body: string;
  created_at: string;
};

export async function getProjectCodeComments(projectCodeId: number): Promise<ProjectCodeComment[]> {
  return (await apiGet<ProjectCodeComment[]>(`/api/v1/project-codes/${projectCodeId}/comments`)) ?? [];
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
  /** A rád osztott, még nem kész autó-teendők (lásd backend
   * routes/dashboard.py). Régebbi backenddel hiányozhat. */
  auto_teendok?: MyTaskItem[];
  /** A rád osztott, nem "Done" HYPE TO-DO feladatok. Régebbi backenddel
   * hiányozhat. */
  hype_todok?: MyTaskItem[];
};

/** Ki felel a diszpó kiküldéséért, oldalanként (gyártás / technika) - a
 * Beállítások oldalon szerkeszthető, és ez alapján kapják meg a felelősök a
 * másnapi diszpókat teendőként. */
export type DispoResponsibles = { gyartas: number[]; technika: number[] };

export async function getDispoResponsibles(): Promise<DispoResponsibles> {
  return (await apiGet<DispoResponsibles>("/api/v1/dispo-responsibles")) ?? { gyartas: [], technika: [] };
}

/** Kik kapják MÁSOLATBAN (CC) az összes kimenő diszpót - a Beállítások
 * oldalon, adminként állítható névsor (lásd backend
 * routes/dispo_responsibles.py "/masolat"). */
export type DiszpoMasolatCimzettek = { employee_ids: number[] };

export async function getDiszpoMasolatCimzettek(): Promise<DiszpoMasolatCimzettek> {
  return (await apiGet<DiszpoMasolatCimzettek>("/api/v1/dispo-responsibles/masolat")) ?? { employee_ids: [] };
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
  /** Miért szerelendő / miért van szervizben - a lezárás megköveteli
   * (lásd MAGYARAZATOT_IGENYLO_ALLAPOTOK). */
  megjegyzes: string | null;
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

export type StocktakeStatusGroupItem = {
  equipment_id: number;
  nev: string;
  megjegyzes: string | null;
  /** Ehhez az állapothoz kötelező a magyarázat. */
  magyarazat_kell: boolean;
};

export type StocktakeStatusGroup = {
  status: string;
  items: StocktakeStatusGroupItem[];
};

export type StocktakeMissingStock = {
  equipment_id: number;
  nev: string;
  expected_qty: number;
  counted_qty: number;
  hiany: number;
};

/** Amiből TÖBB van, mint az elvárt darabszám - ez is eltérés, nem öröm. */
export type StocktakeSurplusStock = {
  equipment_id: number;
  nev: string;
  expected_qty: number;
  counted_qty: number;
  tobblet: number;
};

export type StocktakeSummary = {
  problemas_statuszok: StocktakeStatusGroup[];
  hianyzo_keszletek: StocktakeMissingStock[];
  tobblet_keszletek: StocktakeSurplusStock[];
  /** Amihez még hiányzik a kötelező magyarázat - amíg van ilyen, a leltár nem
   * zárható le (a backend elutasítja). */
  magyarazatra_var: StocktakeStatusGroupItem[];
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
  /** Melyik projektkód költsége (ha a költés egy projekthez tartozik). */
  project_code_id: number | null;
  projektkod: string | null;
};

export type AutoHatarido = {
  id: number;
  nev: string;
  tipus: string;
  kovetkezo_esedekesseg: string | null;
  napok_hatra: number | null;
  allapot: string;
};

/** Egy teendő egy autóhoz - pipálható lista járművenként (lásd backend
 * routes/autok.py "teendok" végpontjai). */
/** Hozzászólás egy autó-teendő alatt - ugyanaz a chat-minta, mint a HYPE
 * TO-DO kommenteknél (lásd backend routes/autok.py komment-végpontjai). */
export type AutoTeendoKomment = {
  id: number;
  auto_teendo_id: number;
  employee_id: number;
  employee_name: string;
  body: string;
  created_at: string;
};

export type AutoTeendo = {
  id: number;
  auto_id: number;
  szoveg: string;
  kesz: boolean;
  hatarido: string | null;
  felelos_id: number | null;
  felelos_nev: string | null;
  kommentek: AutoTeendoKomment[];
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
  teendok: AutoTeendo[];
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
  /** A naphoz feltöltött számlák/blokkok - nem kötelező, lehet üres. */
  csatolmanyok: DocumentAttachment[];
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
  /** A tételhez feltöltött számlák/blokkok - nem kötelező, lehet üres. */
  csatolmanyok: DocumentAttachment[];
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
  /** Ebből mennyit fizettünk már ki, és mennyi van még hátra. A "még jár" a
   * gyakorlatban használt szám: ezt kell elutalni. */
  kifizetve_osszesen: number;
  hatralek: number;
  hatralekos_napok: number;
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
  /** Kifizettük-e már ezt a napot. */
  kifizetve: boolean;
  kifizetes_datuma: string | null;

  /** A NAPRA beírt saját érték (null = az időszakából örökli). */
  bejelentes: string | null;
  bejelentett_napi_ber: number | null;
  /** A ténylegesen érvényes bejelentés és a belőle következő pénzbontás:
   * a bejelentett napi bér utalással megy, a többi készpénzben. */
  ervenyes_bejelentes: string;
  bejelentes_forrasa: "nap" | "idoszak";
  idoszak_id: number | null;
  utalando: number;
  keszpenz: number;
};

// A bejelentés-lista a lib/krumpello.ts-ben él, hogy kliens-komponensből is
// behúzható legyen - itt csak újraexportáljuk, hogy a szerver-oldali hívók
// importja változatlan maradjon (ugyanaz a minta, mint a formatHuf-nál).
export { KRUMPELLO_BEJELENTESEK, krumpelloBejelentesCimke } from "@/lib/krumpello";

/** Egy ember foglalkoztatási időszaka - egyben az elszámolás egysége. */
export type KrumpelloIdoszak = {
  id: number;
  dolgozo_id: number;
  dolgozo_nev: string;
  kezdet: string;
  veg: string | null;
  bejelentes: string;
  bejelentes_cimke: string;
  napi_ber: number | null;
  nev: string | null;
  megjegyzes: string | null;
  napok_szama: number;
  ora_osszesen: number;
  jarandosag: number;
  utalando: number;
  keszpenz: number;
  borravalo: number;
  kifizetett: number;
  hatralek: number;
  kifizetett_napok: number;
  teljesen_kifizetve: boolean;
};

export type KrumpelloIdoszakNap = {
  munkaora_id: number;
  datum: string;
  ora: number;
  orabar: number;
  jarandosag: number;
  borravalo: number;
  bejelentes: string;
  bejelentes_cimke: string;
  bejelentes_forrasa: "nap" | "idoszak";
  utalando: number;
  keszpenz: number;
  /** A bejelentett bér többet fizet, mint amennyi aznap járt (rövid nap). */
  tulfizetett: boolean;
  kifizetve: boolean;
  kifizetes_datuma: string | null;
};

export type KrumpelloIdoszakReszletek = KrumpelloIdoszak & { napok: KrumpelloIdoszakNap[] };

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
  /** Amit még el kell utalni (a jelöletlen napok bére). */
  munkaber_hatralek: number;
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

export async function getKrumpelloIdoszakok(dolgozoId?: number): Promise<KrumpelloIdoszak[]> {
  const qs = dolgozoId != null ? `?dolgozo_id=${dolgozoId}` : "";
  return (await apiGet<KrumpelloIdoszak[]>(`/api/v1/krumpello/idoszakok${qs}`)) ?? [];
}

/** Látja-e a bejelentkezett ember a Krumpellót? A HYPE OS fejlécében ülő
 * kapcsoló ezt kérdezi - jog nélkül a kapcsoló meg sem jelenik. */
export async function getKrumpelloHozzaferes(): Promise<boolean> {
  const res = await apiGet<{ van_hozzaferes: boolean }>("/api/v1/krumpello/hozzaferes");
  return res?.van_hozzaferes ?? false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Vágói játék - havi pontverseny (lásd backend routes/vagoi_jatek.py)
// ─────────────────────────────────────────────────────────────────────────────

export type VagoAllas = {
  employee_id: number;
  nev: string;
  ellenorzes_db: number;
  ellenorzes_pont: number;
  vagas_perc: number;
  vagas_pont: number;
  /** Ellenőrzés-kimenetek: javítás nélkül átment (+) és javításba került (-)
   * anyagok száma, meg a pont-egyenlegük (lásd backend
   * models/vagoi_jatek.VagoEllenorzesKimenet). */
  jovahagyas_db: number;
  javitas_db: number;
  kimenet_pont: number;
  /** Arányosítás ELŐTT. */
  nyers_pont: number;
  munkanap: number;
  /** A verseny hivatalos pontszáma: nyers × (20 / munkanap). */
  pont: number;
  /** 1-től; holtversenynél azonos. 0 = nincs helyezése (0 pont). */
  helyezes: number;
};

export type VagoHonap = {
  ev: number;
  honap: number;
  nyeremeny: string | null;
  megjegyzes: string | null;
  /** Fotó a nyereményről. */
  kep_url: string | null;
  folyamatban: boolean;
  allas: VagoAllas[];
  gyoztes_nev: string | null;
  gyoztes_pont: number;
};

export type VagoSzabalyok = {
  ellenorzes_pont: number;
  perc_per_pont: number;
  alap_munkanap: number;
  jovahagyas_pont: number;
  javitas_pont: number;
};

export async function getVagoHonap(ev?: number, honap?: number): Promise<VagoHonap | null> {
  const p = new URLSearchParams();
  if (ev) p.set("ev", String(ev));
  if (honap) p.set("honap", String(honap));
  const qs = p.toString();
  return apiGet<VagoHonap>(`/api/v1/vagoi-jatek/honap${qs ? `?${qs}` : ""}`);
}

export async function getVagoKorabbiHonapok(darab = 6): Promise<VagoHonap[]> {
  return (await apiGet<VagoHonap[]>(`/api/v1/vagoi-jatek/korabbi?darab=${darab}`)) ?? [];
}

export async function getVagoSzabalyok(): Promise<VagoSzabalyok> {
  return (
    (await apiGet<VagoSzabalyok>("/api/v1/vagoi-jatek/szabalyok")) ?? {
      ellenorzes_pont: 50,
      perc_per_pont: 3,
      alap_munkanap: 20,
      jovahagyas_pont: 100,
      javitas_pont: -20,
    }
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Megrendelői papírozás (lásd backend routes/megrendeloi_papirok.py)
// ─────────────────────────────────────────────────────────────────────────────

/** "szerzodes" = eseti szerződés a megrendelővel, "tig" = teljesítési igazolás. */
export type MegrendeloiPapirFajta = "szerzodes" | "tig";

export type MegrendeloiPapir = {
  id: number;
  project_code_id: number;
  fajta: MegrendeloiPapirFajta;
  client_id: number | null;
  contact_id: number | null;
  keretszerzodes_id: number | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  kepviselo: string | null;
  nyilvantartasi_szam: string | null;
  email: string | null;
  megbizas_targya: string | null;
  projekt_nev: string | null;
  teljesites_szoveg: string | null;
  netto_osszeg: number | null;
  /** MILYEN PÉNZNEMBEN vállaltuk (a projektkódról). A papíron az az összeg
   * áll, amiben megállapodtunk - a bevétel ettől még forintban keletkezik
   * (lásd backend services/penznem.py). */
  penznem: string;
  plusz_afa: boolean | null;
  keltezes: string | null;
  megjegyzes: string | null;
  allapot: string | null;
  file_url: string | null;
  alairt_file_url: string | null;
  kihagyas_oka: string | null;
  /** Kiment, de az aláírt példány még nem jött vissza. */
  alairasra_var: boolean;
  /** A projektkód projektneve - a gyűjtőlista ezt mutatja, ha magára a
   * papírra nem írtak külön projektnevet. */
  projektkod_projekt_nev: string | null;
  projektkod: string | null;
};

/** Amivel egy ÚJ papír indul - a legjobb ismert forrásból előtöltve. */
export type MegrendeloiElotoltes = {
  client_id: number | null;
  contact_id: number | null;
  keretszerzodes_id: number | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  kepviselo: string | null;
  nyilvantartasi_szam: string | null;
  email: string | null;
  megbizas_targya: string | null;
  projekt_nev: string | null;
  teljesites_szoveg: string | null;
  netto_osszeg: number | null;
  plusz_afa: boolean | null;
  /** "keretszerzodes" | "ugyfel" | "kontakt" | "projektkod" */
  forras: string;
  /** Van-e élő keretszerződés - ilyenkor az eseti szerződés elhagyható. */
  van_elo_keretszerzodes: boolean;
};

export type MegrendeloiKeret = {
  id: number;
  client_id: number | null;
  client_nev: string | null;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  kepviselo: string | null;
  nyilvantartasi_szam: string | null;
  email: string | null;
  megbizas_targya: string | null;
  keltezes: string | null;
  allapot: string | null;
  file_url: string | null;
  alairt_file_url: string | null;
  alairva: boolean;
  /** Érvényes-e MA - ettől függ, kiváltja-e az eseti szerződést. */
  ervenyes: boolean;
  projektkod_db: number;
  /** Hány szerződésmódosítás tartozik hozzá, és hány vár még aláírásra. */
  modositas_db: number;
  modositas_alairasra_var: number;
};

/** Egy szerződésmódosítás a keretszerződéshez.
 *
 * Az állapot útja: Készítés alatt -> Aláírásra vár -> Kész. A többi papírtól
 * eltérően itt a KIKÜLDÉS még nem a végállomás: a módosítás akkor ér valamit,
 * ha aláírva visszajött. */
export type MegrendeloiKeretModositas = {
  id: number;
  contract_id: number;
  keltezes: string | null;
  allapot: string | null;
  file_url: string | null;
  alairt_file_url: string | null;
  email: string | null;
  /** Mire és mikor szólt az EREDETI szerződés, amire a módosítás hivatkozik. */
  megbizas_targya: string | null;
  szerzodes_letrejotte: string | null;
  kikuldve: string | null;
  kikuldte: string | null;
  /** A kiküldött kísérőlevél szövege, ahogy megírták (aláírás nélkül). */
  level_szoveg: string | null;
  megjegyzes: string | null;
};

/** Egy papír állapota a keretszerződés adatlapján - annyi, amennyiből látszik,
 * hol tart. A szerkesztés a projektkód adatlapján marad. */
export type MegrendeloiKeretPapir = {
  id: number;
  allapot: string | null;
  netto_osszeg: number | null;
  plusz_afa: boolean | null;
  keltezes: string | null;
  file_url: string | null;
  alairt_file_url: string | null;
  kihagyas_oka: string | null;
};

export type MegrendeloiKeretProjektkod = {
  id: number;
  projektkod: string;
  project_nev: string | null;
  datum: string | null;
  netto_osszeg: number | null;
  /** Kell-e ide egyáltalán papír (a projektkód kapcsolói szerint). */
  kell_papir: boolean;
  szerzodes: MegrendeloiKeretPapir | null;
  tig: MegrendeloiKeretPapir | null;
};

/** Egy a keretszerződéshez feltöltött fájl. */
export type MegrendeloiKeretFajl = {
  id: number;
  filename: string;
  url: string;
  kategoria: string;
  feltoltve: string | null;
};

/** A keretszerződés adatlapja: a saját adatai + minden hozzá tartozó projektkód
 * és azok papírjai + MINDEN feltöltött fájl. */
export type MegrendeloiKeretReszletek = MegrendeloiKeret & {
  nev: string | null;
  megjegyzes: string | null;
  fajlok: MegrendeloiKeretFajl[];
  projektkodok: MegrendeloiKeretProjektkod[];
  modositasok: MegrendeloiKeretModositas[];
};

export async function getMegrendeloiPapirok(
  fajta: MegrendeloiPapirFajta,
  projectCodeId?: number,
): Promise<MegrendeloiPapir[]> {
  const qs = projectCodeId != null ? `?project_code_id=${projectCodeId}` : "";
  return (await apiGet<MegrendeloiPapir[]>(`/api/v1/megrendeloi-papirok/${fajta}${qs}`)) ?? [];
}

export async function getMegrendeloiElotoltes(
  fajta: MegrendeloiPapirFajta,
  projectCodeId: number,
): Promise<MegrendeloiElotoltes | null> {
  return apiGet<MegrendeloiElotoltes>(`/api/v1/megrendeloi-papirok/${fajta}/elotoltes/${projectCodeId}`);
}

/** A megrendelői papírokon eddig előfordult "megbízás tárgya" szövegek -
 * legördülő listához, hogy ne kelljen mindig ugyanazt begépelni (lásd
 * components/megrendeloi/MegrendeloiPapirKezelo.tsx). */
export async function getMegbizasTargyaLista(): Promise<string[]> {
  return (await apiGet<string[]>("/api/v1/megrendeloi-papirok/megbizas-targya-lista")) ?? [];
}

/** A megrendelői SZÁMLA lépésének állása egy projektkódon (a papírozás
 * harmadik szakasza: határidő → kifizetve → bevétel). */
export type MegrendeloiSzamlaAllas = {
  fizetesi_hatarido: string | null;
  kifizetes_datuma: string | null;
  kifizetve: boolean;
  /** "Kifizetve, de ne kerüljön a bevételek közé" - indokkal. */
  bevetelbe_ne_keruljon: boolean;
  bevetel_kihagyas_oka: string | null;
  netto: number | null;
  brutto: number | null;
  van_szamla_fajl: boolean;
  /** A számla PDF-je (csatolmány vagy a Notionból örökölt cím). */
  szamla_url: string | null;
  bevetel_sorok: number;
  /** "Erről a munkáról nincs számla" - ilyenkor határidő sem kell. */
  szamla_kihagyva: boolean;
  szamla_kihagyas_oka: string | null;
  /** Kell-e fizetési határidő a kifizetés jelöléséhez. */
  hatarido_kell: boolean;
  /** Kötelező-e a kifizetés dátuma. Ahol számlát sem várunk, ott nem: a
   * legtöbbször nincs is tranzakció (lásd backend
   * services/megrendeloi_szamla._kifizetes_datum_kell). */
  kifizetes_datum_kell: boolean;
  /** Tranzakció NÉLKÜL lett lezárva - nincs kifizetési dátuma, és ez nem
   * hiány, hanem maga a válasz. */
  tranzakcio_nelkul_lezarva: boolean;
  /** MENNYI IDŐ van a kifizetésig, vagy mennyivel csúszott (lásd
   * lib/hatarido.ts). Fizetési határidő nélkül null. */
  hatarido_allas: HataridoAllas | null;
  /** Milyen pénznemben vállaltuk a munkát, és milyen árfolyamon számolunk. A
   * `netto`/`brutto` ebben a pénznemben van, a `*_forintban` pedig az, ami
   * ténylegesen a Pénzügyekbe kerül (lásd backend services/penznem.py). */
  penznem: string;
  arfolyam: number | null;
  netto_forintban: number | null;
  brutto_forintban: number | null;
  /** HOGYAN érkezett a pénz ("Átutalás" / "Készpénz"). Készpénznél a bevétel a
   * KASSZÁBA is bekerül: a KP forgalom oldalon ugyanez a sor látszik, külön
   * felvezetés nélkül. */
  fizetes_modja: string | null;
  keszpenzes: boolean;
  /** Készpénzes bevételnél ettől függ, hogy sima legális bevétel-e, vagy
   * FEDEZET a számla nélküli kiadásokhoz. */
  van_szamla_a_bevetelen: boolean;
};

export async function getMegrendeloiSzamlaAllas(projectCodeId: number): Promise<MegrendeloiSzamlaAllas | null> {
  return apiGet<MegrendeloiSzamlaAllas>(`/api/v1/megrendeloi-papirok/szamla/${projectCodeId}`);
}

export async function getMegrendeloiKeretek(): Promise<MegrendeloiKeret[]> {
  return (await apiGet<MegrendeloiKeret[]>("/api/v1/megrendeloi-keretszerzodesek")) ?? [];
}

// ── HYPE 2026 diszpótábla (a Google Sheetből átvett munkalapok) ────────────
//
// A cellák SZÍNE itt adat, nem formázás: az mondja meg, ki melyik nap
// dolgozott (lásd backend models/diszpo_tabla.py).

// A színek (és a jelentésük) a KLIENS-BIZTOS lib/diszpoSzin.ts-ben élnek: ezt
// a modult egy klienskomponens nem importálhatja értékként (next/headers).
export type { DiszpoSzin } from "@/lib/diszpoSzin";

export type DiszpoMunkalapFej = {
  id: number;
  nev: string;
  sorrend: number;
  sor_szam: number;
  oszlop_szam: number;
  /** Hány felső sor a fejléc (a belsős táblán kettő: szekciók + nevek). */
  fejlec_sorok: number;
};

export type DiszpoOszlop = {
  idx: number;
  cimke: string | null;
  csoport: string | null;
  /** Melyik munkatárs oszlopa. Enélkül a színei nem számítanak bele a
   * munkanap-számlálásba. */
  employee_id: number | null;
  employee_nev: string | null;
  /** Elrejtett oszlop: a rács nem mutatja, az adata és a munkanap-számítása
   * él (lásd backend models/diszpo_tabla.DiszpoOszlop.rejtett). */
  rejtett: boolean;
};

export type DiszpoSor = {
  idx: number;
  datum: string | null;
  nap: string | null;
  diszposzam: number | null;
  /** Hónap-elválasztó sor ("❄️ JANUÁR ❄️"). */
  elvalaszto: boolean;
};

/** [sor_idx, oszlop_idx, érték, szín] - tömören, mert a külsős munkalap 34
 *  ezer cellája objektumokként több megabájt lenne. */
export type DiszpoCella = [number, number, string | null, string | null];

export type DiszpoMunkalap = DiszpoMunkalapFej & {
  oszlopok: DiszpoOszlop[];
  sorok: DiszpoSor[];
  cellak: DiszpoCella[];
};

export async function getDiszpoMunkalapok(): Promise<DiszpoMunkalapFej[]> {
  return (await apiGet<DiszpoMunkalapFej[]>("/api/v1/diszpo-tabla")) ?? [];
}

export async function getDiszpoMunkalap(id: number): Promise<DiszpoMunkalap | null> {
  return apiGet<DiszpoMunkalap>(`/api/v1/diszpo-tabla/${id}`);
}

/** Ki hány napot dolgozott egy hónapban, és kinél fogyott el a szerződött
 *  napszám (lásd backend services/munkanap_szamlalo.py). */
export type DiszpoHaviAllas = {
  employee_id: number;
  employee_nev: string | null;
  ev: number;
  honap: number;
  munkanapok: number;
  szerzodott_napok: number | null;
  napi_dij: number | null;
  plusz_nap_napi_dij: number | null;
  /** Az a nap, amelyiken a szerződött napok elfogynak. */
  hatarnap: string | null;
  plusz_napok: string[];
  /** Megkaptuk-e a PÉNZÜGYI részt (napidíj, plusz napok, szerződött napszám).
   *  Csak az kapja, aki a Pénzügyek oldalt is látja - a felület ebből tudja,
   *  hogy egy üres napidíj "nincs megadva" vagy "nem látod". */
  penzugyi_adat: boolean;
};

export async function getDiszpoHaviAllas(ev: number, honap: number): Promise<DiszpoHaviAllas[]> {
  return (await apiGet<DiszpoHaviAllas[]>(`/api/v1/diszpo-tabla/munkanapok/${ev}/${honap}`)) ?? [];
}
