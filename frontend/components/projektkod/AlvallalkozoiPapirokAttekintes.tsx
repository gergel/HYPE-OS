"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FileCheck2, FileSignature, Trash2 } from "lucide-react";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import { formatFt } from "@/lib/ido";
import type { ElkeszultSzerzodes, PerformanceCertificate } from "@/lib/api";

function tigSzamlazoKulcs(t: PerformanceCertificate): string {
  return t.vallalkozas_id ? `v${t.vallalkozas_id}` : `e${t.employee_id}`;
}

/** Alvállalkozói szerződés/TIG áttekintés egy PROJEKTKÓDON, forgatás nélkül -
 * lásd projekt/ProjektPapirokEsKoltsegek (a forgatáshoz kötött megfelelője,
 * ugyanaz a szerep): ez NÉZET, nem munkafelület - a papír ELKÉSZÍTÉSE
 * (mentés, generálás, küldés, kihagyás) továbbra is az Utókövetésen történik,
 * lásd utokovetes/projektkodok/[id].
 *
 * A TÖRLÉS viszont innen is elérhető: a szerződés és a TIG EGYBEN, egy
 * kattintással törölhető (bármelyik listából indítva ugyanazt a végpontot
 * hívja - lásd backend subcontractor_contracts.delete_contract_projektkodon,
 * ami a TIG-et is magával viszi), hogy ne kelljen ehhez átmenni az
 * Utókövetésre. */
export function AlvallalkozoiPapirokAttekintes({
  projectCodeId,
  szerzodesek,
  tigek,
  lathatKoltseget,
  canDelete = false,
}: {
  projectCodeId: number;
  szerzodesek: ElkeszultSzerzodes[];
  tigek: PerformanceCertificate[];
  lathatKoltseget: boolean;
  canDelete?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busyKulcs, setBusyKulcs] = useState<string | null>(null);
  const utokovetes = `/utokovetes/projektkodok/${projectCodeId}`;

  async function torol(szamlazoKulcs: string, nev: string) {
    const ok = await confirm(
      `Törlöd ${nev} szerződését és teljesítési igazolását erről a projektkódról? Ez mindkét papírt egyszerre törli.`,
    );
    if (!ok) return;
    setBusyKulcs(szamlazoKulcs);
    try {
      const res = await authFetch(
        `/api/v1/alvallalkozoi-szerzodesek/projektkodok/${projectCodeId}/${szamlazoKulcs}`,
        { method: "DELETE" },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusyKulcs(null);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <Card title={`Alvállalkozói szerződések (${szerzodesek.length})`} icon={FileSignature}>
        {szerzodesek.length === 0 ? (
          <p className="text-[13px] text-text-secondary">Még nincs elkészült szerződés ehhez a projektkódhoz.</p>
        ) : (
          <ul className="space-y-2">
            {szerzodesek.map((sz) => (
              <li key={sz.contract_id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                <span className="text-text-primary">{sz.full_name}</span>
                <span className="flex items-center gap-2">
                  {sz.netto_osszeg != null && lathatKoltseget && (
                    <span className="text-text-secondary">{formatFt(sz.netto_osszeg)}</span>
                  )}
                  <StatusBadge
                    label={sz.alairva ? "Aláírva" : (sz.szerzodes_allapota ?? "Készítés alatt")}
                    tone={sz.alairva ? "success" : sz.szerzodes_allapota === "Kiküldve" ? "warning" : "neutral"}
                  />
                  {canDelete && (
                    <button
                      type="button"
                      disabled={busyKulcs === sz.szamlazo}
                      onClick={() => torol(sz.szamlazo, sz.full_name)}
                      title="Szerződés és TIG törlése erről a projektkódról"
                      className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
        <a href={utokovetes} className="mt-3 block text-[12.5px] text-text-accent hover:underline">
          Szerződés készítése, kiküldése → Utókövetés
        </a>
      </Card>

      <Card title={`Alvállalkozói TIG-ek (${tigek.length})`} icon={FileCheck2}>
        {tigek.length === 0 ? (
          <p className="text-[13px] text-text-secondary">Még nincs teljesítési igazolás ehhez a projektkódhoz.</p>
        ) : (
          <ul className="space-y-2">
            {tigek.map((t) => {
              const kulcs = tigSzamlazoKulcs(t);
              const nev = t.ceg_neve ?? `TIG #${t.id}`;
              return (
                <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                  <span className="text-text-primary">{nev}</span>
                  <span className="flex items-center gap-2">
                    {t.netto_osszeg != null && lathatKoltseget && (
                      <span className="text-text-secondary">{formatFt(t.netto_osszeg)}</span>
                    )}
                    {/* A KIFIZETÉS a TIG utolsó lépése - amíg nincs meg, a papír
                        önmagában nem zárja le az ügyet (lásd
                        ProjektPapirokEsKoltsegek, a forgatás-alapú
                        megfelelője). */}
                    <StatusBadge
                      label={
                        t.szamla_kifizetve
                          ? "Kifizetve"
                          : t.szamla_kihagyva
                            ? "Nincs számla"
                            : (t.allapot ?? "Készítés alatt")
                      }
                      tone={t.szamla_kifizetve ? "success" : t.allapot === "Kiküldve" ? "warning" : "neutral"}
                    />
                    {/* A törlés a TIG kifizetve állapotánál a szerveren megáll
                        (lásd delete_contract_projektkodon) - a fizetés tényét
                        előbb a Pénzügyben kell rendezni. */}
                    {canDelete && (
                      <button
                        type="button"
                        disabled={busyKulcs === kulcs}
                        onClick={() => torol(kulcs, nev)}
                        title="Szerződés és TIG törlése erről a projektkódról"
                        className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <a href={utokovetes} className="mt-3 block text-[12.5px] text-text-accent hover:underline">
          TIG készítése, kiküldése → Utókövetés
        </a>
      </Card>
    </div>
  );
}
