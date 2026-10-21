"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SelectDropdown } from "@/components/SelectDropdown";
import { authFetch } from "@/lib/authFetch";
import { VisszajelzesModal } from "@/components/deliverable/FeedbackSendButton";

// A PONTOS szöveg, amivel a szerver elutasítja az ellenőrzésbe-tételt, ha még
// nincs vágói visszajelzés (lásd backend routes/postproduction.py
// VISSZAJELZES_HIANYZIK_UZENET, és a lista nézet ugyanezt figyelő
// UtomunkaContent.allapotAtallitasa). SIMA SZÖVEG, nem strukturált objektum:
// a `alert()` (itt: window.alert, ami ToastProvider-en át tényleges toastot
// mutat) mindenhol az app-ban stringnek várja a hiba törzsét.
const VISSZAJELZES_HIANYZIK_UZENET = "Mielőtt ellenőrzésbe teszed, írj visszajelzést ehhez az anyaghoz.";

/** Az anyag ÁLLAPOTÁNAK szerkesztője az anyag SAJÁT adatlapján - nem a
 * generikus EditableDetailGrid-en keresztül (ott az "allapot" mező a
 * HIDDEN_FIELDS listával tudatosan el van rejtve), mert ennek a mezőnek
 * EGYETLEN váltása (Ellenőrzésbe tétel) egy külön szabályhoz kötött: csak az
 * teheti oda, aki már írt hozzá vágói visszajelzést (lásd backend
 * routes/postproduction._ellenorzeshez_kell_visszajelzes). Ha ez hiányzik, a
 * sima hiba-toast helyett a felugró visszajelzés-űrlap nyílik meg - ugyanaz a
 * viselkedés, mint a lista "Állapot" oszlopánál (lásd
 * UtomunkaContent.allapotAtallitasa), csak itt EGY rekordra, nem egy
 * kliens-oldali listára vonatkoztatva. */
export function AllapotValaszto({
  deliverableId,
  allapot,
  options,
}: {
  deliverableId: number;
  allapot: string | null;
  options: string[];
}) {
  const router = useRouter();
  const [ertek, setErtek] = useState(allapot);
  const [visszajelzesKerve, setVisszajelzesKerve] = useState<string | null>(null);

  async function allapotAtallitasa(next: string | null) {
    const elozo = ertek;
    setErtek(next);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}`, {
        method: "PATCH",
        body: JSON.stringify({ allapot: next }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setErtek(elozo);
        if (detail?.detail === VISSZAJELZES_HIANYZIK_UZENET) {
          setVisszajelzesKerve(next);
          return;
        }
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      setErtek(elozo);
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    }
  }

  function visszajelzesUtan() {
    const cel = visszajelzesKerve;
    setVisszajelzesKerve(null);
    if (cel !== null) void allapotAtallitasa(cel);
  }

  return (
    <>
      <SelectDropdown value={ertek} options={options} onChange={(next) => void allapotAtallitasa(next)} placeholder="Nincs állapot" />
      {visszajelzesKerve !== null && (
        <VisszajelzesModal
          deliverableId={deliverableId}
          onClose={() => setVisszajelzesKerve(null)}
          onSaved={visszajelzesUtan}
          // Automatikusan dobtuk fel - kihagyható, de csak indoklással.
          kihagyhato
        />
      )}
    </>
  );
}
