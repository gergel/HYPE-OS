"use client";

import { Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import type { InternalPerformanceCertificateInvoice } from "@/lib/api";

/** Egy hónap két papírja: az aláírt TIG és a hozzá kiállított számlák.
 *
 * Azért itt, a hónap oldalán, mert a kérdés is itt merül fel ("megvan-e már
 * ehhez a hónaphoz minden?") - és mindkettő ugyanúgy kezelhető: feltöltés és
 * törlés. A TIG-ből EGY van (új feltöltés lecseréli az előzőt), számlából
 * több is lehet (részszámlák), ezért azok külön-külön törölhetők. */
export function HonapDokumentumok({
  employeeId,
  ev,
  honap,
  tigUrl,
  szamlak,
  szerkeszthet,
  torolhet,
}: {
  employeeId: number;
  ev: number;
  honap: number;
  tigUrl: string | null;
  szamlak: InternalPerformanceCertificateInvoice[];
  szerkeszthet: boolean;
  torolhet: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [dolgozik, setDolgozik] = useState(false);
  const alap = `/api/v1/belsos-tig/${employeeId}/${ev}/${honap}`;

  async function hivas(url: string, init: RequestInit, hibaCimke: string) {
    setDolgozik(true);
    try {
      const valasz = await authFetch(url, init);
      if (!valasz.ok) {
        const reszlet = await valasz.json().catch(() => null);
        alert(`${hibaCimke}: ${reszlet?.detail ?? valasz.status}`);
        return false;
      }
      router.refresh();
      return true;
    } catch (hiba) {
      alert(`${hibaCimke} (hálózati hiba): ${hiba}`);
      return false;
    } finally {
      setDolgozik(false);
    }
  }

  async function tigFeltoltes(input: HTMLInputElement, file: File) {
    const fd = new FormData();
    fd.append("file", file);
    await hivas(`${alap}/tig-fajl`, { method: "POST", body: fd }, `Sikertelen feltöltés (${file.name})`);
    input.value = "";
  }

  async function tigTorles() {
    if (!(await confirm("Biztosan törlöd a hónaphoz tartozó TIG dokumentumot?"))) return;
    await hivas(`${alap}/tig-fajl`, { method: "DELETE" }, "Sikertelen törlés");
  }

  async function szamlaFeltoltes(input: HTMLInputElement, files: File[]) {
    // Egyesével megy fel: minden hívás egy külön számla-sort hoz létre.
    for (const file of files) {
      const fd = new FormData();
      fd.append("file", file);
      const sikeres = await hivas(
        `${alap}/szamla`,
        { method: "POST", body: fd },
        `Sikertelen feltöltés (${file.name})`,
      );
      if (!sikeres) break;
    }
    input.value = "";
  }

  async function szamlaTorles(id: number, filename: string) {
    if (!(await confirm(`Biztosan törlöd ezt a számlát: "${filename}"?`))) return;
    await hivas(`${alap}/szamla/${id}`, { method: "DELETE" }, "Sikertelen törlés");
  }

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div>
        <p className="t-label mb-2">TIG dokumentum</p>
        {tigUrl ? (
          <div className="flex items-center gap-2">
            <a
              href={tigUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="truncate text-[13px] text-text-accent hover:underline"
            >
              Aláírt TIG megnyitása
            </a>
            {torolhet && (
              <button
                type="button"
                disabled={dolgozik}
                onClick={tigTorles}
                className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                title="TIG dokumentum törlése"
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        ) : (
          <p className="text-[13px] text-text-muted">Nincs feltöltött TIG dokumentum.</p>
        )}
        {szerkeszthet && (
          <label className="mt-2 flex w-fit cursor-pointer items-center gap-1.5 text-[12.5px] text-text-accent hover:underline">
            <Upload size={13} />
            {dolgozik ? "Feltöltés…" : tigUrl ? "TIG cseréje" : "TIG feltöltése"}
            <input
              type="file"
              disabled={dolgozik}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) tigFeltoltes(e.target, file);
              }}
              className="hidden"
            />
          </label>
        )}
      </div>

      <div>
        <p className="t-label mb-2">Számlák ({szamlak.length})</p>
        {szamlak.length === 0 ? (
          <p className="text-[13px] text-text-muted">Nincs feltöltött számla.</p>
        ) : (
          <ul className="space-y-1.5">
            {szamlak.map((szamla) => (
              <li key={szamla.id} className="flex items-center gap-2">
                <a
                  href={szamla.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate text-[13px] text-text-accent hover:underline"
                  title={szamla.filename}
                >
                  {szamla.filename}
                </a>
                {torolhet && (
                  <button
                    type="button"
                    disabled={dolgozik}
                    onClick={() => szamlaTorles(szamla.id, szamla.filename)}
                    className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                    title="Számla törlése"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {szerkeszthet && (
          <label className="mt-2 flex w-fit cursor-pointer items-center gap-1.5 text-[12.5px] text-text-accent hover:underline">
            <Upload size={13} />
            {dolgozik ? "Feltöltés…" : "Számla feltöltése"}
            <input
              type="file"
              multiple
              disabled={dolgozik}
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                if (files.length > 0) szamlaFeltoltes(e.target, files);
              }}
              className="hidden"
            />
          </label>
        )}
      </div>
    </div>
  );
}
