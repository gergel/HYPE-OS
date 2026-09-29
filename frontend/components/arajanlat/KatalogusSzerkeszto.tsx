"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { Archive, History, Plus, RotateCcw, Search } from "lucide-react";
import { Card } from "@/components/Card";
import { useToast } from "@/components/ToastProvider";
import { MentoMezo, MentoSzam } from "./mezok";
import { EGYSEGEK, type Egyseg, type Kategoria, type KatalogusTetel, ft, hivas, kuld } from "./quote";

type Tortenet = { id: number; old_price: number | null; new_price: number; changed_at: string | null; changed_by: string | null };

/** A tétel-katalógus szerkesztője: helyben átírható név, leírás, egység,
 * alapár (ártörténettel), tájékoztató ársáv; új tétel, archiválás. Az
 * átárazás a meglévő ajánlatokat NEM írja át (ár-snapshot). */
export function KatalogusSzerkeszto({ canEdit }: { canEdit: boolean }) {
  const toast = useToast();
  const [tetelek, setTetelek] = useState<KatalogusTetel[] | null>(null);
  const [kategoriak, setKategoriak] = useState<Kategoria[]>([]);
  const [kereses, setKereses] = useState("");
  const [kat, setKat] = useState<number | null>(null);
  const [archivaltak, setArchivaltak] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [tortenet, setTortenet] = useState<{ id: number; sorok: Tortenet[] } | null>(null);
  const [uj, setUj] = useState<{ nev: string; kat: string; egyseg: Egyseg; ar: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const [frissites, setFrissites] = useState(0);
  const betolt = useCallback(() => setFrissites((x) => x + 1), []);

  useEffect(() => {
    let el = false;
    Promise.all([
      hivas<KatalogusTetel[]>(`/catalog/items?include_inactive=${archivaltak}`),
      hivas<Kategoria[]>("/catalog/categories"),
    ])
      .then(([t, k]) => {
        if (el) return;
        setTetelek(t);
        setKategoriak(k);
      })
      .catch((e: Error) => !el && setHiba(e.message));
    return () => {
      el = true;
    };
  }, [archivaltak, frissites]);

  async function modosit(t: KatalogusTetel, valtozas: Partial<KatalogusTetel>) {
    setHiba(null);
    try {
      const r = await kuld<KatalogusTetel>(`/catalog/items/${t.id}`, "PATCH", valtozas);
      setTetelek((l) => (l ?? []).map((x) => (x.id === r.id ? r : x)));
      if ("base_price" in valtozas) {
        toast(`Új alapár: ${ft(r.base_price)} - a meglévő ajánlatok nem változnak.`);
        if (tortenet?.id === t.id) void mutatTortenet(t.id, true);
      }
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  async function mutatTortenet(id: number, frissit = false) {
    if (tortenet?.id === id && !frissit) {
      setTortenet(null);
      return;
    }
    try {
      setTortenet({ id, sorok: await hivas<Tortenet[]>(`/catalog/items/${id}/history`) });
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  async function archival(t: KatalogusTetel) {
    try {
      if (t.is_active) await kuld(`/catalog/items/${t.id}`, "DELETE");
      else await kuld(`/catalog/items/${t.id}`, "PATCH", { is_active: true });
      betolt();
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  async function felvesz() {
    if (!uj || !uj.nev.trim() || !uj.kat) return;
    setBusy(true);
    try {
      await kuld("/catalog/items", "POST", {
        category_id: Number(uj.kat),
        name: uj.nev.trim(),
        unit: uj.egyseg,
        base_price: Math.round(Number((uj.ar || "0").replace(/\s/g, "").replace(",", "."))) || 0,
      });
      setUj(null);
      betolt();
    } catch (e) {
      setHiba((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function ujKategoria() {
    const nev = window.prompt("Az új kategória neve:")?.trim();
    if (!nev) return;
    try {
      await kuld("/catalog/categories", "POST", { name: nev });
      betolt();
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  async function alapadatok() {
    setBusy(true);
    try {
      const r = await kuld<Record<string, number>>("/seed", "POST");
      toast(`Alapadatok: ${r.tetel} új tétel, ${r.sablon} új sablon, ${r.kategoria} új kategória.`);
      betolt();
    } catch (e) {
      setHiba((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const k = kereses.trim().toLowerCase();
  const lathato = (tetelek ?? []).filter(
    (t) => (kat === null || t.category_id === kat) && (!k || t.name.toLowerCase().includes(k) || (t.default_description ?? "").toLowerCase().includes(k)),
  );
  const kategoriankent = kategoriak
    .map((c) => ({ kat: c, sorok: lathato.filter((t) => t.category_id === c.id) }))
    .filter((x) => x.sorok.length > 0);

  return (
    <Card
      title="Tétel-katalógus"
      actions={
        canEdit ? (
          <div className="flex flex-wrap gap-1.5">
            <button type="button" className="btn btn-ghost text-[12.5px]" onClick={ujKategoria}>
              + Kategória
            </button>
            <button
              type="button"
              className="btn btn-primary flex items-center gap-1 text-[12.5px]"
              onClick={() => setUj({ nev: "", kat: String(kat ?? kategoriak[0]?.id ?? ""), egyseg: "db", ar: "" })}
            >
              <Plus size={13} /> Új tétel
            </button>
          </div>
        ) : null
      }
    >
      <p className="mb-3 text-[12.5px] text-text-muted">
        Az alapárat a katalógus-panel egy kattintással írja be az ajánlatba. Átárazáskor a meglévő ajánlatok nem változnak -
        a szerkesztőben jelzés mutatja, ha egy sor ára eltér a mostani katalógusártól. A min–max csak tájékoztató.
      </p>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input className="field w-full pl-7" placeholder="Keresés…" value={kereses} onChange={(e) => setKereses(e.target.value)} />
        </div>
        <select className="field w-auto" value={kat ?? ""} onChange={(e) => setKat(e.target.value ? Number(e.target.value) : null)} aria-label="Kategória">
          <option value="">Minden kategória</option>
          {kategoriak.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-[12.5px] text-text-secondary">
          <input type="checkbox" checked={archivaltak} onChange={(e) => setArchivaltak(e.target.checked)} /> archiváltak is
        </label>
        {canEdit && (
          <button type="button" disabled={busy} className="btn btn-ghost text-[12.5px]" onClick={alapadatok} title="A 98 alap tétel, 10 sablon és a standard megjegyzés - a meglévőt és az átírtat nem bántja">
            Alapadatok betöltése
          </button>
        )}
      </div>
      {hiba && <p className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</p>}
      {uj && (
        <div className="mb-4 flex flex-wrap items-end gap-2 rounded-[var(--radius)] border border-border bg-surface-3/50 p-3">
          <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-[12px] text-text-muted">
            Név
            <input className="field" autoFocus value={uj.nev} onChange={(e) => setUj({ ...uj, nev: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Kategória
            <select className="field" value={uj.kat} onChange={(e) => setUj({ ...uj, kat: e.target.value })}>
              {kategoriak.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Egység
            <select className="field" value={uj.egyseg} onChange={(e) => setUj({ ...uj, egyseg: e.target.value as Egyseg })}>
              {EGYSEGEK.map((x) => (
                <option key={x.ertek} value={x.ertek}>
                  {x.cimke}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Alapár (Ft)
            <input className="field w-32 text-right" inputMode="numeric" value={uj.ar} onChange={(e) => setUj({ ...uj, ar: e.target.value })} />
          </label>
          <button type="button" disabled={busy || !uj.nev.trim() || !uj.kat} className="btn btn-primary text-[13px]" onClick={felvesz}>
            Felvétel
          </button>
          <button type="button" className="btn btn-ghost text-[13px]" onClick={() => setUj(null)}>
            Mégse
          </button>
        </div>
      )}
      {tetelek === null ? (
        <p className="text-[13px] text-text-muted">Betöltés…</p>
      ) : kategoriankent.length === 0 ? (
        <p className="text-[13px] text-text-secondary">
          {tetelek.length === 0 ? "A katalógus üres - az „Alapadatok betöltése” gombbal jön be a 98 alap tétel." : "Nincs találat."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-text-secondary">
                <th className="py-1.5 pr-2 font-medium">Tétel</th>
                <th className="py-1.5 pr-2 font-medium">Alapértelmezett leírás</th>
                <th className="w-28 py-1.5 pr-2 font-medium">Egység</th>
                <th className="w-32 py-1.5 pr-2 text-right font-medium">Alapár</th>
                <th className="w-28 py-1.5 pr-2 text-right font-medium">Min</th>
                <th className="w-28 py-1.5 pr-2 text-right font-medium">Max</th>
                <th className="w-20 py-1.5 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {kategoriankent.map(({ kat: c, sorok }) => (
                <Fragment key={c.id}>
                  <tr>
                    <td colSpan={7} className="bg-surface-3/60 px-2 py-1.5 text-[12.5px] font-semibold text-text-primary">
                      {c.name} <span className="font-normal text-text-muted">({sorok.length})</span>
                    </td>
                  </tr>
                  {sorok.map((t) => (
                    <Fragment key={t.id}>
                      <tr className={`border-b border-border align-top ${t.is_active ? "" : "opacity-50"}`}>
                        <td className="py-1.5 pr-2">
                          <MentoMezo ertek={t.name} tiltva={!canEdit} onMent={(v) => v.trim() && modosit(t, { name: v.trim() })} className="field w-full py-1" />
                        </td>
                        <td className="py-1.5 pr-2">
                          <MentoMezo tobbsoros ertek={t.default_description} tiltva={!canEdit} onMent={(v) => modosit(t, { default_description: v || null })} className="field w-full resize-y py-1 text-[12.5px]" placeholder="–" />
                        </td>
                        <td className="py-1.5 pr-2">
                          <select className="field w-full py-1" disabled={!canEdit} value={t.unit} onChange={(e) => modosit(t, { unit: e.target.value as Egyseg })}>
                            {EGYSEGEK.map((x) => (
                              <option key={x.ertek} value={x.ertek}>
                                {x.cimke}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-1.5 pr-2">
                          <MentoSzam ertek={t.base_price} penz tiltva={!canEdit} onMent={(v) => v !== null && modosit(t, { base_price: v })} className="field w-full py-1 text-right font-mono tabular-nums" />
                        </td>
                        <td className="py-1.5 pr-2">
                          <MentoSzam ertek={t.price_min} penz urese tiltva={!canEdit} placeholder="–" onMent={(v) => modosit(t, { price_min: v })} className="field w-full py-1 text-right text-text-muted tabular-nums" />
                        </td>
                        <td className="py-1.5 pr-2">
                          <MentoSzam ertek={t.price_max} penz urese tiltva={!canEdit} placeholder="–" onMent={(v) => modosit(t, { price_max: v })} className="field w-full py-1 text-right text-text-muted tabular-nums" />
                        </td>
                        <td className="whitespace-nowrap py-1.5 text-right">
                          <button type="button" title="Ártörténet" onClick={() => mutatTortenet(t.id)} className="rounded p-1 text-text-muted hover:bg-surface-3">
                            <History size={14} />
                          </button>
                          {canEdit && (
                            <button type="button" title={t.is_active ? "Archiválás (a meglévő ajánlatok hivatkozása megmarad)" : "Visszaállítás"} onClick={() => archival(t)} className="rounded p-1 text-text-muted hover:bg-surface-3">
                              {t.is_active ? <Archive size={14} /> : <RotateCcw size={14} />}
                            </button>
                          )}
                        </td>
                      </tr>
                      {tortenet?.id === t.id && (
                        <tr className="border-b border-border bg-surface-3/30">
                          <td colSpan={7} className="px-3 py-2 text-[12.5px] text-text-secondary">
                            {tortenet.sorok.length === 0 ? (
                              "Még nem változott az ára."
                            ) : (
                              <ul className="flex flex-col gap-0.5">
                                {tortenet.sorok.map((h) => (
                                  <li key={h.id}>
                                    {(h.changed_at ?? "").slice(0, 16).replace("T", " ")} ·{" "}
                                    {h.old_price === null ? "felvéve" : `${ft(h.old_price)} →`} <strong>{ft(h.new_price)}</strong>
                                    {h.changed_by ? ` · ${h.changed_by}` : ""}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
