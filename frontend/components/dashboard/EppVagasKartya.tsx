"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Scissors } from "lucide-react";
import { Card } from "@/components/Card";
import { authFetch } from "@/lib/authFetch";

type FutoTimer = {
  deliverable_id: number;
  employee_id: number;
  full_name: string;
  projekt_neve: string | null;
  kezdet: string | null;
};

/** Milyen sűrűn frissüljön - ugyanaz a ritmus, mint az Utómunka tábla
 * "ki vág éppen" jelzésénél (lásd UtomunkaContent). */
const FRISSITES_MS = 60_000;

function eltelt(kezdet: string | null): string {
  if (!kezdet) return "";
  const percek = Math.max(0, Math.floor((Date.now() - new Date(kezdet).getTime()) / 60000));
  if (percek < 60) return `${percek} perce`;
  const orak = Math.floor(percek / 60);
  return `${orak} ó ${percek % 60} p óta`;
}

/** ÉPP VÁGÁS ALATT - admin dashboard-kártya (a felhasználó kérése): a futó
 * időmérők alapján mutatja, melyik anyagot ki vágja éppen és mióta. Csak
 * akkor jelenik meg, ha tényleg fut mérés - üresen nem foglal helyet. */
export function EppVagasKartya() {
  const [timerek, setTimerek] = useState<FutoTimer[]>([]);

  useEffect(() => {
    let aktiv = true;
    const betolt = () =>
      authFetch("/api/v1/deliverables/futo-timerek")
        .then((res) => (res.ok ? res.json() : null))
        .then((adat: FutoTimer[] | null) => {
          if (aktiv && adat) setTimerek(adat);
        })
        .catch(() => {});
    void betolt();
    const idozito = setInterval(betolt, FRISSITES_MS);
    return () => {
      aktiv = false;
      clearInterval(idozito);
    };
  }, []);

  if (timerek.length === 0) return null;

  // Anyagonként csoportosítva: egy anyagon több vágó mérője is futhat.
  const anyagok = new Map<number, { nev: string; vagok: FutoTimer[] }>();
  for (const t of timerek) {
    if (!anyagok.has(t.deliverable_id)) {
      anyagok.set(t.deliverable_id, { nev: t.projekt_neve ?? `Anyag #${t.deliverable_id}`, vagok: [] });
    }
    anyagok.get(t.deliverable_id)!.vagok.push(t);
  }

  return (
    <Card title={`Épp vágás alatt (${anyagok.size})`} icon={Scissors}>
      <div className="space-y-2.5">
        {Array.from(anyagok.entries()).map(([id, a]) => (
          <div key={id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <Link href={`/utomunka/${id}`} className="min-w-0 text-[13.5px] text-text-accent hover:underline">
              <span className="[overflow-wrap:anywhere]">{a.nev}</span>
            </Link>
            <span className="flex items-center gap-1.5 text-[13px] text-text-secondary">
              {/* Pulzáló pötty - ugyanaz az élő jelzés, mint az Utómunka
                  tábla kártyáin. */}
              <span aria-hidden className="relative flex h-2 w-2 shrink-0 text-text-success">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-current" />
              </span>
              {a.vagok.map((v) => `${v.full_name}${eltelt(v.kezdet) ? ` (${eltelt(v.kezdet)})` : ""}`).join(", ")}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
