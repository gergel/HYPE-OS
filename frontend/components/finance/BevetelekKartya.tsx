import {
  ENTITY_PATHS,
  formatHuf,
  getCurrentUser,
  getFieldTypes,
  getMyPagePermissions,
  getProjectCodeOptions,
  getRevenues,
  Revenue,
} from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { KimenoSzamlaCella } from "@/components/finance/KimenoSzamlaCella";
import { DatumSzuro } from "@/components/finance/DatumSzuro";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { idoszakban } from "@/lib/idoszak";
import { devizaNyom, PENZNEMEK } from "@/lib/penz";
import { canDoAction } from "@/lib/permissions";
import { PENZUGYEK_PAGE, szurtOsszegzes } from "@/components/finance/listaSegedek";

/** A bevétel DÁTUMA a listában és a szűrőben: a pénz beérkezése (fizetés
 * dátuma); amíg az nincs, a számla kiállításáé - így a még ki nem fizetett,
 * de már kiszámlázott bevétel is az időszakához sorolható. */
function bevetelDatuma(r: Revenue): string | null {
  return r.fizetes_datuma ?? r.szamla_kiallitva_datuma ?? null;
}

/** A BEVÉTELEK listája a felvivő űrlappal és a dátum-szűrővel - lásd
 * KiadasokKartya: ugyanígy a Pénzügyek oldalon és a saját
 * /penzugyek/bevetelek oldalán is él. A szűrő az URL `bevetel_tol` /
 * `bevetel_ig` paramétereiből jön. */
export async function BevetelekKartya({ tol, ig }: { tol: string; ig: string }) {
  const [revenues, projectCodes, revenueFieldTypes, currentUser, pagePermissions] = await Promise.all([
    getRevenues(),
    getProjectCodeOptions(),
    getFieldTypes("revenue"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const PAGE = PENZUGYEK_PAGE;
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  // A BEVÉTELNÉL két ÚT van: vagy kézbe kapjuk (kassza), vagy a számlára
  // érkezik - bankkártyát nem fogadunk (lásd backend services/fizetesi_mod.py).
  // A harmadik érték nem út, hanem annak a hiánya: van összeg, de nem mozdult
  // pénz (beszámítás, csere, másik cégen át rendezve).
  const bevetelFizetesiModOptions = revenueFieldTypes.fizetes_modja?.options ?? [
    "Készpénz",
    "Átutalás",
    "Nincs pénzmozgás",
  ];
  // Honnan jött a bevétel: a projektkód és a MUNKA neve. A Revenue maga csak
  // a project_code_id-t hordozza, ezért itt oldjuk fel.
  //
  // Szándékosan nem az ügyfél neve: a régi, Notionból importált kódok
  // többségénél az ügyfél "Ismeretlen ügyfél (Notion import)", vagyis az
  // egész oszlop ugyanazt a semmit írta ki minden soron. A munka nevéből
  // viszont látszik, miről van szó.
  const bevetelForrasa = new Map(
    projectCodes.map((pc) => [
      pc.id,
      { projektkod: pc.projektkod, projektNev: pc.project_nev || null },
    ]),
  );
  const listazottBevetelek = revenues.filter((r) => idoszakban(bevetelDatuma(r), tol, ig));

  return (
    <Card title={`Bevételek (${listazottBevetelek.length})`}>
      <DatumSzuro
        elotag="bevetel"
        tol={tol}
        ig={ig}
        mire="beérkezés, ennek híján a számla kiállítása"
        osszegzes={szurtOsszegzes(listazottBevetelek)}
      />
      {canCreate && (
        <QuickCreateForm
          postPath={ENTITY_PATHS.revenue}
          addLabel="+ Új bevétel hozzáadása"
          fields={[
            {
              // NEM kötelező (a felhasználó kérése): projektkód nélkül is
              // felvehető a bevétel - a kintlévőség-nézetben nem jelenik
              // meg, az összesítőkbe beszámít.
              name: "project_code_id",
              label: "Project Code (ha van)",
              type: "select",
              options: projectCodes.map((pc) => ({ value: pc.id, label: pc.projektkod })),
            },
            { name: "netto", label: "Nettó", type: "number" },
            {
              name: "fizetes_modja",
              label: "Fizetési mód",
              type: "select",
              options: bevetelFizetesiModOptions.map((m) => ({ value: m, label: m })),
            },
            // Lásd a kiadásnál: az összeg a választott pénznemben értendő,
            // a bevételek közé forintban kerül.
            {
              name: "penznem",
              label: "Pénznem",
              type: "select",
              defaultValue: "HUF",
              options: PENZNEMEK.map((k) => ({ value: k, label: k })),
            },
            {
              name: "arfolyam",
              label: "Árfolyam (Ft)",
              type: "number",
              required: true,
              // Csak devizánál kérdezzük: forintnál nincs mit átváltani, és
              // egy mindig ott álló, üresen hagyott mező azt sugallná,
              // hogy kellene kitölteni. (Üres pénznem is forintot jelent.)
              showIf: { field: "penznem", noneOf: ["", "HUF"] },
            },
          ]}
        />
      )}
      <DataTable<Revenue>
        rows={listazottBevetelek}
        emptyText="Még nincs felvett bevétel - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
        getHref={(r) => `/penzugyek/bevetel/${r.id}`}
        deleteHref={canDelete ? (r) => `${ENTITY_PATHS.revenue}/${r.id}` : undefined}
        filterable
        columns={[
          {
            // Melyik MUNKÁÉRT jött a pénz - a projekt neve, alatta a
            // projektkód. Enélkül a soron nem látszik, honnan jött.
            header: "Honnan",
            render: (r) => {
              const forras = bevetelForrasa.get(Number(r.project_code_id));
              if (!forras) return "–";
              return (
                <span className="flex flex-col">
                  <span>{forras.projektNev ?? forras.projektkod}</span>
                  {forras.projektNev && <span className="text-[12px] text-text-muted">{forras.projektkod}</span>}
                </span>
              );
            },
            sortAccessor: (r) => {
              const forras = bevetelForrasa.get(Number(r.project_code_id));
              return forras ? `${forras.projektNev ?? ""} ${forras.projektkod}` : "";
            },
          },
          {
            header: "Forma",
            render: (r) =>
              canEdit ? (
                <EditableTableCell patchPath={`${ENTITY_PATHS.revenue}/${r.id}`} field="bevetel_formaja" value={r.bevetel_formaja} />
              ) : (
                r.bevetel_formaja ?? "–"
              ),
            sortAccessor: (r) => r.bevetel_formaja,
          },
          {
            // A bevétel dátuma (a dátum-szűrő ezt nézi): a beérkezés; ha
            // még nem fizették ki, a számla kiállítása - halványan jelölve.
            header: "Dátum",
            render: (r) =>
              r.fizetes_datuma ? (
                canEdit ? (
                  <EditableTableCell
                    patchPath={`${ENTITY_PATHS.revenue}/${r.id}`}
                    field="fizetes_datuma"
                    value={r.fizetes_datuma}
                    type="date"
                  />
                ) : (
                  r.fizetes_datuma
                )
              ) : r.szamla_kiallitva_datuma ? (
                <span className="flex flex-col">
                  <span>{r.szamla_kiallitva_datuma}</span>
                  <span className="text-[12px] text-text-muted">kiállítva, még nincs fizetve</span>
                </span>
              ) : (
                "–"
              ),
            sortAccessor: (r) => bevetelDatuma(r),
          },
          {
            header: "Nettó",
            align: "right",
            render: (r) => (
              <>
                {canEdit ? (
                  <EditableTableCell patchPath={`${ENTITY_PATHS.revenue}/${r.id}`} field="netto" value={r.netto} type="number" />
                ) : (
                  formatHuf(r.netto)
                )}
                {devizaNyom(r) && <span className="mt-0.5 block text-[11.5px] text-text-muted">{devizaNyom(r)}</span>}
              </>
            ),
            sortAccessor: (r) => r.netto,
          },
          {
            header: "Bruttó",
            align: "right",
            render: (r) =>
              canEdit ? (
                <EditableTableCell patchPath={`${ENTITY_PATHS.revenue}/${r.id}`} field="brutto" value={r.brutto} type="number" />
              ) : (
                formatHuf(r.brutto)
              ),
            sortAccessor: (r) => r.brutto,
          },
          {
            // HOGYAN jött be a pénz. Ebből számol a kassza egyenlege (lásd
            // backend services/fizetesi_mod.py) - ezért fix a lista, nem
            // szabad szöveg: egy "kp" és egy "Készpénz" külön kategória
            // lenne, és pont annyival lenne hamis az egyenleg.
            header: "Fizetési mód",
            render: (r) => (
              <EditableStatusBadge
                patchPath={`${ENTITY_PATHS.revenue}/${r.id}`}
                field="fizetes_modja"
                value={r.fizetes_modja}
                options={bevetelFizetesiModOptions}
                placeholder="Nincs megadva"
              />
            ),
            sortAccessor: (r) => r.fizetes_modja,
          },
          {
            // A tárolt összeg mindig forint; ha devizásan vezették fel, az
            // "EUR → HUF" alak mondja meg, mi történt - egy puszta "HUF"
            // elrejtené, hogy a számla euróban szólt.
            header: "Pénznem",
            align: "right",
            render: (r) => (r.eredeti_penznem ? `${r.eredeti_penznem} → HUF` : r.penznem),
            sortAccessor: (r) => r.eredeti_penznem ?? r.penznem,
          },
          // Számla-állapot oszlop SZÁNDÉKOSAN nincs (ahogy a kiadásoknál
          // sem): ami a bevételek közé kerül, az azért kerül oda, mert a
          // pénz rendezve van. A kifizetés jelölése a projektkód "3.
          // Számla" kártyáján történik (határidő → kifizetve), ott jön
          // létre és zárul le ez a sor; a bevétel saját lapján a dátumok
          // továbbra is szerkeszthetők.
          //
          // "Beleszámít" oszlop SZÁNDÉKOSAN nincs a listán: a mező
          // (`beleszamit_a_bevetelekbe`) és a hozzá tartozó indok
          // (`bevetelKihagyasOka`) továbbra is megvan és szerkeszthető a
          // bevétel saját lapján - lásd backend services/elszamolas.py.
          {
            // A kimenő számla PDF-je: maga a számla külső rendszerben
            // készül, ide azért kerül fel, hogy a havi csomagban is benne
            // legyen (lásd SzamlaCsomagLetoltes).
            header: "Számla fájl",
            align: "right",
            render: (r) => (
              <KimenoSzamlaCella
                revenueId={r.id}
                filename={typeof r.szamla_filename === "string" ? r.szamla_filename : null}
                url={typeof r.szamla_file_url === "string" ? r.szamla_file_url : null}
                canEdit={canEdit}
                canDelete={canDelete}
              />
            ),
            sortAccessor: (r) => (r.szamla_filename ? 1 : 0),
          },
        ]}
      />
    </Card>
  );
}
