"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { TIG_ALLAPOTOK, TigAllapotSelect } from "@/components/TigAllapotSelect";
import { useConfirm } from "@/components/ConfirmProvider";
import { formatFt } from "@/lib/ido";
import type { PerformanceCertificate } from "@/lib/api";

/** Egy projektkód (forgatás nélküli alvállalkozói kiadás) már elkészült
 * teljesítési igazolásai - lásd ElkeszultSzerzodesek (a szerződés-oldali
 * megfelelője, ugyanaz a minta). Egyszerűbb annál: itt nincs "aláírva
 * visszaérkezett" fogalom (a TIG saját generált/feltöltött fájlja MAGA a
 * végleges dokumentum), és nincs számla-allépés sem - a kifizetés állapotát
 * ezen az ágon az Expense hordozza, lásd backend
 * performance_certificates.py "projektkód-szintű ág" fejléce. */
export function ElkeszultTigProjektkod({
  projectCodeId,
  tigek,
  canEdit = true,
  canDelete = true,
}: {
  projectCodeId: number;
  tigek: PerformanceCertificate[];
  canEdit?: boolean;
  canDelete?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const base = `/api/v1/teljesitesi-igazolasok/projektkodok/${projectCodeId}`;
  // A számlázó fél kulcsa ("e12" / "v3"), nem a TIG saját id-ja.
  const [busyId, setBusyId] = useState<string | null>(null);

  const kesz = tigek.filter((t) => t.allapot === "Kiküldve" || t.allapot === "Kihagyva");
  if (kesz.length === 0) return null;

  function szamlazoKulcs(t: PerformanceCertificate): string {
    return t.vallalkozas_id ? `v${t.vallalkozas_id}` : `e${t.employee_id}`;
  }

  async function torol(t: PerformanceCertificate) {
    const kulcs = szamlazoKulcs(t);
    const ok = await confirm(
      `Törlöd ${t.ceg_neve ?? "ezt a felet"} TIG-jét erről a projektkódról? Ezután újra a teendők közt jelenik meg, és készíthetsz neki újat.`,
    );
    if (!ok) return;
    setBusyId(kulcs);
    try {
      const res = await authFetch(`${base}/${kulcs}`, { method: "DELETE" });
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

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="mb-2 text-[13px] font-medium text-text-primary">Elkészült teljesítési igazolások</p>
      <div className="overflow-x-auto">
        <table className="os-table min-w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Megbízott</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Állapot</th>
              <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Nettó</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">TIG</th>
              <th className="py-1.5 text-right font-medium text-text-secondary" />
            </tr>
          </thead>
          <tbody>
            {kesz.map((t) => {
              const kulcs = szamlazoKulcs(t);
              return (
                <tr key={t.id} className="border-b border-border last:border-0">
                  <td className="py-2.5 pr-6">{t.ceg_neve ?? `TIG #${t.id}`}</td>
                  <td className="py-2.5 pr-6">
                    <TigAllapotSelect
                      postPath={`${base}/${kulcs}/allapot`}
                      value={t.allapot}
                      allapotok={TIG_ALLAPOTOK}
                      canEdit={canEdit}
                    />
                    {t.kihagyas_oka && (
                      <p className="mt-1 max-w-[22rem] text-[11.5px] text-text-muted">{t.kihagyas_oka}</p>
                    )}
                  </td>
                  <td className="whitespace-nowrap py-2.5 pr-6 text-right tabular-nums">
                    {t.netto_osszeg === null ? "–" : formatFt(t.netto_osszeg)}
                  </td>
                  <td className="py-2.5 pr-6">
                    {t.file_url ? (
                      <a href={t.file_url} target="_blank" rel="noreferrer" className="text-text-accent hover:underline">
                        Elkészült TIG
                      </a>
                    ) : (
                      <span className="text-text-muted">–</span>
                    )}
                  </td>
                  <td className="py-2.5 text-right">
                    {canDelete && (
                      <button
                        type="button"
                        disabled={busyId === kulcs}
                        onClick={() => torol(t)}
                        title="TIG törlése - utána újra elkészíthető"
                        className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                      >
                        <Trash2 size={13} />
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
