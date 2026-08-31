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
import { VisszajelzesModal } from "@/components/deliverable/FeedbackSendButton";
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
}: {
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

  const statusColumns: BoardColumn[] = useMemo(() => {
    const byStatus = new Map<string, Deliverable[]>();
    for (const d of deliverables) {
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
  }, [deliverables, statusOptions, allapotBeallitasok, kartyaMezok, canEdit, employeeName, timerNevek]);

  const vinyoColumns: BoardColumn[] = useMemo(() => {
    const byVinyo = new Map<string, Deliverable[]>();
    for (const d of deliverables) {
      for (const v of d.vinyok ?? []) {
        if (!byVinyo.has(v)) byVinyo.set(v, []);
        byVinyo.get(v)!.push(d);
      }
    }
    return vinyoOptions
      .filter((v) => (byVinyo.get(v)?.length ?? 0) > 0)
      .map((v) => ({ key: v, label: v, cards: byVinyo.get(v)!.map((d) => toCard(d, d.allapot ? [d.allapot] : [])) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deliverables, vinyoOptions, kartyaMezok, employeeName, timerNevek]);

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
                  />
                ) : undefined
              }
            >
              {/* Szerkesztési joggal a kártyák áthúzhatók másik oszlopba - ez
                  írja át az anyag állapotát. */}
              <DeliverableBoard columns={statusColumns} onAthelyezes={canEdit ? kartyaAthelyezes : undefined} />
            </Card>
            <Card title="Forgatások naptár">
              <ForgatasokCalendar projects={calendarProjects} />
            </Card>
            <Card title="Vinyók szerint">
              <DeliverableBoard columns={vinyoColumns} />
            </Card>
          </div>
        }
        list={
          <Card title={`Utómunka (${deliverables.length})`}>
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
              rows={deliverables}
              emptyText="Még nincs felvett vágandó anyag - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
              getHref={(d) => `/utomunka/${d.id}`}
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
        />
      )}
    </>
  );
}
