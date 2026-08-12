"use client";

import { ModalReteg } from "@/components/ModalReteg";

export type EllenorzoSor = { cimke: string; ertek: string | null };

/** Kiküldés előtti áttekintő: PONTOSAN milyen adatokkal megy ki a papír.
 *
 * A szerződés és a TIG generálása egy Google Docs sablon kitöltése, majd
 * azonnali e-mail (lásd backend gdoc_template.py + google_email.py) - ha
 * elgépelt adószámmal vagy hiányzó székhellyel megy ki, az már a megbízottnál
 * van, és csak új papírral javítható. Ez az ablak azért van, hogy a küldés
 * előtt egyszer, egy helyen látszódjon minden, ami a dokumentumra kerül.
 *
 * A HIÁNYZÓ mezők kiemelve jelennek meg: az üres hely a papíron a
 * leggyakoribb és a legkésőbb észrevett hiba. A küldés attól még engedélyezett -
 * van, amit tényleg nem kell kitölteni -, de tudatos döntés legyen.
 *
 * A hívó feltételesen rendereli, így minden megnyitás friss példány. */
export function KuldesEllenorzo({
  cim,
  cimzett,
  bevezeto,
  sorok,
  tetelek = [],
  gombCimke,
  onMegse,
  onKuld,
  children,
}: {
  cim: string;
  /** Kinek megy az e-mail. Üresen a küldés hibára fut, ezért ez is kiemelt. */
  cimzett: string | null;
  bevezeto: string;
  sorok: EllenorzoSor[];
  /** Kinek a munkáját fedi a papír - ha több emberről/projektről szól. */
  tetelek?: string[];
  gombCimke: string;
  onMegse: () => void;
  onKuld: () => void;
  /** Amit még a küldés előtt meg kell adni (pl. a kísérőlevél szövege).
   * Az adatok ALATT jelenik meg: előbb az ellenőrzés, aztán a szerkesztés. */
  children?: React.ReactNode;
}) {
  const hianyzok = sorok.filter((s) => !(s.ertek ?? "").trim()).map((s) => s.cimke);

  return (
    <ModalReteg onClose={onMegse}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-2xl rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">{cim}</h3>
          <p className="mt-0.5 text-[12.5px] text-text-secondary">{bevezeto}</p>
        </div>

        <div className="max-h-[65vh] overflow-y-auto p-5">
          <div className="mb-4 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
            <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">Címzett</p>
            {cimzett?.trim() ? (
              <p className="text-[13px] text-text-primary">{cimzett}</p>
            ) : (
              <p className="text-[13px] text-text-danger">
                Nincs e-mail cím – a küldés így hibára fut. Vedd fel a címet a megbízott adatlapján.
              </p>
            )}
          </div>

          <table className="w-full border-collapse text-[13px]">
            <tbody>
              {sorok.map((s) => {
                const ures = !(s.ertek ?? "").trim();
                return (
                  <tr key={s.cimke} className="border-b border-border last:border-0">
                    <td className="w-[40%] py-2 pr-4 align-top text-[12px] text-text-muted">{s.cimke}</td>
                    <td className={`py-2 align-top ${ures ? "text-text-danger" : "text-text-primary"}`}>
                      {ures ? "hiányzik – üresen megy ki a papírra" : s.ertek}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {tetelek.length > 0 && (
            <div className="mt-4">
              <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                Kinek a munkájáról szól
              </p>
              <ul className="list-inside list-disc space-y-0.5 text-[12.5px] text-text-secondary">
                {tetelek.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          )}

          {children}

          {hianyzok.length > 0 && (
            <p className="mt-4 text-[12.5px] text-text-danger">
              {hianyzok.length} mező üres ({hianyzok.join(", ")}). Ezek a helyek üresen maradnak a kiküldött
              dokumentumon.
            </p>
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
            onClick={onKuld}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90"
          >
            {gombCimke}
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
