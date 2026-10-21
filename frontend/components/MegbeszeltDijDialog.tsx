"use client";

import { useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";

/** "Mennyiért vállalja ezt a napot?" - a stábtag felvételekor felugró ablak.
 *
 * Miért itt kérdezzük? Mert itt derül ki: aki beosztja az embert a forgatásra,
 * az beszéli meg vele a díjat is. A szerződést és a TIG-et viszont hetekkel
 * később, más ember adminisztrálja, akinek pont ez az összeg kell a papírra -
 * enélkül vagy visszakeresi valaki egy üzenetváltásból, vagy tippel.
 *
 * KIHAGYHATÓ: nem minden stábtaggal beszélnek le előre fix díjat. Ilyenkor nem
 * keletkezik semmi, és a díj utólag is megadható a "Ki számláz kiért"
 * táblázatban.
 *
 * A magyarázat mező azért van, mert fél év múlva a puszta összeg nem mondja
 * meg, miért annyi (saját kamerával? két nap egyben? utazás nélkül?) - és a
 * szerződés készítője pont ezt keresi.
 *
 * A hívó FELTÉTELESEN rendereli, így minden megnyitás friss példány. */
export function MegbeszeltDijDialog({
  nev,
  napSzoveg,
  kezdoDij,
  kezdoMegjegyzes,
  onMegse,
  onKesz,
}: {
  /** Kiről van szó - a felvétel után ez az egyetlen fogódzó. */
  nev: string;
  /** Melyik nap/projekt (már formázva). Üresen elhagyjuk. */
  napSzoveg?: string | null;
  /** Meglévő érték szerkesztéskor - felvételkor üres. */
  kezdoDij?: number | null;
  kezdoMegjegyzes?: string | null;
  onMegse: () => void;
  /** `dij === null` = nincs (vagy törlődik a) lebeszélt díj. */
  onKesz: (dij: number | null, megjegyzes: string) => void;
}) {
  const [dij, setDij] = useState(kezdoDij != null ? String(kezdoDij) : "");
  const [megjegyzes, setMegjegyzes] = useState(kezdoMegjegyzes ?? "");
  const [hiba, setHiba] = useState<string | null>(null);

  function ment() {
    const tisztitott = dij.trim().replace(/\s/g, "");
    if (!tisztitott) {
      setHiba("Írd be az összeget, vagy hagyd ki a kérdést.");
      return;
    }
    const szam = Number(tisztitott);
    if (!Number.isFinite(szam) || szam < 0) {
      setHiba("Az összeg csak nem negatív szám lehet.");
      return;
    }
    onKesz(szam, megjegyzes.trim());
  }

  return (
    <ModalReteg onClose={onMegse}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-2 text-[14px] font-medium text-text-primary">Mennyiért vállalja? – {nev}</h3>
        <p className="mb-4 text-[13px] text-text-secondary">
          {napSzoveg ? `${napSzoveg}: mennyiben` : "Mennyiben"} egyeztetek meg vele erre a forgatásra? Ebből az
          összegből fog megnyílni a szerződése és a TIG-je, tehát az adminisztrációnál nem kell visszakeresni.
        </p>

        <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-text-muted">
          Nettó díj (Ft)
        </label>
        <input
          autoFocus
          inputMode="numeric"
          value={dij}
          onChange={(e) => {
            setDij(e.target.value);
            if (hiba) setHiba(null);
          }}
          placeholder="Pl. 80000"
          className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary outline-none focus:border-text-accent/40"
        />

        <label className="mb-1.5 mt-4 block text-[11px] font-medium uppercase tracking-wide text-text-muted">
          Mi van benne (nem kötelező)
        </label>
        <textarea
          rows={2}
          value={megjegyzes}
          onChange={(e) => setMegjegyzes(e.target.value)}
          placeholder="Pl. saját kamerával, utazás nélkül"
          className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary outline-none focus:border-text-accent/40"
        />
        {hiba && <p className="mt-1.5 text-[12px] text-text-danger">{hiba}</p>}

        <div className="mt-5 flex justify-end gap-3">
          {/* A kihagyás nem "Mégse": a stábtag már fent van a projekten, csak a
              díja nincs lebeszélve. Ha volt már megadva díj, ez törli. */}
          <button
            type="button"
            onClick={() => onKesz(null, "")}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            {kezdoDij != null ? "Díj törlése" : "Nincs megbeszélve"}
          </button>
          <button
            type="button"
            onClick={ment}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90"
          >
            Mentés
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
