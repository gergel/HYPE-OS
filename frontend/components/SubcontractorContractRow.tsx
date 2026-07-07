"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { PendingSubcontractorEmployee } from "@/lib/api";

/** Egy projekten résztvevő, még nem kezelt (sem belsős, sem keretszerződéses)
 * ember sora az "Alvállalkozók szerződése" nézetben - a nettó összeget és a
 * teljesítési időszakot itt kell megadni (ezek projektenként/emberenként
 * eltérőek, nincsenek előre eltárolva), a többi mező (cégnév, székhely,
 * adószám, képviselő) az Employee saját adataiból jön, előtöltve. */
export function SubcontractorContractRow({
  projectId,
  employee,
}: {
  projectId: number;
  employee: PendingSubcontractorEmployee;
}) {
  const router = useRouter();
  const [nettoOsszeg, setNettoOsszeg] = useState("");
  const [teljesitesKezdete, setTeljesitesKezdete] = useState("");
  const [teljesitesVege, setTeljesitesVege] = useState("");
  const [targy, setTargy] = useState(employee.megbizas_targya ?? "");
  const [pluszAfa, setPluszAfa] = useState(employee.plusz_afa ?? "");
  const [busy, setBusy] = useState<"send" | "skip" | null>(null);

  async function handleGenerateAndSend() {
    const netto = Number(nettoOsszeg);
    if (!nettoOsszeg.trim() || Number.isNaN(netto) || netto <= 0) {
      alert("Add meg a nettó összeget.");
      return;
    }
    if (!confirm(`Elküldi a megbízási szerződést ${employee.full_name} email címére?`)) return;
    setBusy("send");
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${employee.id}/generate-and-send`, {
        method: "POST",
        body: JSON.stringify({
          netto_osszeg: netto,
          teljesites_kezdete: teljesitesKezdete || null,
          teljesites_vege: teljesitesVege || null,
          targy: targy || null,
          plusz_afa: pluszAfa || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen küldés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen küldés (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  async function handleSkip() {
    if (!confirm(`Biztosan kihagyod ${employee.full_name}-t? A projekt szerződés nélkül zárul vele.`)) return;
    setBusy("skip");
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${employee.id}/skip`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen kihagyás: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen kihagyás (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  const busyState = busy !== null;

  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-2 p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[14px] font-medium text-text-primary">{employee.full_name}</p>
        <p className="text-[12px] text-text-muted">{employee.email ?? "nincs email"}</p>
      </div>
      <p className="mb-3 text-[12px] text-text-muted">
        {employee.ceg_neve ?? "–"} · {employee.szekhely ?? "–"} · adószám: {employee.adoszam ?? "–"}
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-text-muted">Nettó összeg (Ft) *</label>
          <input
            type="number"
            value={nettoOsszeg}
            onChange={(e) => setNettoOsszeg(e.target.value)}
            disabled={busyState}
            className="w-32 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-text-muted">Teljesítés kezdete</label>
          <input
            type="date"
            value={teljesitesKezdete}
            onChange={(e) => setTeljesitesKezdete(e.target.value)}
            disabled={busyState}
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-text-muted">Teljesítés vége</label>
          <input
            type="date"
            value={teljesitesVege}
            onChange={(e) => setTeljesitesVege(e.target.value)}
            disabled={busyState}
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-text-muted">Megbízás tárgya</label>
          <input
            type="text"
            value={targy}
            onChange={(e) => setTargy(e.target.value)}
            disabled={busyState}
            className="w-40 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-text-muted">Plusz ÁFA</label>
          <input
            type="text"
            value={pluszAfa}
            onChange={(e) => setPluszAfa(e.target.value)}
            disabled={busyState}
            className="w-24 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={handleGenerateAndSend}
          disabled={busyState}
          className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
        >
          {busy === "send" ? "Küldés…" : "Generálás és küldés"}
        </button>
        <button
          type="button"
          onClick={handleSkip}
          disabled={busyState}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {busy === "skip" ? "Kihagyás…" : "Kihagyás (szerződés nélkül)"}
        </button>
      </div>
    </div>
  );
}
