"use client";

import { useState, type ReactNode } from "react";
import { UtokovetesTabla } from "@/components/UtokovetesTabla";
import type { UtokovetesOverview } from "@/lib/api";

const NEZETEK = [
  { kulcs: "attekintes", cimke: "Áttekintés" },
  { kulcs: "admin", cimke: "Admin lista" },
] as const;

type Nezet = (typeof NEZETEK)[number]["kulcs"];

/** A két utókövetés-nézet közti váltás - KISZOLGÁLÓ NÉLKÜL.
 *
 * A váltás korábban sima linkelés volt (?nezet=admin), ami minden kattintásra
 * új szerver-renderelést és új adatlekérést indított: a lista végigszámolja az
 * összes diszpózott projekt szerződés/TIG/kifizetés állapotát, ezért a váltás
 * érezhetően lassú volt. Most mindkét nézet EGY lekérésből készül - az admin
 * táblázat szerver-komponensként érkezik ide gyerekként -, és a váltás csak
 * annyi, hogy melyiket mutatjuk.
 *
 * A címsor azért továbbra is követi a nézetet (replaceState, tehát navigáció
 * nélkül), hogy a link megosztható és frissítés után is ugyanaz maradjon. */
export function UtokovetesNezetek({
  rows,
  lista,
  kezdeti = "attekintes",
}: {
  rows: UtokovetesOverview[];
  lista: ReactNode;
  kezdeti?: Nezet;
}) {
  const [nezet, setNezet] = useState<Nezet>(kezdeti);

  function valt(uj: Nezet) {
    setNezet(uj);
    if (typeof window !== "undefined") {
      const url = uj === "admin" ? "/utokovetes?nezet=admin" : "/utokovetes";
      window.history.replaceState(null, "", url);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <div className="flex items-center gap-1 rounded-[var(--radius)] border border-border p-0.5">
          {NEZETEK.map((n) => (
            <button
              key={n.kulcs}
              type="button"
              onClick={() => valt(n.kulcs)}
              className={`rounded-[var(--radius)] px-2.5 py-1 text-[12.5px] transition-colors ${
                nezet === n.kulcs ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {n.cimke}
            </button>
          ))}
        </div>
      </div>
      {/* Mindkét nézet ugyanabból az adatból: a nem látszó ág egyszerűen nincs
          kirajzolva, de nem is kell hozzá új lekérés. */}
      {nezet === "admin" ? lista : <UtokovetesTabla rows={rows} />}
    </div>
  );
}
