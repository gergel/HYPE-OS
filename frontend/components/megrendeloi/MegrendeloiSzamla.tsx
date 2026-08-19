"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ModalReteg } from "@/components/ModalReteg";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
// A pénzformázó a FÜGGŐSÉG NÉLKÜLI modulból jön: a lib/api.ts a
// "next/headers"-t is behúzza (szerver-oldali süti-olvasás), és egy kliens
// komponensben már egyetlen nem type-only importja is build hibát okoz.
import { formatHuf } from "@/lib/penz";
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
 *   fizetési határidő -> "Kifizetve" (a kifizetés napjával) -> bevétel-sor
 *
 * A HATÁRIDŐ azért kötelező a kifizetés előtt, mert az az egyetlen dolog,
 * amiből látszik, hogy egy még ki nem fizetett számla KÉSIK-e. A BEVÉTEL-SOR
 * pedig azért keletkezik magától, mert eddig a projektkódon ki volt pipálva a
 * kifizetés, a Pénzügyekbe viszont valakinek kézzel kellett felvezetnie - és
 * ha elmaradt, a projekt profitja hazudott. */
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
  const [hatarido, setHatarido] = useState(allas.fizetesi_hatarido ?? "");
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
      <div className="flex flex-wrap items-center gap-2">
        {allas.kifizetve ? (
          <StatusBadge label="Kifizetve" tone="success" />
        ) : allas.szamla_kihagyva ? (
          <StatusBadge label="Nincs számla" tone="neutral" />
        ) : allas.fizetesi_hatarido ? (
          <StatusBadge label="Fizetésre vár" tone="warning" />
        ) : (
          <StatusBadge label="Nincs fizetési határidő" tone="neutral" />
        )}
        {/* A NETTÓ áll elöl: az elszámolásban (bevétel, profit) mindenütt az
            a mérvadó - lásd backend services/elszamolas.py. A bruttót
            mellétesszük, ha eltér: annyi érkezik a bankszámlára. */}
        {allas.netto !== null && (
          <span className="text-[12.5px] text-text-secondary">
            {formatHuf(allas.netto)} nettó
            {allas.brutto !== null && allas.brutto !== allas.netto && (
              <span className="text-text-muted"> ({formatHuf(allas.brutto)} bruttó)</span>
            )}
          </span>
        )}
      </div>

      {/* A Notionból örökölt számla akkor is elérhető legyen, ha nem
          csatolmányként jött át (a régi kódoknál csak egy cím van meg). */}
      {allas.szamla_url && (
        <a
          href={allas.szamla_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-[12.5px] text-text-accent hover:underline"
        >
          Számla megnyitása
        </a>
      )}

      {/* A számlán szereplő fizetési határidő. A kifizetés jelöléséhez kell -
          enélkül nem tudjuk, mikortól késik. Ahol nincs is számla, ott
          értelmetlen, ezért el is tűnik. */}
      {allas.hatarido_kell && (
      <label className="block text-[13px] text-text-secondary">
        Fizetési határidő (a számlán)
        <input
          type="date"
          value={hatarido}
          disabled={!canEdit || busy}
          onChange={(e) => setHatarido(e.target.value)}
          onBlur={async () => {
            const ertek = hatarido || null;
            if (ertek === (allas.fizetesi_hatarido ?? null)) return;
            const sikeres = await hivas("hatarido", { fizetesi_hatarido: ertek });
            if (!sikeres) setHatarido(allas.fizetesi_hatarido ?? "");
          }}
          className="mt-1 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary disabled:opacity-60"
        />
      </label>
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
          <p className="text-[13px] text-text-secondary">
            Kifizetve: <span className="text-text-primary">{allas.kifizetes_datuma ?? "–"}</span>
            {allas.bevetelbe_ne_keruljon ? (
              <span className="text-text-muted"> · a bevétel-sor nem számít az éves bevételbe</span>
            ) : (
              <span className="text-text-muted"> · {allas.bevetel_sorok} bevétel-sor a Pénzügyekben</span>
            )}
          </p>
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
            disabled={busy || (allas.hatarido_kell && !allas.fizetesi_hatarido)}
            onClick={() => setDialogNyitva(true)}
            title={
              !allas.hatarido_kell || allas.fizetesi_hatarido
                ? undefined
                : "Előbb add meg a fizetési határidőt, vagy jelöld, hogy nincs számla."
            }
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Kifizetve
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
          osszeg={
            allas.netto === null
              ? null
              : `${formatHuf(allas.netto)} nettó` +
                (allas.brutto !== null && allas.brutto !== allas.netto ? ` (${formatHuf(allas.brutto)} bruttó)` : "")
          }
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
  osszeg,
  onMegse,
  onJelol,
}: {
  hatarido: string | null;
  osszeg: string | null;
  onMegse: () => void;
  onJelol: (adat: {
    kifizetes_datuma: string;
    bevetelbe_ne_keruljon: boolean;
    kihagyas_oka: string | null;
  }) => void;
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

  return (
    <ModalReteg onClose={onMegse}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">Megrendelői számla kifizetve</h3>
          {osszeg && <p className="mt-0.5 text-[12.5px] text-text-secondary">{osszeg}</p>}
        </div>

        <div className="p-5">
          <label className="block text-[13px] text-text-primary">
            Mikor érkezett meg a pénz *
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
              Kötelező – ez a nap kerül a bevétel-sorra is.{hatarido && ` Fizetési határidő: ${hatarido}.`}
            </span>
          </label>

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
                A projektkód „kifizetve” lesz, de <b>nem keletkezik bevétel-sor</b> – akkor válaszd ezt, ha a pénz
                máshol van elszámolva, és itt csak duplázná az összeget.
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
            disabled={!datum || (!bevetelbeKerul && !indok.trim())}
            onClick={() =>
              onJelol({
                kifizetes_datuma: datum,
                bevetelbe_ne_keruljon: !bevetelbeKerul,
                kihagyas_oka: bevetelbeKerul ? null : indok.trim(),
              })
            }
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Kifizetve jelölés
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
