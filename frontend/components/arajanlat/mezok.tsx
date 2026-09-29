"use client";

import { useState } from "react";
import { szamBe, szamSzoveg } from "./quote";

/** Szövegmező, ami csak elhagyáskor (vagy Enterre) ment - a katalógus és a
 * sablonok szerkesztésénél minden mentés ártörténetet / sablont ír, ezért
 * nem billentyűnként. */
export function MentoMezo({
  ertek,
  onMent,
  tiltva,
  className = "field",
  placeholder,
  tobbsoros,
}: {
  ertek: string | null;
  onMent: (v: string) => void;
  tiltva?: boolean;
  className?: string;
  placeholder?: string;
  tobbsoros?: boolean;
}) {
  const [v, setV] = useState(ertek ?? "");
  // Ha kívülről (mentés után) változik az érték, a mező azt mutassa.
  const [elozo, setElozo] = useState(ertek);
  if (ertek !== elozo) {
    setElozo(ertek);
    setV(ertek ?? "");
  }
  const ment = () => {
    if (v !== (ertek ?? "")) onMent(v);
  };
  if (tobbsoros) {
    return (
      <textarea
        className={className}
        value={v}
        disabled={tiltva}
        placeholder={placeholder}
        rows={Math.max(1, Math.min(6, v.split("\n").length))}
        onChange={(e) => setV(e.target.value)}
        onBlur={ment}
      />
    );
  }
  return (
    <input
      className={className}
      value={v}
      disabled={tiltva}
      placeholder={placeholder}
      onChange={(e) => setV(e.target.value)}
      onBlur={ment}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}

/** Számmező, ami elhagyáskor ment; üresen hagyva `null` (ha megengedett). */
export function MentoSzam({
  ertek,
  onMent,
  tiltva,
  className = "field text-right tabular-nums",
  placeholder,
  urese = false,
  penz = false,
}: {
  ertek: number | null;
  onMent: (v: number | null) => void;
  tiltva?: boolean;
  className?: string;
  placeholder?: string;
  urese?: boolean;
  penz?: boolean;
}) {
  const kiir = (x: number | null) => (x === null ? "" : penz ? Math.round(x).toLocaleString("hu-HU") : szamSzoveg(x));
  const [v, setV] = useState(kiir(ertek));
  const [elozo, setElozo] = useState(ertek);
  if (ertek !== elozo) {
    setElozo(ertek);
    setV(kiir(ertek));
  }
  return (
    <input
      className={className}
      inputMode="decimal"
      value={v}
      disabled={tiltva}
      placeholder={placeholder}
      onFocus={(e) => {
        setV(ertek === null ? "" : penz ? String(Math.round(ertek)) : szamSzoveg(ertek));
        requestAnimationFrame(() => e.target.select());
      }}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => {
        const n = szamBe(v);
        if (n === null && !urese) {
          setV(kiir(ertek));
          return;
        }
        if (n !== null && n < 0) {
          setV(kiir(ertek));
          return;
        }
        if (n !== ertek) onMent(n === null ? null : penz ? Math.round(n) : n);
        else setV(kiir(ertek));
      }}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}
