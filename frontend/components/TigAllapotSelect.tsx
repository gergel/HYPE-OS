"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SelectDropdown } from "@/components/SelectDropdown";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";

/** A TIG állapota kézzel is átállítható - aki az adott oldalon szerkeszthet,
 * javíthatja is (pl. visszaveheti a tévesen kiküldöttre állítottat, vagy
 * kiküldöttnek jelölhet egyet, amit a rendszeren kívül küldtek el). A
 * generálás/küldés folyamat változatlan marad, ez csak az állapot javítása.
 *
 * Szerkesztési jog nélkül ugyanaz a színes címke jelenik meg, csak nem
 * legördíthető. */
export const TIG_ALLAPOTOK = ["Készítés alatt", "Kiküldve", "Kihagyva"];

const TONES: Record<string, "success" | "warning" | "neutral"> = {
  Kiküldve: "success",
  // A "Kész" a Belsős TIG korábbi, email-küldés nélküli életciklusából
  // maradt állapot - a régi bejegyzések így vannak eltárolva.
  Kész: "success",
  "Készítés alatt": "warning",
  Kihagyva: "neutral",
};

export function TigAllapotSelect({
  postPath,
  value,
  canEdit,
  placeholder = "Nincs elkezdve",
}: {
  /** A backend végpont, ami az állapotot állítja (POST {allapot}). */
  postPath: string;
  value: string | null;
  canEdit: boolean;
  placeholder?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  if (!canEdit) {
    return <StatusBadge label={value ?? placeholder} tone={value ? (TONES[value] ?? "neutral") : "neutral"} />;
  }

  async function onChange(next: string | null) {
    if (!next) return;
    setBusy(true);
    try {
      const res = await authFetch(postPath, { method: "POST", body: JSON.stringify({ allapot: next }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span onClick={(e) => e.stopPropagation()}>
      <SelectDropdown
        value={value}
        options={TIG_ALLAPOTOK}
        onChange={onChange}
        placeholder={placeholder}
        disabled={busy}
      />
    </span>
  );
}
