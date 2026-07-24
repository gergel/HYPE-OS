"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";

type Cert = {
  id: number;
  employee_id: number;
  allapot: string | null;
  brutto_osszeg: number | null;
  szamla_url: string | null;
  szamla_kifizetve: boolean;
};

/** A "Kiküldve"/"Kész" állapotú TIG-ekhez (akár Külsős, akár Belsős) tartozó
 * számla feltöltése, majd kifizetettként jelölése - ez utóbbi hozza létre a
 * Pénzügy -> Kiadások-ban megjelenő Expense sort (lásd backend
 * performance_certificates.py / internal_performance_certificates.py
 * /szamla és /szamla-kifizetve végpontjai). Ugyanaz a komponens szolgálja ki
 * mindkét TIG-fajtát, csak a basePath és a readyStatus különbözik köztük. */
export function TigInvoiceManager({
  projectId,
  basePath,
  certificates,
  employeeNameById,
  readyStatus,
}: {
  projectId: number;
  basePath: string;
  certificates: Cert[];
  employeeNameById: Map<number, string>;
  readyStatus: string;
}) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const ready = certificates.filter((c) => c.allapot === readyStatus);

  async function uploadInvoice(employeeId: number, file: File) {
    setBusyId(employeeId);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch(`${basePath}/${projectId}/${employeeId}/szamla`, { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen feltöltés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function markPaid(employeeId: number) {
    if (!confirm("Kifizetettként jelölöd a számlát? Ez létrehoz (vagy frissít) egy Kiadás sort a Pénzügyben.")) return;
    setBusyId(employeeId);
    try {
      const res = await authFetch(`${basePath}/${projectId}/${employeeId}/szamla-kifizetve`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  if (ready.length === 0) return null;

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="mb-2 text-[13px] font-medium text-text-primary">Számlák</p>
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-border">
            <th className="py-1.5 text-left font-medium text-text-secondary">Megbízott</th>
            <th className="py-1.5 text-right font-medium text-text-secondary">Bruttó</th>
            <th className="py-1.5 text-left font-medium text-text-secondary">Számla</th>
            <th className="py-1.5 text-right font-medium text-text-secondary">Státusz</th>
          </tr>
        </thead>
        <tbody>
          {ready.map((c) => (
            <tr key={c.id} className="border-b border-border last:border-0">
              <td className="py-2 pr-4">{employeeNameById.get(c.employee_id) ?? `#${c.employee_id}`}</td>
              <td className="py-2 text-right">{c.brutto_osszeg != null ? `${c.brutto_osszeg.toLocaleString("hu-HU")} Ft` : "–"}</td>
              <td className="py-2 pr-4">
                {c.szamla_url ? (
                  <a href={c.szamla_url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                    Megnyitás
                  </a>
                ) : (
                  <input
                    ref={inputRef}
                    type="file"
                    disabled={busyId === c.employee_id}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) uploadInvoice(c.employee_id, file);
                    }}
                    className="max-w-[160px] text-[12px]"
                  />
                )}
              </td>
              <td className="py-2 text-right">
                {c.szamla_kifizetve ? (
                  <StatusBadge label="Kifizetve" tone="success" />
                ) : c.szamla_url ? (
                  <button
                    type="button"
                    disabled={busyId === c.employee_id}
                    onClick={() => markPaid(c.employee_id)}
                    className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                  >
                    Kifizetve jelölés
                  </button>
                ) : (
                  <StatusBadge label="Nincs számla" tone="neutral" />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
