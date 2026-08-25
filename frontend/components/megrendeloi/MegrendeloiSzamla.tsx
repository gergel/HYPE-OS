"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ModalReteg } from "@/components/ModalReteg";
import { authFetch } from "@/lib/authFetch";
// A pénzformázó a FÜGGŐSÉG NÉLKÜLI modulból jön: a lib/api.ts a
// "next/headers"-t is behúzza (szerver-oldali süti-olvasás), és egy kliens
// komponensben már egyetlen nem type-only importja is build hibát okoz.
import { devizas, formatHuf, penzzel } from "@/lib/penz";
import type { MegrendeloiSzamlaAllas } from "@/lib/api";

/** A mai nap ISO alakban, HELYI idő szerint - a `toISOString()` UTC-re vált, és
 * este 10 után már a következő napot adná vissza. */
function maiNap(): string {
  const most = new Date();
  return `${most.getFullYear()}-${String(most.getMonth() + 1).padStart(2, "0")}-${String(most.getDate()).padStart(2, "0")}`;
}

/** A megrendelői papírozás HARMADIK lépése egy projektkódon: a számla.
 *
 * Ugyanaz a menet, mint az alvállalkozói oldalon, csak fordítva: ott mi
 * fizetünk, itt minket fizetnek.
 *
 *   "Kifizetve" (a kifizetés napjával) -> bevétel-sor
 *
 * A fizetési határidőt és a "kifizetve" jelzőt fájlonként, a feltöltött
 * számláknál lehet megadni (lásd DokumentumFeltoltes) - ez a kártya csak a
 * PROJEKTKÓD egészének lezárását intézi: a "Kifizetve" gombra kattintva
 * nyílik (vagy egészül ki) a bevétel-sor a Pénzügyekben, hogy azt ne kelljen
 * külön, kézzel felvezetni. */
export function MegrendeloiSzamla({
  projectCodeId,
  allas,
  canEdit,
}: {
  projectCodeId: number;
  allas: MegrendeloiSzamlaAllas;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [dialogNyitva, setDialogNyitva] = useState(false);
  const [kihagyasNyitva, setKihagyasNyitva] = useState(false);

  async function hivas(ut: string, torzs?: unknown) {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/megrendeloi-papirok/szamla/${projectCodeId}/${ut}`, {
        method: "POST",
        body: JSON.stringify(torzs ?? {}),
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        setHiba(reszlet?.detail ?? `Sikertelen művelet (HTTP ${res.status})`);
        return false;
      }
      router.refresh();
      return true;
    } catch (err) {
      setHiba(`Sikertelen művelet (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {/* A NETTÓ áll elöl: az elszámolásban (bevétel, profit) mindenütt az
          a mérvadó - lásd backend services/elszamolas.py. A bruttót
          mellétesszük, ha eltér: annyi érkezik a bankszámlára.
          A fizetési állapotot (határidő, kifizetve-e) itt szándékosan nem
          jelezzük külön jelvénnyel - azt fájlonként, a feltöltött
          számláknál mutatjuk (lásd DokumentumFeltoltes), a projektkód
          egészének lezárását pedig a lenti "Kifizetve" gomb és az alatta
          megjelenő összegzés mutatja. */}
      {allas.netto !== null && (
        <p className="text-[12.5px] text-text-secondary">
          {penzzel(allas.netto, allas.penznem)} nettó
          {allas.brutto !== null && allas.brutto !== allas.netto && (
            <span className="text-text-muted"> ({penzzel(allas.brutto, allas.penznem)} bruttó)</span>
          )}
        </p>
      )}

      {/* Devizás munkánál a bevétel FORINTBAN kerül a Pénzügyekbe - ki is
          írjuk, mennyi az, mert a szerződésen szereplő euró összeg önmagában
          nem mondja meg (lásd backend services/penznem.py). */}
      {devizas(allas.penznem) && (
        <p className="text-[12.5px] text-text-secondary">
          {allas.netto_forintban === null
            ? "Add meg az árfolyamot a vállalási árnál - enélkül nem tudjuk, mennyi a bevétel forintban."
            : `A bevételek közé ${formatHuf(allas.netto_forintban)} kerül${
                allas.arfolyam === null ? "" : ` (${allas.arfolyam} Ft/${allas.penznem} árfolyamon)`
              }.`}
        </p>
      )}

      {/* "Erről a munkáról nincs számla" - van, amit nem a megszokott módon
          fizetnek (beszámítás, csere, másik cégen át rendezve). Ilyenkor nincs
          határidő sem, a projektkódot viszont le kell tudni zárni. */}
      {!allas.kifizetve && canEdit && !allas.szamla_kihagyva && (
        <button
          type="button"
          disabled={busy}
          onClick={() => setKihagyasNyitva(true)}
          className="text-[12.5px] text-text-muted hover:text-text-primary disabled:opacity-50"
        >
          Nincs számla erről a munkáról
        </button>
      )}
      {allas.szamla_kihagyva && (
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 p-2.5">
          <p className="text-[12.5px] text-text-secondary">
            Nincs számla erről a munkáról – fizetési határidő sem kell.
          </p>
          {allas.szamla_kihagyas_oka && (
            <p className="mt-0.5 whitespace-pre-line text-[12.5px] text-text-muted">{allas.szamla_kihagyas_oka}</p>
          )}
          {canEdit && !allas.kifizetve && (
            <button
              type="button"
              disabled={busy}
              onClick={() => hivas("nincs-szamla", { kihagyva: false })}
              className="mt-1 text-[12px] text-text-muted hover:text-text-primary disabled:opacity-50"
            >
              Mégis van számla
            </button>
          )}
        </div>
      )}

      {allas.kifizetve ? (
        <div className="space-y-1.5">
          {/* Tranzakció nélküli lezárásnál nincs dátum - és ez nem hiány,
              hanem maga a válasz: nem volt pénzmozgás. Egy "Kifizetve: –" sor
              itt hiányzó adatnak látszana. */}
          {allas.tranzakcio_nelkul_lezarva ? (
            <p className="text-[13px] text-text-secondary">
              Rendezve, <span className="text-text-primary">tranzakció nélkül</span>
              <span className="text-text-muted"> · nem keletkezett bevétel-sor</span>
            </p>
          ) : (
            <p className="text-[13px] text-text-secondary">
              Kifizetve: <span className="text-text-primary">{allas.kifizetes_datuma ?? "–"}</span>
              {allas.bevetelbe_ne_keruljon ? (
                <span className="text-text-muted"> · a bevétel-sor nem számít az éves bevételbe</span>
              ) : (
                <span className="text-text-muted"> · {allas.bevetel_sorok} bevétel-sor a Pénzügyekben</span>
              )}
            </p>
          )}
          {/* Attól, hogy az ÉVES bevételbe nem való (máshogy van rendezve), a
              pénz megjött - tehát a PROJEKT bevételébe és profitjába
              beleszámít. Ki is írjuk, különben úgy nézne ki, mintha ez a munka
              ingyen lett volna. A bevétel-sor a Pénzügyekben is ott van,
              "Beleszámít: nem" jelöléssel (lásd backend
              services/elszamolas.py). */}
          {allas.bevetelbe_ne_keruljon && allas.netto !== null && (
            <p className="text-[13px] text-text-secondary">
              A projekt bevételébe beleszámít:{" "}
              <span className="text-text-primary">{formatHuf(allas.netto)} nettó</span>
              <span className="text-text-muted">
                {" "}
                – ez adja a fenti profitot. A Pénzügyekben a sor látszik, de az éves bevételbe nem számít.
              </span>
            </p>
          )}
          {allas.bevetel_kihagyas_oka && (
            <p className="whitespace-pre-line text-[12.5px] text-text-muted">{allas.bevetel_kihagyas_oka}</p>
          )}
          {/* HOGYAN érkezett a pénz. Készpénznél ki is mondjuk, mi lesz belőle
              a kasszában: számlával sima legális bevétel, számla nélkül
              FEDEZET a számla nélküli kiadásokhoz (lásd backend
              services/megrendeloi_szamla.py). */}
          {allas.fizetes_modja && !allas.tranzakcio_nelkul_lezarva && (
            <p className="text-[13px] text-text-secondary">
              {allas.fizetes_modja}
              {allas.keszpenzes && (
                <span className="text-text-muted">
                  {" "}
                  · a <a href="/penzugyek/kp-forgalom" className="text-text-accent hover:underline">KP forgalomban</a> is
                  szerepel,{" "}
                  {allas.van_szamla_a_bevetelen
                    ? "számlával – legális bevétel"
                    : "számla nélkül – fedezet a számla nélküli kiadásokhoz"}
                </span>
              )}
            </p>
          )}
          {canEdit && (
            <button
              type="button"
              disabled={busy}
              onClick={() => hivas("visszavonas")}
              className="text-[12.5px] text-text-muted hover:text-text-primary disabled:opacity-50"
            >
              Mégsincs kifizetve
            </button>
          )}
        </div>
      ) : (
        canEdit && (
          <button
            type="button"
            disabled={busy}
            onClick={() => setDialogNyitva(true)}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            {allas.kifizetes_datum_kell ? "Kifizetve" : "Rendezve"}
          </button>
        )
      )}

      {hiba && <p className="text-[12.5px] text-text-danger">{hiba}</p>}

      {kihagyasNyitva && (
        <NincsSzamlaDialog
          onMegse={() => setKihagyasNyitva(false)}
          onJelol={async (oka) => {
            const sikeres = await hivas("nincs-szamla", { kihagyva: true, oka });
            if (sikeres) setKihagyasNyitva(false);
          }}
        />
      )}

      {dialogNyitva && (
        <KifizetesDialog
          hatarido={allas.fizetesi_hatarido}
          datumKell={allas.kifizetes_datum_kell}
          osszeg={
            allas.netto === null
              ? null
              : `${formatHuf(allas.netto)} nettó` +
                (allas.brutto !== null && allas.brutto !== allas.netto ? ` (${formatHuf(allas.brutto)} bruttó)` : "")
          }
          // Készpénznél ettől függ, hogy legális bevétel lesz-e belőle a
          // kasszában, vagy fedezet - a felhasználó előre lássa, melyik.
          vanSzamla={allas.van_szamla_fajl && !allas.szamla_kihagyva}
          onMegse={() => setDialogNyitva(false)}
          onJelol={async (adat) => {
            const sikeres = await hivas("kifizetve", adat);
            if (sikeres) setDialogNyitva(false);
          }}
        />
      )}
    </div>
  );
}

/** "Kifizetve" - a kifizetés napjával, és azzal a döntéssel, hogy bekerüljön-e
 * a Pénzügyek bevételei közé.
 *
 * A DÁTUM azért kérdés, mert a jelölés ritkán esik egybe a beérkezéssel: a
 * pénz megjön, és csak napokkal később kattint rá valaki - ha ilyenkor a mai
 * nap kerülne be, a bevétel rossz napon (rosszabb esetben rossz hónapban)
 * állna.
 *
 * A BEVÉTEL azért kérdés, mert van munka, ami ki van fizetve, de a Pénzügyekbe
 * nem való: beszámították, más cégen át folyt be, vagy máshol már el van
 * könyvelve. Ilyenkor egy itteni bevétel-sor megkétszerezné az összeget -
 * viszont a projektkódnak ugyanúgy lezártnak kell lennie, hogy ne álljon
 * örökre a teendők között. Ezért kérünk hozzá indokot. */
function KifizetesDialog({
  hatarido,
  datumKell,
  osszeg,
  onMegse,
  onJelol,
  vanSzamla,
}: {
  hatarido: string | null;
  /** Kötelező-e a dátum. Ahol számlát sem várunk (nincs számla / papír nélkül
   * elszámolt / elmaradt), ott a legtöbbször nincs is tranzakció - ilyenkor a
   * "mikor érkezett meg a pénz" kérdésre nincs igaz válasz, és üresen hagyva
   * TRANZAKCIÓ NÉLKÜLI lezárás lesz belőle (lásd backend
   * services/megrendeloi_szamla._kifizetes_datum_kell). */
  datumKell: boolean;
  osszeg: string | null;
  onMegse: () => void;
  onJelol: (adat: {
    /** `null`, ha üresen hagyták: a szerver ebből tudja, hogy tranzakció
     * nélküli lezárás. Üres SZÖVEGET nem küldünk - egy dátum-mezőre az nem
     * érvényes érték, a szerver 422-vel utasítaná el. */
    kifizetes_datuma: string | null;
    bevetelbe_ne_keruljon: boolean;
    kihagyas_oka: string | null;
    /** "Átutalás" vagy "Készpénz" - tranzakció nélküli lezárásnál null. */
    fizetes_modja: string | null;
  }) => void;
  /** Van-e számla a bevétel mögött. Készpénznél ez dönti el, hogy a kasszában
   * sima legális bevétel lesz-e belőle, vagy FEDEZET a számla nélküli
   * kiadásokhoz. */
  vanSzamla: boolean;
}) {
  // ÜRESEN indul, NEM a mai nappal. A jelölés ritkán esik egybe a
  // beérkezéssel: a pénz megjön, és csak napokkal később kattint rá valaki -
  // egy előre kitöltött "ma" ilyenkor nem segítség, hanem egy csendben beírt
  // rossz dátum, ami utólag fel sem tűnik (nem üres, csak nem igaz). Ebből
  // lesz a bevétel-sor dátuma, tehát rossz hónapba is csúszhat a bevétel.
  // A "Ma" gomb egy kattintás annak, akinél tényleg ma jött meg.
  const [datum, setDatum] = useState("");
  const [bevetelbeKerul, setBevetelbeKerul] = useState(true);
  const [indok, setIndok] = useState("");
  // Átutalással indul, mert az a gyakori - de a KÉSZPÉNZ nem ugyanaz a
  // pénzmozgás: az a kasszába kerül, tehát tudni kell róla (lásd backend
  // services/kassza.py). Ezért választás, nem tippelés.
  const [mod, setMod] = useState<"Átutalás" | "Készpénz">("Átutalás");

  return (
    <ModalReteg onClose={onMegse}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">
            {datumKell ? "Megrendelői számla kifizetve" : "A munka rendezve"}
          </h3>
          {osszeg && <p className="mt-0.5 text-[12.5px] text-text-secondary">{osszeg}</p>}
        </div>

        <div className="p-5">
          <label className="block text-[13px] text-text-primary">
            Mikor érkezett meg a pénz{datumKell ? " *" : ""}
            <span className="mt-1 flex items-center gap-2">
              <input
                type="date"
                value={datum}
                onChange={(e) => setDatum(e.target.value)}
                className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary"
              />
              <button
                type="button"
                onClick={() => setDatum(maiNap())}
                className="shrink-0 rounded-[var(--radius)] border border-border px-2 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-3"
              >
                Ma
              </button>
            </span>
            <span className="mt-0.5 block text-[12px] text-text-muted">
              {datumKell
                ? "Kötelező – ez a nap kerül a bevétel-sorra is."
                : "Nem kötelező: erről a munkáról nincs számla, és ilyenkor a legtöbbször pénzmozgás sincs. Üresen hagyva tranzakció nélkül zárjuk le – nem keletkezik bevétel-sor."}
              {hatarido && ` Fizetési határidő: ${hatarido}.`}
            </span>
          </label>

          {/* A bevétel-sor kérdése csak akkor merül fel, ha VAN dátum: egy
              tranzakció nélküli lezárásnál nincs mit dátumozni a soron, tehát
              sor sem keletkezik. */}
          {/* HOGYAN érkezett: ez dönti el, hogy a pénz a bankszámlán van-e,
              vagy a KASSZÁBAN. Csak akkor kérdés, ha volt tranzakció. */}
          {datum && (
            <div className="mt-4">
              <p className="text-[13px] text-text-primary">Hogyan érkezett a pénz?</p>
              <div className="mt-1.5 flex gap-2">
                {(["Átutalás", "Készpénz"] as const).map((lehetoseg) => (
                  <button
                    key={lehetoseg}
                    type="button"
                    onClick={() => setMod(lehetoseg)}
                    className={`rounded-[var(--radius)] border px-3 py-1.5 text-[13px] ${
                      mod === lehetoseg
                        ? "border-text-accent/40 bg-bg-accent text-text-accent"
                        : "border-border text-text-secondary hover:bg-surface-3"
                    }`}
                  >
                    {lehetoseg}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-[12px] text-text-muted">
                {mod === "Készpénz" ? (
                  <>
                    A bevételek közé is bekerül, <b>és a kasszába is</b> – a KP forgalomban ugyanez a sor jelenik meg.{" "}
                    {vanSzamla
                      ? "Van mögötte számla, tehát legális bevétel."
                      : "Nincs mögötte számla, tehát fedezet: a számla nélküli kiadásokat csökkenti."}
                  </>
                ) : (
                  "A bankszámlára érkezett – a bevételek közé kerül, a kasszát nem mozgatja."
                )}
              </p>
            </div>
          )}

          {datum && (
            <>
              <label className="mt-4 flex cursor-pointer items-start gap-2.5">
                <input
                  type="checkbox"
                  checked={bevetelbeKerul}
                  onChange={(e) => setBevetelbeKerul(e.target.checked)}
                  className="mt-0.5"
                />
                <span className="text-[13px] text-text-primary">
                  Kerüljön be a Pénzügy → Bevételek közé
                  <span className="mt-0.5 block text-[12px] text-text-muted">
                    Ez hozza létre (vagy egészíti ki) a bevétel-sort, és így számít bele a pénzügyi összesítőkbe.
                  </span>
                </span>
              </label>

              {!bevetelbeKerul && (
                <div className="mt-3 space-y-2 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
                  <p className="text-[12.5px] text-text-secondary">
                    A projektkód „kifizetve” lesz, de <b>nem keletkezik bevétel-sor</b> – akkor válaszd ezt, ha a
                    pénz máshol van elszámolva, és itt csak duplázná az összeget.
                  </p>
                  <label className="block text-[13px] text-text-primary">
                    Miért nem kerül a bevételek közé?
                    <textarea
                      rows={2}
                      value={indok}
                      onChange={(e) => setIndok(e.target.value)}
                      placeholder="Pl. beszámítva a bérleti díjba, a másik cégen át számláztuk…"
                      className="mt-1 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] leading-relaxed text-text-primary"
                    />
                  </label>
                </div>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onMegse}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Mégse
          </button>
          <button
            type="button"
            disabled={(datumKell && !datum) || (!!datum && !bevetelbeKerul && !indok.trim())}
            onClick={() =>
              onJelol({
                kifizetes_datuma: datum || null,
                bevetelbe_ne_keruljon: !bevetelbeKerul,
                kihagyas_oka: bevetelbeKerul ? null : indok.trim(),
                // Tranzakció nélküli lezárásnál nincs mit módozni: nem mozdult
                // pénz sem a bankszámlán, sem a kasszában.
                fizetes_modja: datum ? mod : null,
              })
            }
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            {datum ? "Kifizetve jelölés" : "Rendezve, tranzakció nélkül"}
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}

/** "Erről a munkáról nincs számla" - indokkal.
 *
 * Van, amit nem a megszokott módon fizetnek: beszámítás, csere, egy másik
 * cégen át rendezett tétel. Ilyenkor nincs kiállított számla, tehát fizetési
 * határidő sincs - a projektkódot viszont le kell tudni zárni, különben
 * örökre ott áll a teendők között.
 *
 * Az INDOK azért kötelező, mert fél év múlva ez az egyetlen dolog, amiből
 * kiderül, mi történt: enélkül csak annyi látszana, hogy erről az egy munkáról
 * nincs papír. */
function NincsSzamlaDialog({ onMegse, onJelol }: { onMegse: () => void; onJelol: (oka: string) => void }) {
  const [indok, setIndok] = useState("");

  return (
    <ModalReteg onClose={onMegse}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">Nincs számla erről a munkáról</h3>
        </div>
        <div className="space-y-3 p-5">
          <p className="text-[12.5px] text-text-secondary">
            Nem lesz kiállított számla, tehát fizetési határidő sem. A munka ettől még lehet kifizetve – a
            „Kifizetve” gomb utána is használható.
          </p>
          <label className="block text-[13px] text-text-primary">
            Miért nincs számla?
            <textarea
              autoFocus
              rows={2}
              value={indok}
              onChange={(e) => setIndok(e.target.value)}
              placeholder="Pl. beszámítva, cserébe csináltuk, a másik cégen át rendeztük…"
              className="mt-1 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] leading-relaxed text-text-primary"
            />
          </label>
        </div>
        <div className="flex justify-end gap-3 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onMegse}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Mégse
          </button>
          <button
            type="button"
            disabled={!indok.trim()}
            onClick={() => onJelol(indok.trim())}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Mentés
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
