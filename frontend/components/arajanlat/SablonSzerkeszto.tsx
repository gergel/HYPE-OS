"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, Plus, Search, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { MentoMezo, MentoSzam } from "./mezok";
import { type Ajanlat, type KatalogusTetel, type Megjegyzes, type Sablon, egysegCimke, ft, hivas, kuld } from "./quote";

/** Sablon-szerkesztő: a sablon adatai (összesítő címke, tipikus végösszeg,
 * megjegyzés…) és a sorai - katalógusból vagy egyedi sorként, alapértelmezett
 * alkalom / mennyiség, opcionális jelölő, sorrend. */
export function SablonSzerkeszto({ canEdit, canCreate }: { canEdit: boolean; canCreate: boolean }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [lista, setLista] = useState<Sablon[] | null>(null);
  const [kivalasztott, setKivalasztott] = useState<Sablon | null>(null);
  const [katalogus, setKatalogus] = useState<KatalogusTetel[]>([]);
  const [megjegyzesek, setMegjegyzesek] = useState<Megjegyzes[]>([]);
  const [hiba, setHiba] = useState<string | null>(null);
  const [kereses, setKereses] = useState("");

  const [frissites, setFrissites] = useState(0);
  const betoltLista = useCallback(() => setFrissites((x) => x + 1), []);

  useEffect(() => {
    hivas<Sablon[]>("/templates?include_inactive=true")
      .then(setLista)
      .catch((e: Error) => setHiba(e.message));
  }, [frissites]);

  useEffect(() => {
    hivas<KatalogusTetel[]>("/catalog/items").then(setKatalogus).catch(() => undefined);
    hivas<Megjegyzes[]>("/notes").then(setMegjegyzesek).catch(() => undefined);
  }, []);

  async function valaszt(id: number) {
    try {
      setKivalasztott(await hivas<Sablon>(`/templates/${id}`));
      setHiba(null);
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  async function muvelet(fn: () => Promise<Sablon | void>) {
    setHiba(null);
    try {
      const r = await fn();
      if (r) setKivalasztott(r);
      betoltLista();
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  const t = kivalasztott;
  const tid = t?.id;
  const modositSablon = (v: Partial<Sablon>) => muvelet(() => kuld<Sablon>(`/templates/${tid}`, "PATCH", v));
  const modositSor = (sorId: number, v: Record<string, unknown>) =>
    muvelet(() => kuld<Sablon>(`/templates/${tid}/items/${sorId}`, "PATCH", v));

  function mozgat(index: number, irany: -1 | 1) {
    if (!t?.items) return;
    const sorok = [...t.items];
    const cel = index + irany;
    if (cel < 0 || cel >= sorok.length) return;
    [sorok[index], sorok[cel]] = [sorok[cel], sorok[index]];
    void muvelet(() => kuld<Sablon>(`/templates/${tid}/items/reorder`, "PATCH", { items: sorok.map((s) => ({ id: s.id })) }));
  }

  async function ujSablon() {
    const nev = window.prompt("Az új sablon neve:")?.trim();
    if (!nev) return;
    await muvelet(() => kuld<Sablon>("/templates", "POST", { name: nev }));
  }

  async function torol() {
    if (!t || !(await confirm(`Törlöd a sablont: „${t.name}”? A belőle készült ajánlatok megmaradnak.`))) return;
    await muvelet(async () => {
      await kuld(`/templates/${t.id}`, "DELETE");
      setKivalasztott(null);
    });
  }

  async function ajanlatEbbol() {
    if (!t) return;
    try {
      const q = await kuld<Ajanlat>("", "POST", { template_id: t.id, brand: t.brand });
      router.push(`/arajanlatok/${q.id}`);
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  const k = kereses.trim().toLowerCase();
  const talalatok = k ? katalogus.filter((c) => c.name.toLowerCase().includes(k)).slice(0, 8) : [];

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[13px] font-medium text-text-primary">Sablonok</p>
          {canEdit && (
            <button type="button" onClick={ujSablon} className="btn btn-ghost flex items-center gap-1 text-[12px]">
              <Plus size={12} /> Új
            </button>
          )}
        </div>
        {lista === null ? (
          <p className="text-[12.5px] text-text-muted">Betöltés…</p>
        ) : lista.length === 0 ? (
          <p className="text-[12.5px] text-text-muted">Még nincs sablon - a Katalógus fülön az „Alapadatok betöltése” hozza be a 10 alap sablont.</p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {lista.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => valaszt(s.id)}
                  className={`w-full rounded-[var(--radius)] px-2.5 py-2 text-left text-[13px] ${t?.id === s.id ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3/60"} ${s.is_active ? "" : "opacity-50"}`}
                >
                  <span className="block">{s.name}</span>
                  <span className="text-[11.5px] text-text-muted">
                    {s.item_count} sor · alap {ft(s.base_total)}
                    {s.pricing_mode === "monthly" ? " · havidíjas" : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section className="min-w-0 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
        {hiba && <p className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</p>}
        {!t ? (
          <p className="text-[13px] text-text-muted">Válassz egy sablont a bal oldali listából.</p>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <MentoMezo ertek={t.name} tiltva={!canEdit} onMent={(v) => v.trim() && modositSablon({ name: v.trim() })} className="field min-w-[240px] flex-1 text-[15px] font-semibold" />
              {!t.is_active && <StatusBadge label="Inaktív" tone="warning" />}
              {canCreate && (
                <button type="button" onClick={ajanlatEbbol} className="btn btn-primary text-[12.5px]">
                  Új ajánlat ebből
                </button>
              )}
              {canEdit && (
                <>
                  <button type="button" onClick={() => modositSablon({ is_active: !t.is_active })} className="btn btn-ghost text-[12.5px]">
                    {t.is_active ? "Elrejtés" : "Aktiválás"}
                  </button>
                  <button type="button" onClick={torol} className="btn btn-ghost p-1.5 text-text-muted hover:text-text-danger" aria-label="Sablon törlése" title="Sablon törlése">
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <label className="flex flex-col gap-1 text-[12px] text-text-muted md:col-span-2 xl:col-span-3">
                Rövid leírás (a sablon-kártyán)
                <MentoMezo ertek={t.description} tiltva={!canEdit} onMent={(v) => modositSablon({ description: v || null })} />
              </label>
              <label className="flex flex-col gap-1 text-[12px] text-text-muted">
                Márka
                <select className="field" disabled={!canEdit} value={t.brand} onChange={(e) => modositSablon({ brand: e.target.value as Sablon["brand"] })}>
                  <option value="HYPE">HYPE</option>
                  <option value="CB">ContentBee</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-[12px] text-text-muted">
                Árazás
                <select className="field" disabled={!canEdit} value={t.pricing_mode} onChange={(e) => modositSablon({ pricing_mode: e.target.value as Sablon["pricing_mode"] })}>
                  <option value="one_off">Egyszeri</option>
                  <option value="monthly">Havidíjas</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-[12px] text-text-muted">
                Összesítő sor címkéje
                <MentoMezo ertek={t.summary_label} tiltva={!canEdit} placeholder="A PROJECT TELJES KÖLTSÉGE" onMent={(v) => modositSablon({ summary_label: v || null })} />
              </label>
              <label className="flex flex-col gap-1 text-[12px] text-text-muted">
                „Alkalom” oszlop felirata
                <MentoMezo ertek={t.occasions_label} tiltva={!canEdit} placeholder="Alkalom (pl. LED falnál: Nap)" onMent={(v) => modositSablon({ occasions_label: v || null })} />
              </label>
              <label className="flex flex-col gap-1 text-[12px] text-text-muted">
                Tipikus végösszeg (tájékoztató)
                <MentoSzam ertek={t.typical_total} penz urese tiltva={!canEdit} placeholder="–" onMent={(v) => modositSablon({ typical_total: v })} />
              </label>
              <label className="flex flex-col gap-1 text-[12px] text-text-muted">
                Megjegyzés
                <select className="field" disabled={!canEdit} value={t.default_note_id ?? ""} onChange={(e) => modositSablon({ default_note_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">(az első megjegyzés-sablon)</option>
                  {megjegyzesek.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-[13px]">
                <thead>
                  <tr className="border-b border-border text-left text-text-secondary">
                    <th className="w-36 py-1.5 pr-2 font-medium">Szekció</th>
                    <th className="py-1.5 pr-2 font-medium">Tétel (felülírható)</th>
                    <th className="w-20 py-1.5 pr-2 text-right font-medium">Alkalom</th>
                    <th className="w-20 py-1.5 pr-2 text-right font-medium">Menny.</th>
                    <th className="w-32 py-1.5 pr-2 text-right font-medium">Egységár</th>
                    <th className="w-16 py-1.5 pr-2 text-center font-medium">Opció</th>
                    <th className="w-24 py-1.5" />
                  </tr>
                </thead>
                <tbody>
                  {(t.items ?? []).map((s, i) => (
                    <tr key={s.id} className={`border-b border-border align-top ${s.is_optional ? "opacity-70" : ""}`}>
                      <td className="py-1.5 pr-2">
                        <MentoMezo ertek={s.section} tiltva={!canEdit} placeholder="–" onMent={(v) => modositSor(s.id, { section: v.trim() || null })} className="field w-full py-1" />
                      </td>
                      <td className="py-1.5 pr-2">
                        <MentoMezo ertek={s.name_override} tiltva={!canEdit} placeholder={s.catalog_item?.name ?? "Megnevezés"} onMent={(v) => modositSor(s.id, { name_override: v.trim() || null })} className="field w-full py-1 font-medium" />
                        <MentoMezo tobbsoros ertek={s.description_override} tiltva={!canEdit} placeholder={s.catalog_item?.default_description ?? "Leírás"} onMent={(v) => modositSor(s.id, { description_override: v || null })} className="field mt-1 w-full py-1 text-[12px]" />
                        <span className="text-[11px] text-text-muted">
                          {s.catalog_item ? `katalógus: ${s.catalog_item.name}` : "egyedi sor"} · {egysegCimke(s.effective.unit)}
                        </span>
                      </td>
                      <td className="py-1.5 pr-2">
                        <MentoSzam ertek={s.default_occasions} tiltva={!canEdit} onMent={(v) => v !== null && modositSor(s.id, { default_occasions: v })} className="field w-full py-1 text-right" />
                      </td>
                      <td className="py-1.5 pr-2">
                        <MentoSzam ertek={s.default_quantity} tiltva={!canEdit} onMent={(v) => v !== null && modositSor(s.id, { default_quantity: v })} className="field w-full py-1 text-right" />
                      </td>
                      <td className="py-1.5 pr-2">
                        <MentoSzam ertek={s.price_override} penz urese tiltva={!canEdit} placeholder={s.catalog_item ? ft(s.catalog_item.base_price) : "0"} onMent={(v) => modositSor(s.id, { price_override: v })} className="field w-full py-1 text-right font-mono" />
                      </td>
                      <td className="py-1.5 pr-2 text-center">
                        <input type="checkbox" disabled={!canEdit} checked={s.is_optional} onChange={(e) => modositSor(s.id, { is_optional: e.target.checked })} aria-label="Opcionális" />
                      </td>
                      <td className="whitespace-nowrap py-1.5 text-right">
                        {canEdit && (
                          <>
                            <button type="button" onClick={() => mozgat(i, -1)} disabled={i === 0} className="rounded p-1 text-text-muted hover:bg-surface-3 disabled:opacity-30" aria-label="Fel">
                              <ArrowUp size={13} />
                            </button>
                            <button type="button" onClick={() => mozgat(i, 1)} disabled={i === (t.items?.length ?? 0) - 1} className="rounded p-1 text-text-muted hover:bg-surface-3 disabled:opacity-30" aria-label="Le">
                              <ArrowDown size={13} />
                            </button>
                            <button type="button" onClick={() => muvelet(() => kuld<Sablon>(`/templates/${t.id}/items/${s.id}`, "DELETE"))} className="rounded p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger" aria-label="Sor törlése">
                              <Trash2 size={13} />
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-right text-[13px] text-text-secondary">
              Alap végösszeg (opciók nélkül): <strong className="font-mono text-text-primary">{ft(t.base_total)}</strong>
            </p>

            {canEdit && (
              <div className="flex flex-wrap items-start gap-2">
                <div className="relative min-w-[280px] flex-1">
                  <Search size={13} className="pointer-events-none absolute left-2.5 top-[11px] text-text-muted" />
                  <input className="field w-full pl-7" placeholder="Tétel hozzáadása a katalógusból…" value={kereses} onChange={(e) => setKereses(e.target.value)} />
                  {talalatok.length > 0 && (
                    <div className="absolute left-0 right-0 top-full z-20 mt-1 rounded-[var(--radius)] border border-border bg-surface-1 py-1 shadow-lg">
                      {talalatok.map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => {
                            setKereses("");
                            void muvelet(() => kuld<Sablon>(`/templates/${t.id}/items`, "POST", { catalog_item_id: c.id, section: t.items?.[t.items.length - 1]?.section ?? null }));
                          }}
                          className="flex w-full justify-between gap-2 px-3 py-1.5 text-left text-[13px] hover:bg-surface-3"
                        >
                          <span>{c.name}</span>
                          <span className="text-text-muted">{ft(c.base_price)}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn-ghost flex items-center gap-1 text-[12.5px]"
                  onClick={() => {
                    const nev = window.prompt("Az egyedi sor megnevezése:")?.trim();
                    if (nev) void muvelet(() => kuld<Sablon>(`/templates/${t.id}/items`, "POST", { name_override: nev, price_override: 0 }));
                  }}
                >
                  <Plus size={13} /> Egyedi sor
                </button>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
