import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { formatFt } from "@/lib/ido";
import type { ElkeszultSzerzodes, PerformanceCertificate, ProjektkodBontas } from "@/lib/api";

/** Egy forgatás PAPÍRJAI és KÖLTSÉGE, áttekintésként a projekt adatlapján.
 *
 * Miért itt is, ha egyszer az Utókövetés a papírozás helye? Mert az adatlapot
 * megnyitva a leggyakoribb kérdés az, hogy "megvan-e már minden ehhez a
 * forgatáshoz, és mibe került" - erre eddig el kellett navigálni két másik
 * oldalra. Ez a blokk ezért NÉZET, nem munkafelület: mutatja az állást és az
 * összegeket, a tényleges papírkészítés (generálás, kiküldés, aláírt példány,
 * számla) marad az Utókövetésen, ahol egyszerre több projektre rálátva
 * történik. Így nem lesz két hely ugyanarra a műveletre.
 *
 * A DISZPÓ felől megnyitott projekten ez a blokk nem jelenik meg (lásd
 * ProjectDetailContent `csakDiszpo`): a diszpós munkája a forgatás, a stáb és
 * a technika - a papírozás hetekkel később, más kézben történik. */
export function ProjektPapirokEsKoltsegek({
  projectId,
  projectCodeId,
  szerzodesek,
  tigek,
  bontas,
  lathatKoltseget,
}: {
  projectId: number;
  projectCodeId: number | null;
  szerzodesek: ElkeszultSzerzodes[];
  tigek: PerformanceCertificate[];
  bontas: ProjektkodBontas | null;
  /** A forint összegek a Pénzügy-hozzáféréshez kötöttek - ugyanaz a szabály,
   * mint az utómunka költségénél (lásd ProjectDetailContent). */
  lathatKoltseget: boolean;
}) {
  // A projektkód bontásából EZ a forgatás sora: mibe került ez a nap.
  const sajatSor = bontas?.projektek.find((p) => p.id === projectId) ?? null;
  const utokovetes = `/utokovetes/${projectId}`;

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
      <Card title={`Alvállalkozói szerződések (${szerzodesek.length})`}>
        {szerzodesek.length === 0 ? (
          <p className="text-[13px] text-text-secondary">
            Még nincs elkészült szerződés ehhez a forgatáshoz.
          </p>
        ) : (
          <ul className="space-y-2">
            {szerzodesek.map((sz) => (
              <li key={sz.contract_id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                <span className="text-text-primary">{sz.full_name}</span>
                <span className="flex items-center gap-2">
                  {sz.netto_osszeg != null && lathatKoltseget && (
                    <span className="text-text-secondary">{formatFt(sz.netto_osszeg)}</span>
                  )}
                  {/* Az ALÁÍRT példány a legerősebb állítás: ha megvan, a papír
                      kész - bármit is mond az állapot-mező. */}
                  <StatusBadge
                    label={sz.alairva ? "Aláírva" : (sz.szerzodes_allapota ?? "Készítés alatt")}
                    tone={sz.alairva ? "success" : sz.szerzodes_allapota === "Kiküldve" ? "warning" : "neutral"}
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
        <a href={utokovetes} className="mt-3 block text-[12.5px] text-text-accent hover:underline">
          Szerződés készítése, kiküldése → Utókövetés
        </a>
      </Card>

      <Card title={`Külsős TIG-ek (${tigek.length})`}>
        {tigek.length === 0 ? (
          <p className="text-[13px] text-text-secondary">Még nincs teljesítési igazolás ehhez a forgatáshoz.</p>
        ) : (
          <ul className="space-y-2">
            {tigek.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                <span className="text-text-primary">{t.ceg_neve ?? `TIG #${t.id}`}</span>
                <span className="flex items-center gap-2">
                  {t.netto_osszeg != null && lathatKoltseget && (
                    <span className="text-text-secondary">{formatFt(t.netto_osszeg)}</span>
                  )}
                  {/* A KIFIZETÉS a TIG utolsó lépése - amíg nincs meg, a papír
                      önmagában nem zárja le az ügyet. */}
                  <StatusBadge
                    label={
                      t.szamla_kifizetve
                        ? "Kifizetve"
                        : t.szamla_kihagyva
                          ? "Nincs számla"
                          : (t.allapot ?? "Készítés alatt")
                    }
                    tone={t.szamla_kifizetve ? "success" : t.allapot === "Kiküldve" ? "warning" : "neutral"}
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
        <a href={utokovetes} className="mt-3 block text-[12.5px] text-text-accent hover:underline">
          TIG készítése, számla, kifizetés → Utókövetés
        </a>
      </Card>

      <Card title="Költségek (nettó)">
        {!lathatKoltseget ? (
          <p className="text-[13px] text-text-secondary">
            A forint összegek a Pénzügy-hozzáféréshez kötöttek.
          </p>
        ) : sajatSor === null ? (
          <p className="text-[13px] text-text-secondary">
            {projectCodeId === null
              ? "Nincs projektkód ezen a forgatáson - a költségek a projektkódhoz kötődnek."
              : "Nincs felvezetett költség ehhez a forgatáshoz."}
          </p>
        ) : (
          <>
            <ul className="space-y-1.5 text-[13px]">
              <li className="flex items-center justify-between">
                <span className="text-text-secondary">Külsős stáb</span>
                <span className="tabular-nums text-text-primary">{formatFt(sajatSor.kulsos_koltseg)}</span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-text-secondary">Belsős munkanapok</span>
                <span className="tabular-nums text-text-primary">{formatFt(sajatSor.belsos_koltseg)}</span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-text-secondary">Vágás (utómunka)</span>
                <span className="tabular-nums text-text-primary">{formatFt(sajatSor.vagas_koltseg)}</span>
              </li>
            </ul>
            <div className="mt-2 flex items-center justify-between border-t border-border pt-2 text-[13px]">
              <span className="text-text-secondary">Összesen</span>
              <span className="tabular-nums font-medium text-text-primary">{formatFt(sajatSor.osszesen)}</span>
            </div>
          </>
        )}
        {/* A projektkód-szintű kiadások (bérlés, utazás, egyéb) NEM egy
            forgatáshoz tartoznak, hanem az egész munkához - ezért ott
            látszanak tételesen, nem itt. */}
        {projectCodeId !== null && (
          <a
            href={`/projektek/project-kodok/${projectCodeId}`}
            className="mt-3 block text-[12.5px] text-text-accent hover:underline"
          >
            Tételes bontás és a projektkód kiadásai →
          </a>
        )}
      </Card>
    </div>
  );
}
