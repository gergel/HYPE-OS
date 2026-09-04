"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { SelectDropdown } from "@/components/SelectDropdown";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { formatIdopont } from "@/lib/ido";
import { humanizeKey } from "@/lib/mezoNev";
import { useLiveTopic } from "@/lib/live";
import { AllapotBeallitasok } from "@/components/deliverable/AllapotBeallitasok";
import { DeliverableBoard, type BoardCard, type BoardColumn } from "@/components/deliverable/DeliverableBoard";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import { UtomunkaViewTabs } from "@/components/deliverable/UtomunkaViewTabs";
import { VinyoKezeles } from "@/components/deliverable/VinyoKezeles";
import { VisszajelzesModal } from "@/components/deliverable/FeedbackSendButton";
import { RecordDetailModal } from "@/components/RecordDetailModal";
import type { AllapotBeallitas, Deliverable, Employee } from "@/lib/api";

// Nem importáljuk az ENTITY_PATHS-t a lib/api.ts-ből (bár csak egy sima
// konstans) - az a modul a `next/headers`-t is importálja (szerver-oldali
// cookie-olvasáshoz), és egy kliens komponensbe akár csak egyetlen NEM
// type-only importja is beviszi a teljes modult a kliens bundle-be, ami
// build hibát okoz ("next/headers" csak Server Component-ekben érhető el).
const DELIVERABLE_BASE_PATH = "/api/v1/deliverables";

// A PONTOS szöveg, amivel a szerver elutasítja az ellenőrzésbe-tételt, ha még
// nincs vágói visszajelzés (lásd backend routes/postproduction.py
// VISSZAJELZES_HIANYZIK_UZENET) - ebből ismerjük fel EZT a konkrét hibát a
// többi közül, hogy a sima hiba-alert helyett a felugró visszajelzés-űrlapot
// nyissuk meg. SIMA SZÖVEG, nem strukturált objektum: kb. 80 helyen fut a
// felületen ugyanaz a minta (`alert(\`...: ${detail?.detail}\`)`), ami
// stringnek várja a hiba törzsét.
const VISSZAJELZES_HIANYZIK_UZENET = "Mielőtt ellenőrzésbe teszed, írj visszajelzést ehhez az anyaghoz.";

const NO_STATUS_KEY = "__nincs_allapot__";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

type CalendarProject = { id: number; nev: string; forgatas_datuma: string | null; forgatas_datuma_vege: string | null };

type FutoTimer = { deliverable_id: number; employee_id: number; full_name: string };

/** Milyen sűrűn frissüljön a "ki vág éppen" jelzés a kártyákon. Egy futó
 * timer percekig-órákig megy, a 60 másodperc bőven elég friss - és a
 * lekérdezés egyetlen olcsó kör (lásd backend get_futo_timerek). */
const FUTO_TIMER_FRISSITES_MS = 60_000;

/** Az Utómunka oldal tényleges tartalma (tábla + naptár + admin lista) - a
 * kezdeti szerver-oldali renderelés csak a legutóbb módosított anyagok/
 * forgatások egy szeletét kapja meg (lásd app/utomunka/page.tsx), hogy az
 * oldal azonnal betöltődjön még nagyon sok, rég lezárt/nem használt rekord
 * mellett is - a maradékot ez a komponens tölti be a háttérben,
 * betöltés-jelző/blokkolás nélkül, és csendben beleolvasztja a listába. */
export function UtomunkaContent({
  lejartSzures = false,
  initialDeliverables,
  deliverablesHasMore,
  initialProjects,
  projectsHasMore,
  employees,
  statusOptions,
  allapotBeallitasok,
  kartyaMezok,
  vinyoOptions,
  canCreate,
  canDelete,
  canEdit,
  vinyoKezelheto = false,
  isAdmin = false,
}: {
  /** Igaz esetén az oldal a LEJÁRT határidejű anyagokra szűrve nyílik (a
   * dashboard figyelmeztetéséről jövet, ?szures=lejart) - a felületen
   * kikapcsolható. */
  lejartSzures?: boolean;
  initialDeliverables: Deliverable[];
  deliverablesHasMore: boolean;
  initialProjects: CalendarProject[];
  projectsHasMore: boolean;
  employees: Employee[];
  statusOptions: string[];
  /** Az állapot-oszlopok sorrendje/színe (lásd AllapotBeallitasok). */
  allapotBeallitasok: AllapotBeallitas[];
  /** Mely mezők látszódjanak a tábla kártyáin (üres = alapértelmezés). */
  kartyaMezok: string[];
  vinyoOptions: string[];
  canCreate: boolean;
  canDelete: boolean;
  canEdit: boolean;
  /** Kezelheti-e a vinyó-neveket (új/átnevezés/törlés) - admin, vagy akinek
   * admin külön megadta (lásd backend postproduction._vinyo_kezelheto). */
  vinyoKezelheto?: boolean;
  /** Admin a vinyó-kezelésben a jogosultság-kiosztást is látja. */
  isAdmin?: boolean;
}) {
  const [deliverables, setDeliverables] = useState(initialDeliverables);
  const [projects, setProjects] = useState(initialProjects);
  // Ha egy állapotváltást a szerver azért utasít el, mert az anyaghoz még
  // nincs vágói visszajelzés (lásd allapotAtallitasa), itt tartjuk számon,
  // MELYIK anyagot és MILYEN állapotba próbáltuk tenni - a felugró
  // visszajelzés-űrlap sikeres mentése után ebből tudjuk újra megpróbálni
  // ugyanazt a váltást, akárhonnan is indult (Kanban-húzás vagy a lista
  // "Állapot" legördülője).
  const [visszajelzesKerve, setVisszajelzesKerve] = useState<{ deliverableId: number; allapot: string | null } | null>(
    null,
  );
  // Épp futó időmérések - a kártyákon látszik, ki min dolgozik (lásd lent
  // a frissítő useEffect-et és a toCard-ot).
  const [futoTimerek, setFutoTimerek] = useState<FutoTimer[]>([]);
  // Kereső a "Vinyók szerint" nézethez (a felhasználó kérése): projekt-névre,
  // eseményre vagy projektkódra szűkíti a kártyákat - az üres oszlopok el is
  // tűnnek, így rögtön látszik, melyik vinyón van a keresett projekt.
  const [vinyoKereses, setVinyoKereses] = useState("");
  // Ugyanilyen kereső az "Állapot szerint" nézethez is (a felhasználó kérése).
  const [allapotKereses, setAllapotKereses] = useState("");
  // A kártya FELUGRÓ ABLAKBAN nyílik (a felhasználó kérése), nem teljes
  // oldalként - itt az épp nyitott anyag útvonala (lásd RecordDetailModal).
  const [modalHref, setModalHref] = useState<string | null>(null);
  // A dashboard figyelmeztetéséről jövet csak a lejárt anyagok látszanak -
  // a sávon kikapcsolható, és onnantól a teljes oldal a megszokott.
  const [csakLejart, setCsakLejart] = useState(lejartSzures);

  useEffect(() => {
    if (!deliverablesHasMore) return;
    authFetch(`/api/v1/deliverables?skip=${initialDeliverables.length}&limit=5000`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rest: Deliverable[]) => setDeliverables((prev) => [...prev, ...rest]))
      .catch(() => {});
    // csak első betöltéskor fusson - a szűrő/rendezés kliens-oldali állapota nem függ ettől
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!projectsHasMore) return;
    authFetch(`/api/v1/projects?skip=${initialProjects.length}&limit=5000`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rest: CalendarProject[]) => setProjects((prev) => [...prev, ...rest]))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A futó időmérések betöltése + időzített frissítése: aki elindít vagy
  // leállít egy mérőt, az legfeljebb egy percen belül a többiek tábláján is
  // látszik/eltűnik.
  useEffect(() => {
    let aktiv = true;
    const betolt = () =>
      authFetch("/api/v1/deliverables/futo-timerek")
        .then((res) => (res.ok ? res.json() : null))
        .then((adat: FutoTimer[] | null) => {
          if (aktiv && adat) setFutoTimerek(adat);
        })
        .catch(() => {});
    void betolt();
    const idozito = setInterval(betolt, FUTO_TIMER_FRISSITES_MS);
    return () => {
      aktiv = false;
      clearInterval(idozito);
    };
  }, []);

  // Mindkét lista a komponens saját állapotában él (a szerver csak az első
  // szeletet adja), ezért a háttérfrissítésnél itt kell újratölteni.
  useLiveTopic("deliverables", () => {
    authFetch(`/api/v1/deliverables?limit=5000`)
      .then((res) => (res.ok ? res.json() : null))
      .then((fresh: Deliverable[] | null) => fresh && setDeliverables(fresh))
      .catch(() => {});
  });

  useLiveTopic("projects", () => {
    authFetch(`/api/v1/projects?limit=5000`)
      .then((res) => (res.ok ? res.json() : null))
      .then((fresh: CalendarProject[] | null) => fresh && setProjects(fresh))
      .catch(() => {});
  });

  const employeeName = useMemo(() => new Map(employees.map((e) => [e.id, e.full_name])), [employees]);

  // {anyag id -> akiknek épp fut rajta az időmérője}.
  const timerNevek = useMemo(() => {
    const nevek = new Map<number, string[]>();
    for (const t of futoTimerek) {
      if (!nevek.has(t.deliverable_id)) nevek.set(t.deliverable_id, []);
      nevek.get(t.deliverable_id)!.push(t.full_name);
    }
    return nevek;
  }, [futoTimerek]);

  /** Egy mező értéke emberi alakban a kártyára. A munkatárs-azonosítókat
   * névre oldjuk, a logikai mezőket Igen/Nem-re - különben "true" és nyers
   * id-k jelennének meg a kártyán. */
  function mezoErteke(d: Deliverable, kulcs: string): string | null {
    const nyers = (d as unknown as Record<string, unknown>)[kulcs];
    if (nyers === null || nyers === undefined || nyers === "") return null;
    if (kulcs.endsWith("employee_id")) return employeeName.get(Number(nyers)) ?? `#${nyers}`;
    if (typeof nyers === "boolean") return nyers ? "Igen" : "Nem";
    if (Array.isArray(nyers)) return nyers.length > 0 ? nyers.join(", ") : null;
    const szoveg = String(nyers);
    // Dátum/időpont: elég a nap (a kártyán nincs hely az ISO-időbélyegre).
    return /^\d{4}-\d{2}-\d{2}/.test(szoveg) ? formatDate(szoveg) : szoveg;
  }

  function toCard(d: Deliverable, badges: string[]): BoardCard {
    // Beállítás nélkül marad az eddigi alapértelmezés (határidő), hogy a
    // tábla ne ürüljön ki azoknál, akik sosem nyúlnak a beállításhoz. A
    // kiosztás nem itt van: azt a kártya MINDIG mutatja (lásd lent).
    const alapertelmezett = kartyaMezok.length === 0;
    const subtitleParts = alapertelmezett
      ? [d.hatarido ? `Határidő: ${formatDate(d.hatarido)}` : null].filter((p): p is string => p !== null)
      : [];
    const mezok = alapertelmezett
      ? []
      : kartyaMezok
          .map((kulcs) => ({ cimke: humanizeKey(kulcs), ertek: mezoErteke(d, kulcs) }))
          .filter((m): m is { cimke: string; ertek: string } => m.ertek !== null);
    // Kikre van kiosztva: az új több-emberes lista; régi (még egyértékű)
    // adatnál az assigned_to mezőből oldjuk fel a nevet.
    const kiosztva =
      d.kiosztott_nevek && d.kiosztott_nevek.length > 0
        ? d.kiosztott_nevek
        : d.assigned_to_employee_id
          ? [employeeName.get(d.assigned_to_employee_id) ?? "?"]
          : [];
    return {
      id: d.id,
      href: `/utomunka/${d.id}`,
      title: d.projekt_neve,
      subtitle: subtitleParts.length > 0 ? subtitleParts.join(" · ") : null,
      badges,
      mezok,
      // A felhasználó kérése: a kártyán MINDIG látsszon, kinek van kiosztva
      // és kinek fut rajta épp az időmérője.
      kiosztva,
      timerek: timerNevek.get(d.id) ?? [],
    };
  }

  // Ugyanaz a "lejárt" definíció, mint a dashboard figyelmeztetés-számlálójában
  // (lásd backend routes/dashboard.py): a határidő a múltban van, az anyag
  // nincs kiküldve, és nem áll kész állapotban (a kész állapotokat az admin
  // jelöli az állapot-beállításokon).
  const lathatoAnyagok = useMemo(() => {
    if (!csakLejart) return deliverables;
    const ma = new Date();
    const maNap = `${ma.getFullYear()}-${String(ma.getMonth() + 1).padStart(2, "0")}-${String(ma.getDate()).padStart(2, "0")}`;
    const keszek = new Set(allapotBeallitasok.filter((b) => b.kesz_allapot).map((b) => b.allapot));
    return deliverables.filter(
      (d) =>
        d.hatarido !== null &&
        d.hatarido.slice(0, 10) < maNap &&
        !d.anyag_kikuldve &&
        !(d.allapot !== null && keszek.has(d.allapot)),
    );
  }, [deliverables, csakLejart, allapotBeallitasok]);

  const statusColumns: BoardColumn[] = useMemo(() => {
    // Kereső az állapot-nézeten (a felhasználó kérése) - ugyanarra a három
    // mezőre, mint a vinyó-nézet keresője.
    const keresett = allapotKereses.trim().toLocaleLowerCase("hu-HU");
    const talal = (d: Deliverable) =>
      !keresett ||
      [d.projekt_neve, d.esemeny_neve, d.projektkod_szoveg].some((mezo) =>
        (mezo ?? "").toLocaleLowerCase("hu-HU").includes(keresett),
      );
    const byStatus = new Map<string, Deliverable[]>();
    for (const d of lathatoAnyagok) {
      if (!talal(d)) continue;
      const key = d.allapot && statusOptions.includes(d.allapot) ? d.allapot : NO_STATUS_KEY;
      if (!byStatus.has(key)) byStatus.set(key, []);
      byStatus.get(key)!.push(d);
    }
    // Az oszlopok sorrendjét és színét az admin állítja (lásd
    // AllapotBeallitasok); amihez nincs beállítás, az a végére kerül, a
    // választható értékek sorrendjében.
    const szinek = new Map(allapotBeallitasok.map((b) => [b.allapot, b.szin]));
    const helye = new Map(allapotBeallitasok.map((b, i) => [b.allapot, i]));
    const rendezett = [...statusOptions].sort(
      (a, b) => (helye.get(a) ?? Number.MAX_SAFE_INTEGER) - (helye.get(b) ?? Number.MAX_SAFE_INTEGER),
    );
    return [
      ...rendezett.map((s) => ({
        key: s,
        label: s,
        szin: szinek.get(s) ?? null,
        cards: (byStatus.get(s) ?? []).map((d) => toCard(d, d.vinyok ?? [])),
      })),
      // Az "állapot nélküli" oszlop akkor is kell, ha épp üres - de csak
      // annak, aki húzhat: enélkül nem lehetne visszavenni egy anyagról az
      // állapotot a táblán.
      ...(byStatus.has(NO_STATUS_KEY) || canEdit
        ? [
            {
              key: NO_STATUS_KEY,
              label: "Nincs állapot",
              cards: (byStatus.get(NO_STATUS_KEY) ?? []).map((d) => toCard(d, d.vinyok ?? [])),
            },
          ]
        : []),
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lathatoAnyagok, statusOptions, allapotBeallitasok, kartyaMezok, canEdit, employeeName, timerNevek, allapotKereses]);

  const vinyoColumns: BoardColumn[] = useMemo(() => {
    const keresett = vinyoKereses.trim().toLocaleLowerCase("hu-HU");
    const talal = (d: Deliverable) =>
      !keresett ||
      [d.projekt_neve, d.esemeny_neve, d.projektkod_szoveg].some((mezo) =>
        (mezo ?? "").toLocaleLowerCase("hu-HU").includes(keresett),
      );
    const byVinyo = new Map<string, Deliverable[]>();
    for (const d of lathatoAnyagok) {
      if (!talal(d)) continue;
      for (const v of d.vinyok ?? []) {
        if (!byVinyo.has(v)) byVinyo.set(v, []);
        byVinyo.get(v)!.push(d);
      }
    }
    return vinyoOptions
      .filter((v) => (byVinyo.get(v)?.length ?? 0) > 0)
      // A kártya-címke itt az ARCHIVÁLÁS állapota (a felhasználó kérése) -
      // a vágás-állapotot a fenti állapot-tábla úgyis mutatja.
      .map((v) => ({ key: v, label: v, cards: byVinyo.get(v)!.map((d) => toCard(d, d.archivalas ? [d.archivalas] : [])) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lathatoAnyagok, vinyoOptions, vinyoKereses, kartyaMezok, employeeName, timerNevek]);

  /** Az anyag ÁLLAPOTÁNAK tényleges átírása - ezt hívja mind a Kanban-húzás
   * (kartyaAthelyezes, a celOszlop -> allapot fordítás után), mind a lista
   * "Állapot" oszlopának legördülője, hogy ELLENŐRZÉS-be visszajelzés nélkül
   * SEHONNAN ne lehessen tenni: bárhonnan is próbálják, ugyanaz a felugró
   * visszajelzés-űrlap nyíljon meg a sima hiba-alert helyett.
   *
   * A képernyőn azonnal átíródik az állapot (optimista frissítés) - a vágó ne
   * várjon a szerverre egy ilyen apró lépésnél -, hiba esetén viszont
   * visszaáll, hogy ne higgyük elmentettnek, ami nem ment el. */
  async function allapotAtallitasa(deliverableId: number, ujAllapot: string | null) {
    const eredeti = deliverables.find((d) => d.id === deliverableId);
    if (!eredeti || eredeti.allapot === ujAllapot) return;
    setDeliverables((elozo) => elozo.map((d) => (d.id === deliverableId ? { ...d, allapot: ujAllapot } : d)));
    try {
      const res = await authFetch(`${DELIVERABLE_BASE_PATH}/${deliverableId}`, {
        method: "PATCH",
        body: JSON.stringify({ allapot: ujAllapot }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setDeliverables((elozo) =>
          elozo.map((d) => (d.id === deliverableId ? { ...d, allapot: eredeti.allapot } : d)),
        );
        // Ez a konkrét hiba (lásd routes/postproduction._ellenorzeshez_kell_visszajelzes)
        // ebből a pontos szövegből ismerhető fel - sima alert() helyett a
        // felugró visszajelzés-űrlapot nyitjuk meg helyette.
        if (detail?.detail === VISSZAJELZES_HIANYZIK_UZENET) {
          setVisszajelzesKerve({ deliverableId, allapot: ujAllapot });
          return;
        }
        alert(`Az állapot módosítása nem sikerült: ${detail?.detail ?? res.status}`);
      }
    } catch (err) {
      setDeliverables((elozo) =>
        elozo.map((d) => (d.id === deliverableId ? { ...d, allapot: eredeti.allapot } : d)),
      );
      alert(`Az állapot módosítása nem sikerült (hálózati hiba): ${err}`);
    }
  }

  /** Kártya áthúzása másik oszlopba: a Kanban oszlop-kulcsot (ami a "nincs
   * állapot" oszlopnál a NO_STATUS_KEY sentinel) fordítja a tényleges
   * allapot-értékre. */
  async function kartyaAthelyezes(deliverableId: number, celOszlop: string) {
    await allapotAtallitasa(deliverableId, celOszlop === NO_STATUS_KEY ? null : celOszlop);
  }

  /** A visszajelzés-űrlap sikeres mentése után újra megpróbáljuk ugyanazt az
   * állapotváltást, amit a szerver az imént elutasított - a felhasználónak
   * nem kell külön még egyszer elvégeznie a lépést, a visszajelzés megírása
   * MAGA a befejezése. */
  function visszajelzesUtan() {
    if (!visszajelzesKerve) return;
    const { deliverableId, allapot } = visszajelzesKerve;
    setVisszajelzesKerve(null);
    void allapotAtallitasa(deliverableId, allapot);
  }

  const calendarProjects = useMemo(() => projects.filter((p) => p.forgatas_datuma !== null), [projects]);

  // DUPLIKÁLT anyagok (a felhasználó kérése): ugyanaz az anyagnév több
  // vinyón is szerepel - név szerint összevonva (akár egy anyag több vinyóval,
  // akár több azonos nevű anyag külön vinyókkal), hogy takarításkor látszódjon,
  // mi hol foglal helyet feleslegesen.
  const duplikaltak = useMemo(() => {
    const nevhez = new Map<string, { nev: string; vinyok: Set<string> }>();
    for (const d of deliverables) {
      const nev = (d.projekt_neve ?? "").trim();
      if (!nev) continue;
      const kulcs = nev.toLocaleLowerCase("hu-HU");
      for (const v of d.vinyok ?? []) {
        if (!nevhez.has(kulcs)) nevhez.set(kulcs, { nev, vinyok: new Set() });
        nevhez.get(kulcs)!.vinyok.add(v);
      }
    }
    return Array.from(nevhez.values())
      .filter((x) => x.vinyok.size >= 2)
      .map((x) => ({ nev: x.nev, vinyok: Array.from(x.vinyok).sort((a, b) => a.localeCompare(b, "hu")) }))
      .sort((a, b) => a.nev.localeCompare(b.nev, "hu"));
  }, [deliverables]);

  // Miből lehet válogatni a kártyára: az anyagok mezői (a nevet és a
  // technikai azonosítókat kihagyva - azok nem mondanak semmit a kártyán).
  const mezoValasztek = useMemo(() => {
    const minta = deliverables[0];
    const kulcsok = minta ? Object.keys(minta) : [];
    return kulcsok
      .filter((k) => !["id", "projekt_neve", "project_id", "project_code_id"].includes(k))
      .map((kulcs) => ({ kulcs, cimke: humanizeKey(kulcs) }));
  }, [deliverables]);

  return (
    <>
      {/* A dashboard figyelmeztetéséről jövet aktív lejárt-szűrés jelzése -
          innen kapcsolható vissza a teljes lista. */}
      {csakLejart && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] bg-bg-warning px-3 py-2.5 text-[13px] text-text-warning">
          <span>
            Csak a lejárt határidejű anyagok látszanak ({lathatoAnyagok.length}) - amiknek a
            határideje elmúlt, de nincsenek kiküldve vagy kész állapotban.
          </span>
          <button
            type="button"
            onClick={() => setCsakLejart(false)}
            className="rounded-[var(--radius)] border border-text-warning/40 px-2.5 py-1 font-medium hover:opacity-80"
          >
            Szűrés kikapcsolása
          </button>
        </div>
      )}
      <UtomunkaViewTabs
        board={
          <div className="space-y-6">
            <Card
              title="Állapot szerint"
              actions={
                canEdit ? (
                  <AllapotBeallitasok
                    allapotok={statusOptions}
                    kezdeti={allapotBeallitasok}
                    mezoValasztek={mezoValasztek}
                    kezdetiKartyaMezok={kartyaMezok}
                    emberek={employees.map((e) => ({ id: e.id, nev: e.full_name }))}
                  />
                ) : undefined
              }
            >
              {/* Kereső az állapot-nézet tetején (a felhasználó kérése). */}
              <input
                type="search"
                value={allapotKereses}
                onChange={(e) => setAllapotKereses(e.target.value)}
                placeholder="Keresés projektre (név, esemény, projektkód)…"
                aria-label="Keresés az állapot nézetben projektre"
                className="mb-3 w-80 max-w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
              />
              {/* Szerkesztési joggal a kártyák áthúzhatók másik oszlopba - ez
                  írja át az anyag állapotát. A kártya felugró ablakban nyílik
                  (a felhasználó kérése). */}
              <DeliverableBoard
                columns={statusColumns}
                onAthelyezes={canEdit ? kartyaAthelyezes : undefined}
                onMegnyitas={setModalHref}
              />
            </Card>
            <Card title="Forgatások naptár">
              <ForgatasokCalendar projects={calendarProjects} />
            </Card>
            <Card
              title="Vinyók szerint"
              // A vinyó-nevek kezelése (a felhasználó kérése) - csak annak,
              // akinek admin megadta a külön jogosultságot (vagy adminnak).
              actions={
                vinyoKezelheto ? (
                  <VinyoKezeles
                    kezdetiOpciok={vinyoOptions}
                    isAdmin={isAdmin}
                    emberek={employees.map((e) => ({ id: e.id, nev: e.full_name }))}
                  />
                ) : undefined
              }
            >
              <input
                type="search"
                value={vinyoKereses}
                onChange={(e) => setVinyoKereses(e.target.value)}
                placeholder="Keresés projektre (név, esemény, projektkód)…"
                aria-label="Keresés a vinyók közt projektre"
                className="mb-3 w-80 max-w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
              />
              {vinyoKereses.trim() && vinyoColumns.length === 0 && (
                <p className="mb-2 text-[13px] text-text-muted">Nincs találat erre: „{vinyoKereses.trim()}”.</p>
              )}
              <DeliverableBoard columns={vinyoColumns} onMegnyitas={setModalHref} />
            </Card>
            {/* DUPLIKÁLT anyagok (a felhasználó kérése): ugyanaz az anyagnév
                több vinyón - takarításkor innen látszik, mi hol foglal
                feleslegesen. Csak akkor jelenik meg, ha van ilyen. */}
            {duplikaltak.length > 0 && (
              <Card title={`Több vinyóra mentett anyagok (${duplikaltak.length})`}>
                <p className="mb-3 text-[13px] text-text-secondary">
                  Ezek az anyagnevek egyszerre több vinyón is szerepelnek - ha valamelyik példány már nem kell,
                  itt látszik, honnan lehet törölni.
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b border-border text-left text-text-secondary">
                        <th className="py-1.5 pr-4 font-medium">Anyag</th>
                        <th className="py-1.5 font-medium">Ezeken a vinyókon</th>
                      </tr>
                    </thead>
                    <tbody>
                      {duplikaltak.map((sor) => (
                        <tr key={sor.nev} className="border-b border-border/60 align-top">
                          <td className="py-2 pr-4 text-text-primary [overflow-wrap:anywhere]">{sor.nev}</td>
                          <td className="py-2">
                            <div className="flex flex-wrap gap-1">
                              {sor.vinyok.map((v) => (
                                <span
                                  key={v}
                                  className="rounded bg-surface-3 px-1.5 py-0.5 text-[12px] text-text-secondary"
                                >
                                  {v}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </div>
        }
        list={
          <Card title={`Utómunka (${lathatoAnyagok.length})`}>
            {canCreate && (
              <QuickCreateForm
                postPath={DELIVERABLE_BASE_PATH}
                addLabel="+ Új anyag hozzáadása"
                // A PROJEKTKÓD kötelező: ebből derül ki, melyik munka utómunkája,
                // és ez alapján kerül a helyére a projektkód adatlapján. A
                // formátum szabad (lásd backend services/projektkod_kotes.py).
                fields={[
                  { name: "projekt_neve", label: "Anyag neve", required: true },
                  { name: "projektkod_szoveg", label: "Projektkód", required: true },
                  { name: "hatarido", label: "Határidő", type: "date" },
                ]}
              />
            )}
            <DataTable<Deliverable>
              rows={lathatoAnyagok}
              emptyText="Még nincs felvett vágandó anyag - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
              getHref={(d) => `/utomunka/${d.id}`}
              // A sor felugró ablakban nyílik (a felhasználó kérése) - a
              // teljes adatlap, elnavigálás nélkül.
              openInModal
              deleteHref={canDelete ? (d) => `${DELIVERABLE_BASE_PATH}/${d.id}` : undefined}
              filterable
              columns={[
                {
                  header: "Anyag",
                  render: (d) =>
                    canEdit ? (
                      <EditableTableCell patchPath={`${DELIVERABLE_BASE_PATH}/${d.id}`} field="projekt_neve" value={d.projekt_neve} />
                    ) : (
                      d.projekt_neve
                    ),
                  sortAccessor: (d) => d.projekt_neve,
                },
                {
                  header: "Állapot",
                  // Nem az általános EditableStatusBadge-t használjuk: az
                  // "Ellenőrzés" (vagy hasonló) állapot itt is neki ütközhet a
                  // visszajelzés-hiány szabálynak (lásd allapotAtallitasa
                  // fentebb), és a lista legördülőjének is ugyanúgy fel kell
                  // dobnia a visszajelzés-űrlapot, nem csak a Kanban-húzásnak.
                  render: (d) => (
                    <span onClick={(e) => e.stopPropagation()}>
                      <SelectDropdown
                        value={d.allapot}
                        options={statusOptions}
                        onChange={(next) => void allapotAtallitasa(d.id, next)}
                        placeholder="Nincs állapot"
                      />
                    </span>
                  ),
                  sortAccessor: (d) => d.allapot,
                },
                {
                  header: "Határidő",
                  render: (d) =>
                    canEdit ? (
                      <EditableTableCell patchPath={`${DELIVERABLE_BASE_PATH}/${d.id}`} field="hatarido" value={d.hatarido} type="date" />
                    ) : (
                      formatDate(d.hatarido)
                    ),
                  sortAccessor: (d) => d.hatarido,
                },
                {
                  header: "Vágás leállítva",
                  render: (d) => formatIdopont(d.vagas_leallitva),
                  sortAccessor: (d) => d.vagas_leallitva,
                },
                {
                  header: "Kiküldve",
                  align: "right",
                  render: (d) => (
                    <StatusBadge
                      label={d.anyag_kikuldve ? "Kiküldve" : "Nincs kiküldve"}
                      tone={d.anyag_kikuldve ? "success" : "warning"}
                    />
                  ),
                  sortAccessor: (d) => (d.anyag_kikuldve ? 1 : 0),
                },
              ]}
            />
          </Card>
        }
      />
      {/* Ha egy áthelyezést a szerver visszajelzés hiánya miatt utasított el
          (lásd kartyaAthelyezes), itt a helye megírni - mentés után a lépés
          magától folytatódik (visszajelzesUtan). */}
      {visszajelzesKerve && (
        <VisszajelzesModal
          deliverableId={visszajelzesKerve.deliverableId}
          onClose={() => setVisszajelzesKerve(null)}
          onSaved={visszajelzesUtan}
          // Automatikusan dobtuk fel - kihagyható, de csak indoklással.
          kihagyhato
        />
      )}
      {/* A tábla-kártyákról felugró ablakban nyíló teljes adatlap (a
          felhasználó kérése) - ugyanaz a nézet, mint a külön oldal. */}
      <RecordDetailModal href={modalHref} onClose={() => setModalHref(null)} />
    </>
  );
}
