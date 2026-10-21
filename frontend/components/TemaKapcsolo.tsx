"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { temaAttributum, temaSutiMentese, temaVagyAlap, type Tema } from "@/lib/tema";

/** Világos/sötét kapcsoló a fejlécben.
 *
 * A `kezdeti` érték a BEJELENTKEZETT ember mentett beállítása (a szerverről
 * jön, lásd TopBar). A süti csak a legelső festés gyorsítótára, ezért ha a
 * kettő eltér - más gép, más böngésző, vagy ugyanazon a gépen másik ember
 * lépett be -, itt a szerver nyer, és a hatás-blokk csendben javítja a DOM-ot
 * és a sütit is.
 *
 * A váltás AZONNAL látszik (nem várunk a hálózatra): a nézet átállítása helyi
 * művelet, a mentés csak utána indul. Ha a mentés elhasal, a felület nem
 * ugrik vissza - a mostani munkamenet marad úgy, ahogy kérték, csak a
 * következő belépéskor jön elő a régi beállítás. Egy témaváltás miatt
 * hibaüzenettel zavarni azt, aki csak jobban lát világosban, aránytalan
 * lenne. */
export function TemaKapcsolo({ kezdeti }: { kezdeti: string | null }) {
  const [tema, setTema] = useState<Tema>(() => temaVagyAlap(kezdeti));

  // Csak DOM-ot és sütit ír, állapotot nem - így nem "setState az effektben",
  // és minden megjelenítés egy irányba folyik: állapot -> felület.
  useEffect(() => {
    const attributum = temaAttributum(tema);
    if (attributum) document.documentElement.setAttribute("data-theme", attributum);
    else document.documentElement.removeAttribute("data-theme");
    temaSutiMentese(tema);
  }, [tema]);

  async function valtas() {
    const uj: Tema = tema === "vilagos" ? "sotet" : "vilagos";
    setTema(uj);
    try {
      await authFetch("/api/v1/auth/me/tema", { method: "PUT", body: JSON.stringify({ tema: uj }) });
    } catch {
      // Lásd a komponens leírását: a nézet marad, a mentés elmaradása nem
      // állítja vissza és nem is dob figyelmeztetést.
    }
  }

  const vilagos = tema === "vilagos";
  return (
    <button
      type="button"
      onClick={valtas}
      // A cím és az aria-label a CÉLÁLLAPOTot mondja ("mire kapcsolok"), nem a
      // jelenlegit - egy kapcsolónál ez az, ami eldönti, megnyomjam-e.
      title={vilagos ? "Váltás sötét nézetre" : "Váltás világos nézetre"}
      aria-label={vilagos ? "Váltás sötét nézetre" : "Váltás világos nézetre"}
      className="flex h-9 w-9 items-center justify-center rounded-[var(--radius)] border border-border text-text-secondary transition-colors hover:bg-surface-3 hover:text-text-primary"
    >
      {vilagos ? <Moon size={15} /> : <Sun size={15} />}
    </button>
  );
}
