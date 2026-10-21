"use client";

import { useState } from "react";
import { FileText } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

/** A diszpó PDF megnyitása a SAJÁT tárhelyről (R2), nagyban - új lapon (a
 * felhasználó kérése: ne a Drive-ról nyíljon). A cím a backendtől jön
 * (routes/dashboard.sajat_diszpo_pdf_url) - a régi, csak Drive-os diszpót
 * az első megnyitás költözteti át R2-re. Az új lapot SZINKRON nyitjuk (a
 * felugró-blokkolók miatt), és a kérés után irányítjuk a PDF-re. */
export function DiszpoPdfGomb({
  projectId,
  cimke = "Diszpó PDF megnyitása",
  className,
}: {
  projectId: number;
  cimke?: string;
  className: string;
}) {
  const [busy, setBusy] = useState(false);

  async function nyit() {
    if (busy) return;
    const ablak = window.open("", "_blank");
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/dashboard/sajat-diszpok/${projectId}/pdf-url`);
      const adat = await res.json().catch(() => null);
      if (!res.ok || !adat?.url) {
        ablak?.close();
        alert(adat?.detail ?? "A diszpó PDF nem érhető el.");
        return;
      }
      if (ablak) ablak.location.href = adat.url;
      else window.open(adat.url, "_blank");
    } catch {
      ablak?.close();
      alert("Hálózati hiba - próbáld újra.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button type="button" onClick={() => void nyit()} disabled={busy} className={className}>
      <FileText size={16} />
      {busy ? "Megnyitás…" : cimke}
    </button>
  );
}
