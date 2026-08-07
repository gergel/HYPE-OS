"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Send } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

/** Keretszerződés generálása és kiküldése e-mailben.
 *
 * Akkor is használható, ha az embernek MÁR van keretszerződése - épp ez a
 * dolga: a lejárt/felmondott helyett újat lehessen küldeni. A generálás a
 * Google Docs sablonból megy, a levél az adminisztráció nevében (lásd backend
 * services/keretszerzodes_kuldes.py).
 *
 * Kiküldés előtt megerősítés kell: valódi levél megy ki a megbízottnak, ezt
 * nem lehet visszavonni. */
export function KeretszerzodesKuldes({ contractId, cegNeve }: { contractId: number; cegNeve: string | null }) {
  const router = useRouter();
  const [nyitva, setNyitva] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ujIdoszak, setUjIdoszak] = useState(true);
  const [keltezes, setKeltezes] = useState(() => new Date().toISOString().slice(0, 10));

  async function kuld() {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/contracts/${contractId}/kuldes`, {
        method: "POST",
        body: JSON.stringify({ keltezes: keltezes || null, uj_idoszak: ujIdoszak }),
      });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        alert(`A kiküldés nem sikerült: ${adat?.detail ?? res.status}`);
        return;
      }
      alert(`Kiküldve ide: ${(adat?.cimzettek ?? []).join(", ")}`);
      setNyitva(false);
      router.refresh();
    } catch (err) {
      alert(`A kiküldés nem sikerült (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!nyitva) {
    return (
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className="inline-flex items-center gap-1 text-[12.5px] text-text-accent hover:underline"
      >
        <Send size={12} aria-hidden /> Kiküldés
      </button>
    );
  }

  return (
    <span className="inline-flex flex-col items-start gap-1.5 rounded-[var(--radius)] border border-border bg-surface-3 p-2 text-left">
      <span className="text-[12px] text-text-muted">
        A(z) {cegNeve ?? "megbízott"} keretszerződése generálódik a sablonból, és e-mailben kimegy neki.
      </span>
      <label className="flex items-center gap-1.5 text-[12.5px] text-text-secondary">
        Keltezés
        <input
          type="date"
          value={keltezes}
          onChange={(e) => setKeltezes(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12.5px] text-text-primary"
        />
      </label>
      <label className="flex cursor-pointer items-center gap-1.5 text-[12.5px] text-text-secondary">
        <input
          type="checkbox"
          checked={ujIdoszak}
          onChange={(e) => setUjIdoszak(e.target.checked)}
          className="cursor-pointer"
        />
        Új érvényességi időszak indítása ettől a naptól
      </label>
      <span className="flex items-center gap-2">
        <button type="button" disabled={busy} onClick={kuld} className="btn btn-primary disabled:opacity-50">
          {busy ? "Küldés…" : "Kiküldés"}
        </button>
        <button
          type="button"
          onClick={() => setNyitva(false)}
          className="text-[12.5px] text-text-secondary hover:text-text-primary hover:underline"
        >
          Mégse
        </button>
      </span>
    </span>
  );
}
