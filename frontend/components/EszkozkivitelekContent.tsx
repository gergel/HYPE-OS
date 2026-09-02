"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { SearchableIdPicker } from "@/components/SearchableIdPicker";
import { StatusBadge } from "@/components/StatusBadge";
import type { EszkozKivitelSor } from "@/lib/api";

type ValaszthatoProjekt = { id: number; nev: string; projektkod: string | null; datum: string | null };

function datum(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

/** Az eszközkivitelek kezelő-nézete: kód-generálás forgatásokhoz, és
 * kivitelenkénti tétel-lista a HIÁNNYAL (kivitt > visszahozott). A hiány
 * szándékosan csak itt látszik, a publikus /eszkozkivitel oldalon nem
 * (a felhasználó kérése). */
export function EszkozkivitelekContent({
  kivitelek,
  projektek,
  canCreate,
  canDelete,
}: {
  kivitelek: EszkozKivitelSor[];
  projektek: ValaszthatoProjekt[];
  canCreate: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const [valasztott, setValasztott] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [nyitott, setNyitott] = useState<Set<number>>(new Set());

  async function general() {
    if (valasztott === null || busy) return;
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/eszkozkivitelek/generalas", {
        method: "POST",
        body: JSON.stringify({ project_id: valasztott }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      setValasztott(null);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function torol(id: number) {
    if (!confirm("Biztosan törlöd ezt a kivitelt a beírt tételeivel együtt?")) return;
    const res = await authFetch(`/api/v1/eszkozkivitelek/${id}`, { method: "DELETE" });
    if (!res.ok) {
      alert(`Sikertelen törlés: ${res.status}`);
      return;
    }
    router.refresh();
  }

  function nyitZar(id: number) {
    setNyitott((elozo) => {
      const uj = new Set(elozo);
      if (uj.has(id)) uj.delete(id);
      else uj.add(id);
      return uj;
    });
  }

  return (
    <div className="space-y-4">
      {canCreate && (
        <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-2 p-3">
          <span className="text-[13px] text-text-secondary">Kód generálása forgatáshoz:</span>
          <SearchableIdPicker
            value={valasztott}
            options={projektek.map((p) => ({
              id: p.id,
              label: p.nev,
              sublabel: [p.projektkod, datum(p.datum)].filter(Boolean).join(" · "),
            }))}
            onChange={setValasztott}
            placeholder="Válassz forgatást…"
            className="min-w-[16rem]"
          />
          <button
            type="button"
            disabled={valasztott === null || busy}
            onClick={general}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Kód generálása
          </button>
          <span className="text-[12px] text-text-muted">
            A kapott kóddal a stáb az /eszkozkivitel oldalon lép be. Az &quot;admin&quot; kód mindig él, és a
            teszt-kivitelbe visz.
          </span>
        </div>
      )}

      {kivitelek.length === 0 ? (
        <p className="text-[13px] text-text-muted">Még nincs kivitel - generálj kódot egy forgatáshoz.</p>
      ) : (
        <div className="space-y-2">
          {kivitelek.map((k) => {
            const lenyitva = nyitott.has(k.id);
            const kivittOsszes = k.tetelek.reduce((s, t) => s + t.kivitt_db, 0);
            const visszaOsszes = k.tetelek.reduce((s, t) => s + t.visszahozott_db, 0);
            return (
              <div key={k.id} className="rounded-[var(--radius)] border border-border bg-surface-2">
                <button
                  type="button"
                  onClick={() => nyitZar(k.id)}
                  className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2.5 text-left"
                >
                  <span className="font-mono text-[15px] font-semibold tracking-widest text-text-accent">
                    {k.kod}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13.5px] text-text-primary">
                    {k.teszt ? "TESZT KIVITEL" : (k.projekt_nev ?? `#${k.project_id}`)}
                    {k.projektkod && <span className="ml-2 text-text-muted">{k.projektkod}</span>}
                  </span>
                  <span className="text-[12.5px] text-text-muted">
                    {datum(k.forgatas_datuma)}
                    {k.ervenyes_eddig && ` · érvényes: ${datum(k.ervenyes_eddig)}`}
                  </span>
                  {k.allapot === "kivitel" && <StatusBadge label="Kivitel folyamatban" tone="blue" />}
                  {k.allapot === "vissza" && <StatusBadge label="Visszahozatal folyamatban" tone="orange" />}
                  {k.allapot === "lezart" && <StatusBadge label="Lezárva" tone="success" />}
                  {!k.ervenyes && <StatusBadge label="Lejárt" tone="neutral" />}
                  <span className="text-[12.5px] text-text-secondary">
                    {kivittOsszes} db kivitt · {visszaOsszes} db vissza
                  </span>
                  {k.hianyos_tetelek > 0 ? (
                    <StatusBadge label={`${k.hianyos_tetelek} tétel hiányzik!`} tone="danger" />
                  ) : (
                    kivittOsszes > 0 && <StatusBadge label="Minden visszajött" tone="success" />
                  )}
                </button>
                {lenyitva && (
                  <div className="border-t border-border px-3 py-2">
                    {k.megjegyzes && (
                      <p className="mb-2 rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[13px] text-text-primary">
                        <span className="font-medium">Észrevétel a lezáráskor:</span> {k.megjegyzes}
                      </p>
                    )}
                    {k.tetelek.length === 0 ? (
                      <p className="py-1 text-[12.5px] text-text-muted">Még nincs beírt tétel.</p>
                    ) : (
                      <table className="w-full text-[13px]">
                        <thead>
                          <tr className="border-b border-border text-left text-text-secondary">
                            <th className="py-1 font-medium">Eszköz</th>
                            <th className="py-1 text-right font-medium">Kivitt</th>
                            <th className="py-1 text-right font-medium">Visszahozott</th>
                            <th className="py-1 text-right font-medium">Hiány</th>
                          </tr>
                        </thead>
                        <tbody>
                          {k.tetelek.map((t) => {
                            const hiany = t.kivitt_db - t.visszahozott_db;
                            return (
                              <tr key={t.id} className="border-b border-border last:border-0">
                                <td className="py-1.5">
                                  {t.nev}
                                  {t.kategoria && (
                                    <span className="ml-2 text-[11.5px] text-text-muted">{t.kategoria}</span>
                                  )}
                                </td>
                                <td className="py-1.5 text-right tabular-nums">{t.kivitt_db} db</td>
                                <td className="py-1.5 text-right tabular-nums">{t.visszahozott_db} db</td>
                                <td
                                  className={`py-1.5 text-right tabular-nums ${
                                    hiany > 0 ? "font-semibold text-text-danger" : "text-text-muted"
                                  }`}
                                >
                                  {hiany > 0 ? `${hiany} db` : "–"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                    {canDelete && (
                      <button
                        type="button"
                        onClick={() => torol(k.id)}
                        className="mt-2 inline-flex items-center gap-1 text-[12.5px] text-text-secondary hover:text-text-danger"
                      >
                        <Trash2 size={13} /> Kivitel törlése
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
