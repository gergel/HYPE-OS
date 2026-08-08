"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import type { BelsosAttekintes } from "@/lib/api";

/** Ki mettől meddig volt belsős.
 *
 * Ettől függ, mely hónapokra vár a rendszer havi TIG-et: aki márciusban lépett
 * be, attól januárra nincs mit kérni; aki augusztusban elment, attól
 * szeptemberre sincs. Enélkül ezek a hónapok örökre "hiányzó TIG"-ként
 * állnának a listán.
 *
 * Egy embernél TÖBB időszak is felvehető – ha kilépett, majd visszajött, a
 * köztes hónapok kimaradnak.
 *
 * Ha valakinél nincs egyetlen időszak sem, a rendszer a munkatárs első/utolsó
 * munkanapjára esik vissza, annak híján pedig minden hónapra vár TIG-et (ez
 * volt a korábbi viselkedés). */
export function BelsosIdoszakok({ sorok, canEdit }: { sorok: BelsosAttekintes[]; canEdit: boolean }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitottId, setNyitottId] = useState<number | null>(null);
  const [kezdet, setKezdet] = useState("");
  const [veg, setVeg] = useState("");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function hivas(path: string, init: RequestInit) {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(path, init);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen művelet (HTTP ${res.status})`);
        return false;
      }
      router.refresh();
      return true;
    } catch (err) {
      setHiba(`Sikertelen művelet (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function felvesz(employeeId: number) {
    if (!kezdet && !veg) {
      setHiba("Adj meg legalább egy dátumot. Üres kezdet = a kezdetektől, üres vég = azóta is itt van.");
      return;
    }
    const ok = await hivas(`/api/v1/belsos-idoszakok/${employeeId}`, {
      method: "POST",
      body: JSON.stringify({ kezdet: kezdet || null, veg: veg || null }),
    });
    if (ok) {
      setKezdet("");
      setVeg("");
    }
  }

  async function torol(idoszakId: number, nev: string) {
    if (!(await confirm(`Törlöd ${nev} egyik belsős időszakát?`))) return;
    await hivas(`/api/v1/belsos-idoszakok/idoszak/${idoszakId}`, { method: "DELETE" });
  }

  return (
    <div>
      <p className="mb-3 text-[12.5px] text-text-muted">
        Csak azokra a hónapokra várunk havi TIG-et, amikor az illető tényleg belsős volt. Több időszak is felvehető –
        ha valaki kilépett, majd visszajött, a köztes hónapok kimaradnak. Üres kezdet = „a kezdetektől”, üres vég =
        „azóta is itt van”. Ha valakinél nincs időszak, a munkatárs első/utolsó munkanapja dönt.
      </p>
      {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Munkatárs</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Mettől meddig</th>
              <th className="py-1.5 text-right font-medium text-text-secondary">Most belsős</th>
            </tr>
          </thead>
          <tbody>
            {sorok.map((sor) => {
              const nyitva = nyitottId === sor.employee_id;
              return (
                <tr key={sor.employee_id} className="border-b border-border align-top last:border-0">
                  <td className="py-2.5 pr-6">
                    <a href={`/csapat/${sor.employee_id}`} className="text-text-accent hover:underline">
                      {sor.full_name}
                    </a>
                  </td>
                  <td className="py-2.5 pr-6">
                    {sor.idoszakok.length === 0 ? (
                      <span className="text-text-muted">
                        {sor.osszefoglalo ? `${sor.osszefoglalo} (munkanapok alapján)` : "Nincs megadva – minden hónap"}
                      </span>
                    ) : (
                      <span className="flex flex-col gap-1">
                        {sor.idoszakok.map((i) => (
                          <span key={i.id} className="flex items-center gap-2">
                            <span className="text-text-primary">
                              {i.kezdet ? i.kezdet : "a kezdetektől"} – {i.veg ? i.veg : "azóta is"}
                            </span>
                            {canEdit && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => torol(i.id, sor.full_name)}
                                title="Időszak törlése"
                                className="rounded-[var(--radius)] p-0.5 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                              >
                                <Trash2 size={12} />
                              </button>
                            )}
                          </span>
                        ))}
                      </span>
                    )}
                    {canEdit &&
                      (nyitva ? (
                        <span className="mt-2 flex flex-wrap items-end gap-2">
                          <span className="flex flex-col gap-0.5">
                            <label className="text-[11px] text-text-muted">Mettől</label>
                            <input
                              type="date"
                              value={kezdet}
                              onChange={(e) => setKezdet(e.target.value)}
                              disabled={busy}
                              className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none"
                            />
                          </span>
                          <span className="flex flex-col gap-0.5">
                            <label className="text-[11px] text-text-muted">Meddig</label>
                            <input
                              type="date"
                              value={veg}
                              onChange={(e) => setVeg(e.target.value)}
                              disabled={busy}
                              className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none"
                            />
                          </span>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => felvesz(sor.employee_id)}
                            className="rounded-[var(--radius)] border border-border bg-bg-accent px-2.5 py-1 text-[12.5px] text-text-accent hover:opacity-90 disabled:opacity-50"
                          >
                            Mentés
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => setNyitottId(null)}
                            className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                          >
                            Mégse
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setNyitottId(sor.employee_id);
                            setKezdet("");
                            setVeg("");
                            setHiba(null);
                          }}
                          className="mt-1 block text-[12px] text-text-accent hover:underline"
                        >
                          <Plus size={11} className="mr-0.5 inline" />
                          Időszak hozzáadása
                        </button>
                      ))}
                  </td>
                  <td className="py-2.5 text-right">
                    {sor.most_belsos ? (
                      <StatusBadge label="Igen" tone="success" />
                    ) : (
                      <StatusBadge label="Nem" tone="neutral" />
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
