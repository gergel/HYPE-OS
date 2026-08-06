"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { formatIdopont } from "@/lib/ido";
import { humanizeKey } from "@/lib/mezoNev";
import { useLiveTopic } from "@/lib/live";
import { AllapotBeallitasok } from "@/components/deliverable/AllapotBeallitasok";
import { DeliverableBoard, type BoardCard, type BoardColumn } from "@/components/deliverable/DeliverableBoard";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import { UtomunkaViewTabs } from "@/components/deliverable/UtomunkaViewTabs";
import type { AllapotBeallitas, Deliverable, Employee } from "@/lib/api";

// Nem importáljuk az ENTITY_PATHS-t a lib/api.ts-ből (bár csak egy sima
// konstans) - az a modul a `next/headers`-t is importálja (szerver-oldali
// cookie-olvasáshoz), és egy kliens komponensbe akár csak egyetlen NEM
// type-only importja is beviszi a teljes modult a kliens bundle-be, ami
// build hibát okoz ("next/headers" csak Server Component-ekben érhető el).
const DELIVERABLE_BASE_PATH = "/api/v1/deliverables";

const NO_STATUS_KEY = "__nincs_allapot__";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

type CalendarProject = { id: number; nev: string; forgatas_datuma: string | null; forgatas_datuma_vege: string | null };

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
    // Beállítás nélkül marad az eddigi alapértelmezés (határidő + kiosztva),
    // hogy a tábla ne ürüljön ki azoknál, akik sosem nyúlnak a beállításhoz.
    const alapertelmezett = kartyaMezok.length === 0;
    const subtitleParts = alapertelmezett
      ? [
          d.hatarido ? `Határidő: ${formatDate(d.hatarido)}` : null,
          d.assigned_to_employee_id ? `Kiosztva: ${employeeName.get(d.assigned_to_employee_id) ?? "?"}` : null,
        ].filter((p): p is string => p !== null)
      : [];
    const mezok = alapertelmezett
      ? []
      : kartyaMezok
          .map((kulcs) => ({ cimke: humanizeKey(kulcs), ertek: mezoErteke(d, kulcs) }))
          .filter((m): m is { cimke: string; ertek: string } => m.ertek !== null);
    return {
      id: d.id,
      href: `/utomunka/${d.id}`,
      title: d.projekt_neve,
      subtitle: subtitleParts.length > 0 ? subtitleParts.join(" · ") : null,
      badges,
      mezok,
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
      ...(byStatus.has(NO_STATUS_KEY)
        ? [{ key: NO_STATUS_KEY, label: "Nincs állapot", cards: byStatus.get(NO_STATUS_KEY)!.map((d) => toCard(d, d.vinyok ?? [])) }]
        : []),
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deliverables, statusOptions, allapotBeallitasok, kartyaMezok, employeeName]);

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
  }, [deliverables, vinyoOptions, kartyaMezok, employeeName]);

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
            <DeliverableBoard columns={statusColumns} />
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
              fields={[
                { name: "projekt_neve", label: "Anyag neve", required: true },
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
                render: (d) => (
                  <EditableStatusBadge
                    patchPath={`${DELIVERABLE_BASE_PATH}/${d.id}`}
                    field="allapot"
                    value={d.allapot}
                    options={statusOptions}
                  />
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
  );
}
