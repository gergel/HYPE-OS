"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** Egy ember munkanapjainak állítása az adott hónapra - ez teszi igazságossá
 * a versenyt.
 *
 * Helyben szerkeszthető szám, nem felugró ablak: menet közben kell hozzányúlni
 * (valaki megbetegszik, valaki plusz napot vállal), és egy ablak minden ilyen
 * apró javításnál útban lenne. A mentés a mezőből kilépve történik, mert a
 * gépelés közbeni mentés minden leütésnél újraszámolná az egész állást.
 *
 * A pontokat NEM írja át: azok a nyers teljesítményt őrzik, az arányosítás
 * pedig mindig a friss munkanapszámmal fut le (lásd backend
 * services/vagoi_jatek.py). */
export function MunkanapSzerkeszto({
  ev,
  honap,
  employeeId,
  munkanap,
  szerkesztheto,
}: {
  ev: number;
  honap: number;
  employeeId: number;
  munkanap: number;
  szerkesztheto: boolean;
}) {
  const router = useRouter();
  const [ertek, setErtek] = useState(String(munkanap));
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState(false);

  if (!szerkesztheto) {
    return <span className="text-[13px] tabular-nums text-text-secondary">{munkanap}</span>;
  }

  async function mentes() {
    const szam = Number(ertek);
    if (ertek.trim() === "" || Number.isNaN(szam) || szam < 0 || szam > 31) {
      setHiba(true);
      setErtek(String(munkanap));
      return;
    }
    if (szam === munkanap) return;
    setBusy(true);
    setHiba(false);
    try {
      const res = await authFetch("/api/v1/vagoi-jatek/munkanap", {
        method: "PUT",
        body: JSON.stringify({ ev, honap, employee_id: employeeId, munkanap: szam }),
      });
      if (!res.ok) {
        setHiba(true);
        setErtek(String(munkanap));
        return;
      }
      router.refresh();
    } catch {
      setHiba(true);
      setErtek(String(munkanap));
    } finally {
      setBusy(false);
    }
  }

  return (
    <input
      type="number"
      min={0}
      max={31}
      value={ertek}
      onChange={(e) => setErtek(e.target.value)}
      onBlur={mentes}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      disabled={busy}
      title="Hány munkanapja volt ebben a hónapban. A pontok ehhez arányosodnak."
      className={`w-14 rounded-[var(--radius)] border bg-surface-3 px-2 py-1 text-right text-[13px] tabular-nums text-text-primary focus:outline-none disabled:opacity-50 ${
        hiba ? "border-[color:var(--text-danger)]" : "border-border"
      }`}
    />
  );
}
