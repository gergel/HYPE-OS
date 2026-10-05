import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { EszkozArchivalas } from "@/components/EszkozArchivalas";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { StatusBadge } from "@/components/StatusBadge";
import { canDoPageAction } from "@/lib/permissions";
import {
  ENTITY_PATHS,
  getDetailTabs,
  getEszkozForgatasai,
  getFieldTypes,
  getMyPagePermissions,
  getRecord,
  getRecordsByIds,
  getVisibleFields,
} from "@/lib/api";

function datumHu(iso: string): string {
  return iso.replaceAll("-", ".") + ".";
}
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/felszereles";

export default async function EquipmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const equipmentId = Number(id);

  // A "projects" lista az EGYETLEN, ami az equipment rekordtól függ (a
  // project_ids mezőjétől) - a többi csak equipmentId-t vagy semmit nem kér,
  // ezért azok a getRecord-dal EGYSZERRE indulnak, nem utána: egy kevesebb
  // kör az oldalbetöltésnél.
  const [equipment, visibleFields, fieldTypes, dbTabs, pagePermissions, forgatasok] = await Promise.all([
    getRecord(ENTITY_PATHS.equipment, equipmentId),
    getVisibleFields("equipment"),
    getFieldTypes("equipment"),
    getDetailTabs("equipment"),
    getMyPagePermissions(),
    // A forgatások, amiken TÉNYLEG dolgozott (napokkal) - a „hány napot
    // dolgozott” is ebből számol (lásd backend services/eszkoz_statisztika).
    getEszkozForgatasai(equipmentId),
  ]);
  if (!equipment) notFound();

  // A KÖZELGŐ foglalások: a még el nem kezdődött forgatások, amikre az eszköz
  // fel van véve - ezek még nem számítanak munkának, de jó látni őket.
  const projectIds = Array.isArray(equipment.project_ids) ? (equipment.project_ids as number[]) : [];
  const maIso = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Budapest" });
  const dolgozottIdk = new Set(forgatasok.map((f) => f.project_id));
  const kozelgo = (await getRecordsByIds(ENTITY_PATHS.project, projectIds))
    .filter((p) => !dolgozottIdk.has(Number(p.id)) && typeof p.forgatas_datuma === "string" && p.forgatas_datuma > maIso)
    .sort((a, b) => String(a.forgatas_datuma).localeCompare(String(b.forgatas_datuma)));
  const osszesNap = Number(equipment.hany_napot_dolgozott ?? 0);

  // A FORGATÁSOK SZÁMA a „Történet” kártyán áll (a felhasználó kérése) - ez
  // számolt mező, egyik admin-fül sem sorolja fel, ezért eddig egyedül egy
  // külön „Egyéb” kártyát tartott életben. Kódból kerül a történet-fülbe
  // (tab_key „tortenet”, vagy amelyiknek a címe „Történet…”), így egy
  // későbbi fül-átrendezés sem dobja vissza az Egyébbe.
  const tortenetTab =
    dbTabs.find((t) => t.tab_key === "tortenet") ?? dbTabs.find((t) => /történet/i.test(t.label));
  const fulek = dbTabs.map((t) =>
    t === tortenetTab && !t.field_keys.includes("forgatasok_szama")
      ? { ...t, field_keys: [...t.field_keys, "forgatasok_szama"] }
      : t,
  );

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.equipment}/${equipment.id}`,
    // Ugyanaz a szám, amit a lenti „Forgatások” lista felsorol: a forgatások,
    // amiken az eszköz TÉNYLEG dolgozott (a jövőbeli foglalások nélkül).
    record: { ...equipment, forgatasok_szama: forgatasok.length },
    dbTabs: fulek,
    visibleFields,
    fieldTypes,
    pagePermissions,
    // A „hány forgatáson vett részt” ugyanazt mondja, mint a forgatások száma
    // - kétszer kiírva csak zavarna.
    alwaysHidden: ["project_ids", "hany_forgatason_vett_reszt", "archivalva_at", "archivalta_id", "archivalas_oka"],
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href="/felszereles" label="Felszerelés" />
          <h1 className="t-page">{String(equipment.nev ?? `Eszköz #${equipment.id}`)}</h1>
          <EszkozArchivalas
            equipmentId={equipment.id}
            archivalvaAt={(equipment.archivalva_at as string | null) ?? null}
            archivalasOka={(equipment.archivalas_oka as string | null) ?? null}
            canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
          />
        </div>

        <DetailSections sections={tabs} />

        <Card title={`Forgatások (${forgatasok.length} forgatás · ${osszesNap} nap)`}>
          {forgatasok.length === 0 ? (
            <p className="text-[13px] text-text-muted">Ez az eszköz még egyetlen forgatáson sem dolgozott.</p>
          ) : (
            <ul className="divide-y divide-border">
              {forgatasok.map((f) => (
                <li key={f.project_id}>
                  <a
                    href={`/projektek/${f.project_id}`}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-[13.5px] hover:bg-surface-3"
                  >
                    <span className="min-w-0 flex-1 font-medium text-text-primary">
                      {f.nev}
                      {f.helyszin && <span className="ml-1.5 font-normal text-text-muted">· {f.helyszin}</span>}
                    </span>
                    <span className="tabular-nums text-text-secondary">
                      {datumHu(f.kezdet)}
                      {f.vege !== f.kezdet ? ` – ${datumHu(f.vege).slice(5)}` : ""}
                    </span>
                    <span className="w-14 text-right font-semibold tabular-nums text-text-primary">{f.napok} nap</span>
                    <StatusBadge
                      label={f.forras === "kivitel" ? "Eszközkivitel" : "Foglalás"}
                      tone={f.forras === "kivitel" ? "success" : "neutral"}
                    />
                  </a>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-[12px] text-text-muted">
            Minden nap egy napnak számít, amin az eszköz dolgozott (pár óra is) - egy napon két forgatás is egy
            nap. Ahol van eszközkivitel, ott a kint töltött napok számítanak, máshol a foglalás és a forgatás
            napjai. A jövőbeli foglalások még nem számítanak.
          </p>
          {kozelgo.length > 0 && (
            <div className="mt-4 border-t border-border pt-3">
              <p className="t-label mb-2">Közelgő foglalások ({kozelgo.length})</p>
              <RelatedTable rows={kozelgo} emptyText="" getHref={(p) => `/projektek/${p.id}`} />
            </div>
          )}
        </Card>

        {/* A Foglalások lista lekerült (a felhasználó kérése) - a foglalások
            a projekteken, a technika-szekcióban kezelhetők. */}
      </div>
    </div>
  );
}
