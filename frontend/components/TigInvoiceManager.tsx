"use client";

import { Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { TigAllapotSelect } from "@/components/TigAllapotSelect";
import type { PerformanceCertificate } from "@/lib/api";

/** A "Kiküldve"/"Kész" állapotú TIG-ekhez (akár Külsős, akár Belsős) tartozó
 * számlák feltöltése, majd kifizetettként jelölése - ez utóbbi hozza létre a
 * Pénzügy -> Kiadások-ban megjelenő Expense sort (lásd backend
 * performance_certificates.py / internal_performance_certificates.py
 * /szamla és /szamla-kifizetve végpontjai). Ugyanaz a komponens szolgálja ki
 * mindkét TIG-fajtát, csak a basePath és a readyStatus különbözik köztük.
 *
 * Egy TIG-hez több számla is tartozhat (pl. részszámlák), és bármelyik
 * külön-külön törölhető - a törlés a kifizetettséget NEM vonja vissza, mert az
 * már pénzügyi tény (lásd backend delete_szamla).
 *
 * Maga a TIG is törölhető innen (amíg nincs kifizetve): ha rossz adattal ment
 * ki, vagy tévesen lett kihagyva, a törlés után az illető visszakerül a
 * teendők közé, és készíthető neki új TIG. Ezért jelennek meg itt a KIHAGYOTT
 * bejegyzések is - különben egy téves kihagyás sehol nem lenne javítható. */
export function TigInvoiceManager({
  projectId,
  basePath,
  certificates,
  employeeNameById,
  readyStatus,
  canEdit = true,
}: {
  projectId: number;
  basePath: string;
  certificates: PerformanceCertificate[];
  employeeNameById: Map<number, string>;
  readyStatus: string;
  /** Az állapot legördülője csak szerkesztési joggal aktív - enélkül sima
   * címkeként jelenik meg (lásd TigAllapotSelect). */
  canEdit?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busyId, setBusyId] = useState<number | null>(null);

  const ready = certificates.filter((c) => c.allapot === readyStatus || c.allapot === "Kihagyva");

  /** Egyszerre több kiválasztott fájl is feltölthető - egymás után megy fel,
   * mert minden hívás egy külön számla-sort hoz létre a backenden. */
  async function uploadInvoices(employeeId: number, input: HTMLInputElement, files: File[]) {
    setBusyId(employeeId);
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        const res = await authFetch(`${basePath}/${projectId}/${employeeId}/szamla`, { method: "POST", body: fd });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          alert(`Sikertelen feltöltés (${file.name}): ${detail?.detail ?? res.status}`);
          break;
        }
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
      input.value = "";
    }
  }

  async function deleteInvoice(employeeId: number, invoiceId: number, filename: string) {
    if (!(await confirm(`Biztosan törlöd ezt a számlát: "${filename}"?`))) return;
    setBusyId(employeeId);
    try {
      const res = await authFetch(`${basePath}/${projectId}/${employeeId}/szamla/${invoiceId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function deleteCertificate(employeeId: number, nev: string) {
    const ok = await confirm(
      `Törlöd ${nev} teljesítési igazolását erről a projektről? Ezután újra a teendők közt jelenik meg, és készíthetsz neki újat.`,
    );
    if (!ok) return;
    setBusyId(employeeId);
    try {
      const res = await authFetch(`${basePath}/${projectId}/${employeeId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function markPaid(employeeId: number) {
    if (!(await confirm("Kifizetettként jelölöd a számlát? Ez létrehoz (vagy frissít) egy Kiadás sort a Pénzügyben."))) return;
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
      <p className="mb-2 text-[13px] font-medium text-text-primary">Elkészült TIG-ek és számlák</p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Megbízott</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">TIG állapota</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">TIG dokumentum</th>
              <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Bruttó</th>
              <th className="min-w-[240px] py-1.5 pr-6 text-left font-medium text-text-secondary">Számlák</th>
              <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Státusz</th>
              <th className="py-1.5 text-right font-medium text-text-secondary" />
            </tr>
          </thead>
          <tbody>
            {ready.map((c) => {
              const busy = busyId === c.employee_id;
              const invoices = c.invoices ?? [];
              return (
                <tr key={c.id} className="border-b border-border align-top last:border-0">
                  <td className="py-3 pr-6">{employeeNameById.get(c.employee_id) ?? `#${c.employee_id}`}</td>
                  <td className="py-3 pr-6">
                    {/* Kézzel is javítható: egy tévesen kiküldöttre állított TIG
                        visszavehető "Készítés alatt"-ra, és újra elkészíthető. */}
                    <TigAllapotSelect
                      postPath={`${basePath}/${projectId}/${c.employee_id}/allapot`}
                      value={c.allapot}
                      canEdit={canEdit}
                    />
                  </td>
                  {/* Az elkészült TIG dokumentuma: a generálás+küldés után ez
                      mutatja meg, mi ment ki - enélkül a kiküldött TIG-hez
                      nem vezetne út a felületről. */}
                  <td className="py-3 pr-6">
                    {c.file_url ? (
                      <a
                        href={c.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        Elkészült TIG
                      </a>
                    ) : (
                      <span className="text-text-muted">–</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap py-3 pr-6 text-right">
                    {c.brutto_osszeg != null ? `${c.brutto_osszeg.toLocaleString("hu-HU")} Ft` : "–"}
                  </td>
                  <td className="py-3 pr-6">
                    <div className="flex flex-col gap-1.5">
                      {invoices.map((inv) => (
                        <div key={inv.id} className="flex items-center gap-2">
                          <a
                            href={inv.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="max-w-[180px] truncate text-text-accent hover:underline"
                            title={inv.filename}
                          >
                            {inv.filename}
                          </a>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => deleteInvoice(c.employee_id, inv.id, inv.filename)}
                            className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                            title="Számla törlése"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      ))}
                      <label className="w-fit cursor-pointer text-[12px] text-text-accent hover:underline">
                        {busy ? "Feltöltés…" : "+ Számla feltöltése"}
                        <input
                          type="file"
                          multiple
                          disabled={busy}
                          onChange={(e) => {
                            const files = Array.from(e.target.files ?? []);
                            if (files.length > 0) uploadInvoices(c.employee_id, e.target, files);
                          }}
                          className="hidden"
                        />
                      </label>
                    </div>
                  </td>
                  <td className="py-3 pr-6 text-right">
                    {c.szamla_kifizetve ? (
                      <StatusBadge label="Kifizetve" tone="success" />
                    ) : invoices.length > 0 ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => markPaid(c.employee_id)}
                        className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                      >
                        Kifizetve jelölés
                      </button>
                    ) : (
                      <StatusBadge label="Nincs számla" tone="neutral" />
                    )}
                  </td>
                  <td className="py-3 text-right">
                    {/* A kifizetett TIG-hez Kiadás sor tartozik a Pénzügyben -
                        azt a backend nem is engedi törölni (lásd
                        performance_certificates.py delete_certificate). */}
                    {canEdit && !c.szamla_kifizetve && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => deleteCertificate(c.employee_id, employeeNameById.get(c.employee_id) ?? "a megbízott")}
                        title="TIG törlése - utána újra elkészíthető"
                        className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                      >
                        <XCircle size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
