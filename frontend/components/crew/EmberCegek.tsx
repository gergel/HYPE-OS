"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import { huDatum } from "@/lib/huDate";
import type { EmberCeg } from "@/lib/api";

/** A munkatárs cégei, időszakkal.
 *
 * Egy emberhez több cég is tartozhat, és időben válthat köztük ("2026 májusáig
 * a régi Kft.-ről, azóta az új Bt.-ről számláz"). Az időszak nem formaság: a
 * havi belsős TIG ebből tudja, melyik céget ajánlja fel az adott hónapra (lásd
 * backend routes/internal_performance_certificates.py _ceg_valasztek).
 *
 * A cégek TÖRZSADATÁT (székhely, adószám) továbbra is a Pénzügyek > Számlázó
 * cégek oldalon lehet szerkeszteni - itt csak az tartozik ide, hogy melyik cég
 * mikor az övé. */
export function EmberCegek({
  employeeId,
  cegek,
  valaszthato,
  canEdit,
}: {
  employeeId: number;
  cegek: EmberCeg[];
  /** Minden aktív cég, amiből választani lehet. */
  valaszthato: { id: number; nev: string }[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const [ujCeg, setUjCeg] = useState("");
  const [ujKezdet, setUjKezdet] = useState("");
  const [ujVeg, setUjVeg] = useState("");

  async function hivas(url: string, init: RequestInit, hibaSzoveg: string) {
    setBusy(true);
    try {
      const res = await authFetch(url, init);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`${hibaSzoveg}: ${detail?.detail ?? res.status}`);
        return false;
      }
      router.refresh();
      return true;
    } catch (err) {
      alert(`${hibaSzoveg} (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function felvesz() {
    if (!ujCeg) return;
    const sikeres = await hivas(
      `/api/v1/vallalkozasok/ember/${employeeId}`,
      {
        method: "POST",
        body: JSON.stringify({
          vallalkozas_id: Number(ujCeg),
          kezdet: ujKezdet || null,
          veg: ujVeg || null,
        }),
      },
      "Sikertelen felvétel",
    );
    if (sikeres) {
      setUjCeg("");
      setUjKezdet("");
      setUjVeg("");
    }
  }

  async function idoszak(tagsagId: number, mezo: "kezdet" | "veg", ertek: string, sor: EmberCeg) {
    await hivas(
      `/api/v1/vallalkozasok/tagsagok/${tagsagId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          kezdet: mezo === "kezdet" ? ertek || null : sor.kezdet,
          veg: mezo === "veg" ? ertek || null : sor.veg,
          megjegyzes: sor.megjegyzes,
        }),
      },
      "Sikertelen mentés",
    );
  }

  async function torol(sor: EmberCeg) {
    if (!(await confirm(`Leveszed a(z) „${sor.nev}” céget erről a munkatársról?`))) return;
    await hivas(`/api/v1/vallalkozasok/tagsagok/${sor.id}`, { method: "DELETE" }, "Sikertelen törlés");
  }

  const mar_felvett = new Set(cegek.map((c) => c.vallalkozas_id));
  const felvehetok = valaszthato.filter((c) => !mar_felvett.has(c.id));

  return (
    <div>
      <p className="mb-3 text-[12.5px] text-text-muted">
        Melyik cégekről számláz ez a munkatárs, és mikortól meddig. A havi TIG készítésekor ezek közül lehet
        választani – az időszakhoz illő cég az alapértelmezett.
      </p>

      {cegek.length === 0 ? (
        <p className="mb-3 text-[13px] text-text-secondary">Nincs cég felvezetve – a papírok a saját nevére szólnak.</p>
      ) : (
        <table className="mb-3 w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Cég</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Mettől</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Meddig</th>
              <th className="py-1.5" />
            </tr>
          </thead>
          <tbody>
            {cegek.map((sor) => (
              <tr key={sor.id} className="border-b border-border last:border-0">
                <td className="py-2 pr-4 text-text-primary">
                  {sor.nev}
                  {!sor.aktiv && <span className="ml-1.5 text-[11px] text-text-muted">(inaktív)</span>}
                </td>
                {(["kezdet", "veg"] as const).map((mezo) => (
                  <td key={mezo} className="py-2 pr-4">
                    {canEdit ? (
                      <input
                        type="date"
                        defaultValue={sor[mezo] ?? ""}
                        disabled={busy}
                        onChange={(e) => idoszak(sor.id, mezo, e.target.value, sor)}
                        className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none disabled:opacity-50"
                      />
                    ) : (
                      <span className="text-text-secondary">{sor[mezo] ? huDatum(sor[mezo]!) : "–"}</span>
                    )}
                  </td>
                ))}
                <td className="py-2 text-right">
                  {canEdit && (
                    <button
                      type="button"
                      onClick={() => torol(sor)}
                      disabled={busy}
                      title="Cég levétele"
                      className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {canEdit && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Cég</label>
            <select
              value={ujCeg}
              onChange={(e) => setUjCeg(e.target.value)}
              disabled={busy || felvehetok.length === 0}
              className="min-w-[200px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none disabled:opacity-50"
            >
              <option value="">{felvehetok.length === 0 ? "Nincs több cég" : "Válassz céget…"}</option>
              {felvehetok.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nev}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Mettől</label>
            <input
              type="date"
              value={ujKezdet}
              onChange={(e) => setUjKezdet(e.target.value)}
              disabled={busy}
              className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none disabled:opacity-50"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Meddig</label>
            <input
              type="date"
              value={ujVeg}
              onChange={(e) => setUjVeg(e.target.value)}
              disabled={busy}
              className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none disabled:opacity-50"
            />
          </div>
          <button
            type="button"
            onClick={felvesz}
            disabled={busy || !ujCeg}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Mentés…" : "Cég hozzáadása"}
          </button>
        </div>
      )}
    </div>
  );
}
