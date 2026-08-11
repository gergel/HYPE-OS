"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";
import { SZERZODES_ALLAPOTOK, SZERZODES_MAR_VAN, TigAllapotSelect } from "@/components/TigAllapotSelect";
import { useConfirm } from "@/components/ConfirmProvider";
import { formatFt } from "@/lib/ido";
import type { ElkeszultSzerzodes } from "@/lib/api";

/** Egy projekt már elkészült eseti szerződései.
 *
 * A fölötte lévő "Szerződés készítés" blokk csak a TEENDŐKET sorolja fel:
 * amint egy szerződés kiküldésre kerül (vagy kihagyják), az onnan eltűnik.
 * Ez a lista mutatja meg, kinek van kész papírja - a generált dokumentum
 * linkjével és a szerződés adatlapjával, ahová az aláírt PDF feltölthető.
 *
 * Egy kész papír itt VISSZAVEHETŐ és TÖRÖLHETŐ:
 *
 * - az állapot "Készítés alatt"-ra állításával az illető visszakerül a fenti
 *   teendő-listára, ahol az adatai újra szerkeszthetők és a szerződés
 *   újragenerálható - anélkül, hogy bármit elölről kellene felvinni (lásd
 *   backend subcontractor_contracts.py set_szerzodes_allapot);
 * - a törlés a bejegyzést szünteti meg, ha tiszta lappal kell újrakezdeni
 *   (lásd delete_contract).
 *
 * Ugyanaz a két lehetőség, ami a TIG-nél már megvolt - a papírozás két oldala
 * ne viselkedjen máshogy. */
export function ElkeszultSzerzodesek({
  projectId,
  szerzodesek,
  canEdit = true,
  canDelete = true,
}: {
  projectId: number;
  szerzodesek: ElkeszultSzerzodes[];
  canEdit?: boolean;
  canDelete?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  // A számlázó fél kulcsa ("e12" / "v3"), nem ember-azonosító: a
  // szerződés cég nevére is szólhat (lásd backend services/szamlazo.py).
  const [busyId, setBusyId] = useState<string | null>(null);

  // Minden LEZÁRT szerződés ide tartozik - a "Van már szerződés" is, ami a
  // máshol elkészült papírt jelöli (lásd backend MAR_VAN_ALLAPOT).
  const kesz = szerzodesek.filter(
    (s) =>
      s.szerzodes_allapota === "Kiküldve" ||
      s.szerzodes_allapota === "Kihagyva" ||
      s.szerzodes_allapota === SZERZODES_MAR_VAN,
  );
  if (kesz.length === 0) return null;

  /** Az ALÁÍRVA visszaérkezett példány feltöltése. Külön a generált/feltöltött
   * saját dokumentumtól: az a mi papírunk, ez a visszakapott - a kettő
   * egyszerre is létezik. Amíg ez nincs meg, a projekt "aláírt szerződésre
   * vár" az utókövetés áttekintőjén. */
  async function alairtFeltolt(s: ElkeszultSzerzodes, file: File) {
    setBusyId(s.szamlazo);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${s.szamlazo}/alairt-fajl`, {
        method: "POST",
        body: fd,
      });
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
    }
  }

  async function alairtTorol(s: ElkeszultSzerzodes) {
    const ok = await confirm(`Eldobod ${s.full_name} feltöltött aláírt szerződését? Utána újra visszavárjuk.`);
    if (!ok) return;
    setBusyId(s.szamlazo);
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${s.szamlazo}/alairt-fajl`, {
        method: "DELETE",
      });
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

  async function torol(s: ElkeszultSzerzodes) {
    const ok = await confirm(
      `Törlöd ${s.full_name} szerződését erről a projektről? Ezután újra a teendők közt jelenik meg, és készíthetsz neki újat.`,
    );
    if (!ok) return;
    setBusyId(s.szamlazo);
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${s.szamlazo}`, {
        method: "DELETE",
      });
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
      <p className="mb-2 text-[13px] font-medium text-text-primary">Elkészült szerződések</p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Megbízott</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Állapot</th>
              <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Nettó</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Szerződés</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Aláírva visszaérkezett</th>
              <th className="py-1.5 text-right font-medium text-text-secondary" />
            </tr>
          </thead>
          <tbody>
            {kesz.map((s) => (
              <tr key={s.contract_id} className="border-b border-border last:border-0">
                <td className="py-2.5 pr-6">{s.full_name}</td>
                <td className="py-2.5 pr-6">
                  {/* Legördíthető: "Készítés alatt"-ra visszavéve a fél újra a
                      teendők közé kerül, és a szerződése szerkeszthető. */}
                  <TigAllapotSelect
                    postPath={`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${s.szamlazo}/allapot`}
                    value={s.szerzodes_allapota}
                    allapotok={SZERZODES_ALLAPOTOK}
                    canEdit={canEdit}
                  />
                  {/* A kihagyás indoka a jelölés mellett látszik: enélkül egy
                      hiányzó papírról később nem derülne ki, hogy szándékos volt. */}
                  {s.kihagyas_oka && (
                    <p className="mt-1 max-w-[22rem] text-[11.5px] text-text-muted">{s.kihagyas_oka}</p>
                  )}
                </td>
                <td className="whitespace-nowrap py-2.5 pr-6 text-right tabular-nums">
                  {s.netto_osszeg === null ? "–" : formatFt(s.netto_osszeg)}
                </td>
                <td className="py-2.5 pr-6">
                  <span className="flex flex-wrap gap-x-3 gap-y-1">
                    {s.szerzodes_file_url && (
                      <a
                        href={s.szerzodes_file_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        Elkészült szerződés
                      </a>
                    )}
                    {/* A szerződés saját adatlapja: ide tölthető fel az aláírva
                        visszakapott PDF. */}
                    <a href={`/szerzodesek/${s.contract_id}`} className="text-text-accent hover:underline">
                      Adatlap és fájlok
                    </a>
                  </span>
                </td>
                <td className="py-2.5 pr-6">
                  {/* A KIHAGYOTT szerződésnél nincs papír, amit vissza lehetne
                      várni - ott nincs mit mutatni. */}
                  {s.szerzodes_allapota !== "Kiküldve" ? (
                    <span className="text-text-muted">–</span>
                  ) : s.alairva ? (
                    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <StatusBadge label="Megérkezett" tone="success" />
                      {s.alairt_file_url && (
                        <a
                          href={s.alairt_file_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-text-accent hover:underline"
                        >
                          Aláírt példány
                        </a>
                      )}
                      {canEdit && (
                        <button
                          type="button"
                          disabled={busyId === s.szamlazo}
                          onClick={() => alairtTorol(s)}
                          className="text-[12px] text-text-muted hover:text-text-danger disabled:opacity-50"
                        >
                          Eldobás
                        </button>
                      )}
                    </span>
                  ) : (
                    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <StatusBadge label="Visszavárjuk" tone="warning" />
                      {canEdit && (
                        <label className="cursor-pointer text-[12px] text-text-accent hover:underline">
                          Feltöltés
                          <input
                            type="file"
                            className="hidden"
                            disabled={busyId === s.szamlazo}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              // Az input értékét nullázzuk, hogy ugyanazt a
                              // fájlt újra ki lehessen választani egy hibás
                              // feltöltés után.
                              e.target.value = "";
                              if (file) alairtFeltolt(s, file);
                            }}
                          />
                        </label>
                      )}
                    </span>
                  )}
                </td>
                <td className="py-2.5 text-right">
                  {canDelete && (
                    <button
                      type="button"
                      disabled={busyId === s.szamlazo}
                      onClick={() => torol(s)}
                      title="Szerződés törlése - utána újra elkészíthető"
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
      </div>
    </div>
  );
}
