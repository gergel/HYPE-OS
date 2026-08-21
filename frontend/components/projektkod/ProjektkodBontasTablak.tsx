import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { ENTITY_PATHS, formatHuf, type ProjektkodBontas } from "@/lib/api";
import { Clapperboard, Receipt, Scissors } from "lucide-react";

/** Mért idő emberi alakban: 95 perc -> "1 ó 35 p".
 *
 * Percben kiírva egy hosszabb vágás (pl. 730 perc) semmit nem mond ránézésre -
 * pont az a kérdés, hány napi munka van benne. */
function idoSzoveg(percek: number): string {
  if (!percek) return "–";
  const ora = Math.floor(percek / 60);
  const perc = Math.round(percek % 60);
  if (!ora) return `${perc} p`;
  return perc ? `${ora} ó ${perc} p` : `${ora} ó`;
}

/** A projektkód TÉTELES bontása: forgatásonként, anyagonként, kiadásonként.
 *
 * A fejléc négy összege megmondja, mennyi ment el - ezek a táblák azt, hogy
 * MIRE. A számok ugyanabból a forrásból jönnek, mint az összesítés (lásd
 * backend services/projektkod_bontas.py), tehát a tételek összege a
 * fejléc-számot adja ki, nem egy másik igazságot.
 *
 * A sorok TÖRÖLHETŐK is: itt látszik, mi terheli a kódot, tehát itt derül ki,
 * ha valami tévedésből került rá - és a javításhoz eddig három másik oldalra
 * kellett elnavigálni. A törlés a rekord SAJÁT végpontjára megy, tehát
 * ugyanazt a jogosultságot kéri, mint a saját oldalán (a forgatás a
 * Projektekét, az anyag az Utómunkáét, a kiadás a Pénzügyekét) - ezért kap
 * mindhárom tábla külön kapcsolót, nem egy közöset. */
export function ProjektkodBontasTablak({
  bontas,
  torolhetForgatast = false,
  torolhetUtomunkat = false,
  torolhetKiadast = false,
}: {
  bontas: ProjektkodBontas;
  torolhetForgatast?: boolean;
  torolhetUtomunkat?: boolean;
  torolhetKiadast?: boolean;
}) {
  const kulsosKiadas = bontas.kiadasok.filter((k) => k.resz === "kulsos");
  const egyebKiadas = bontas.kiadasok.filter((k) => k.resz === "egyeb");

  return (
    <>
      {/* FORGATÁSOK: mibe került egy-egy nap. A több napra szóló TIG összege a
          napok közt fel van osztva (lásd backend kulsos_koltseg._tig_resze),
          ezért itt naponta látszik, mennyi jut rá. */}
      <Card title={`Forgatások (${bontas.projektek.length})`} icon={Clapperboard}>
        <DataTable
          rows={bontas.projektek}
          emptyText="Nincs forgatás ehhez a projektkódhoz."
          getHref={(p) => `/projektek/${p.id}`}
          deleteHref={torolhetForgatast ? (p) => `${ENTITY_PATHS.project}/${p.id}` : undefined}
          columns={[
            {
              header: "Forgatás",
              render: (p) => p.nev ?? `#${p.id}`,
              sortAccessor: (p) => p.nev,
            },
            {
              header: "Dátum",
              render: (p) => p.forgatas_datuma ?? "–",
              sortAccessor: (p) => p.forgatas_datuma,
            },
            {
              header: "Külsős stáb",
              align: "right",
              render: (p) => formatHuf(p.kulsos_koltseg),
              sortAccessor: (p) => p.kulsos_koltseg,
            },
            {
              header: "Belsős napidíj",
              align: "right",
              render: (p) => formatHuf(p.belsos_koltseg),
              sortAccessor: (p) => p.belsos_koltseg,
            },
            {
              header: "Vágás",
              align: "right",
              render: (p) => formatHuf(p.vagas_koltseg),
              sortAccessor: (p) => p.vagas_koltseg,
            },
            {
              header: "Összesen",
              align: "right",
              render: (p) => <span className="font-medium text-text-primary">{formatHuf(p.osszesen)}</span>,
              sortAccessor: (p) => p.osszesen,
            },
          ]}
        />
      </Card>

      {/* UTÓMUNKA: melyik anyagot meddig vágtuk, és mennyibe került. */}
      <Card title={`Utómunka (${bontas.utomunkak.length})`} icon={Scissors}>
        <DataTable
          rows={bontas.utomunkak}
          emptyText="Nincs vágandó anyag ehhez a projektkódhoz."
          getHref={(u) => `/utomunka/${u.id}`}
          deleteHref={torolhetUtomunkat ? (u) => `${ENTITY_PATHS.deliverable}/${u.id}` : undefined}
          columns={[
            {
              header: "Anyag",
              render: (u) => u.nev ?? `#${u.id}`,
              sortAccessor: (u) => u.nev,
            },
            {
              header: "Vágó",
              render: (u) => u.vago_nev ?? "–",
              sortAccessor: (u) => u.vago_nev,
            },
            {
              header: "Mennyi ideig vágtuk",
              align: "right",
              render: (u) => idoSzoveg(u.percek),
              sortAccessor: (u) => u.percek,
            },
            {
              header: "Költség",
              align: "right",
              render: (u) => formatHuf(u.koltseg),
              sortAccessor: (u) => u.koltseg,
            },
          ]}
        />
      </Card>

      {/* KIADÁSOK: minden kiadás-sor, ami erre a kódra terhel. A TIG-ekből
          keletkezett sorok kimaradnak - azok ugyanaz a pénz, amit a forgatások
          "Külsős stáb" oszlopa már mutat. A besorolás azért látszik, mert a
          külsős sorok a fejléc KÜLSŐS részébe esnek, nem az egyébbe. */}
      <Card title={`Egyéb projekt kiadások (${bontas.kiadasok.length})`} icon={Receipt}>
        <p className="mb-3 text-[12.5px] text-text-muted">
          Egyéb: {formatHuf(egyebKiadas.reduce((s, k) => s + k.osszeg, 0))}
          {kulsosKiadas.length > 0 && (
            <> · Külsős kifizetés (TIG-en kívül): {formatHuf(kulsosKiadas.reduce((s, k) => s + k.osszeg, 0))}</>
          )}
          . A TIG-ekből keletkezett kiadás-sorok itt nem szerepelnek: azok a forgatások „Külsős stáb” oszlopában
          vannak, ugyanaz a pénz lenne kétszer.
        </p>
        <DataTable
          rows={bontas.kiadasok}
          emptyText="Nincs kiadás ehhez a projektkódhoz."
          getHref={(k) => `/penzugyek/kiadas/${k.id}`}
          deleteHref={torolhetKiadast ? (k) => `${ENTITY_PATHS.expense}/${k.id}` : undefined}
          columns={[
            {
              header: "Dátum",
              render: (k) => k.datum ?? "–",
              sortAccessor: (k) => k.datum,
            },
            {
              header: "Megnevezés",
              render: (k) => k.megnevezes ?? "–",
              sortAccessor: (k) => k.megnevezes,
            },
            {
              header: "Kinek",
              render: (k) => k.kinek ?? "–",
              sortAccessor: (k) => k.kinek,
            },
            {
              header: "Besorolás",
              render: (k) => (k.resz === "kulsos" ? "Külsős" : "Egyéb"),
              sortAccessor: (k) => k.resz,
            },
            {
              header: "Összeg (nettó)",
              align: "right",
              render: (k) => formatHuf(k.osszeg),
              sortAccessor: (k) => k.osszeg,
            },
            {
              header: "Állapot",
              align: "right",
              render: (k) => (
                <StatusBadge label={k.kifizetve ? "Kifizetve" : "Nyitott"} tone={k.kifizetve ? "success" : "warning"} />
              ),
              sortAccessor: (k) => (k.kifizetve ? 1 : 0),
            },
          ]}
        />
      </Card>
    </>
  );
}
