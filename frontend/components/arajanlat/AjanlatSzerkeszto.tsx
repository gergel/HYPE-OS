"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Copy,
  FileSpreadsheet,
  FileText,
  GitBranch,
  GripVertical,
  MoreHorizontal,
  Plus,
  Save,
  Search,
  Trash2,
} from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";
import { UgyfelValaszto } from "./UjAjanlatModal";
import {
  MARKAK,
  STATUSZOK,
  type Ajanlat,
  type AjanlatSor,
  type Kategoria,
  type KatalogusTetel,
  type Megjegyzes,
  egysegCimke,
  ft,
  hivas,
  kuld,
  letoltes,
  osszesit,
  sorOsszeg,
  szamBe,
  szamSzoveg,
} from "./quote";

type Mentes = "mentve" | "mentes" | "valtozott" | "hiba";
type UgyfelArak = Record<string, { unit_price: number; quote_number: string; date: string | null }>;
type Csoport = { szekcio: string | null; sorok: AjanlatSor[] };

const OSSZESITO_CIMKEK = [
  "A PROJECT TELJES KÖLTSÉGE",
  "STREAMING SZOLGÁLTATÁS KÖLTSÉGE",
  "LED FAL BÉRLÉS KÖLTSÉGE",
  "FOTÓZÁS KÖLTSÉGE",
];

/** Egymás után következő, azonos szekciójú sorok egy csoportban (ahogy az
 * exportban is), plusz a még üres, frissen létrehozott szekciók. */
function csoportok(sorok: AjanlatSor[], uresek: string[]): Csoport[] {
  const ki: Csoport[] = [];
  for (const s of [...sorok].sort((a, b) => a.sort_order - b.sort_order)) {
    const sz = s.section?.trim() || null;
    const utolso = ki[ki.length - 1];
    if (utolso && utolso.szekcio === sz) utolso.sorok.push(s);
    else ki.push({ szekcio: sz, sorok: [s] });
  }
  for (const u of uresek) if (!ki.some((c) => c.szekcio === u)) ki.push({ szekcio: u, sorok: [] });
  return ki;
}

/** Az árajánlat szerkesztője (a fő képernyő): Excel-logikájú táblázat
 * (Tétel/Szolgáltatás | Alkalom | Mennyiség | Egységár | Teljes ár), minden
 * cella helyben szerkeszthető, fogd-és-vidd sorrend szekciókkal, jobbra a
 * katalógus (egy kattintás = új sor), alul élő összesítő és megjegyzés.
 * Mentés: automatikus (késleltetett), optimista - a szerver válasza
 * megerősíti az összegeket. */
export function AjanlatSzerkeszto({
  id,
  canEdit,
  canCreate,
  canDelete,
}: {
  id: number;
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const toast = useToast();
  const [aj, setAj] = useState<Ajanlat | null>(null);
  const [betoltesHiba, setBetoltesHiba] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [mentes, setMentes] = useState<Mentes>("mentve");
  const [celSzekcio, setCelSzekcio] = useState<string | null>(null);
  const [uresSzekciok, setUresSzekciok] = useState<string[]>([]);
  const [katalogus, setKatalogus] = useState<KatalogusTetel[]>([]);
  const [kategoriak, setKategoriak] = useState<Kategoria[]>([]);
  const [megjegyzesek, setMegjegyzesek] = useState<Megjegyzes[]>([]);
  const [arak, setArak] = useState<{ ugyfel: number | null; arak: UgyfelArak }>({ ugyfel: null, arak: {} });
  const [huzott, setHuzott] = useState<number | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);

  const fuggoFej = useRef<Record<string, unknown>>({});
  const fuggoSorok = useRef<Map<number, Record<string, unknown>>>(new Map());
  const idozito = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lanc = useRef<Promise<unknown>>(Promise.resolve());

  const irhat = canEdit;

  // ── Betöltés ──
  useEffect(() => {
    hivas<Ajanlat>(`/${id}`)
      .then((a) => {
        setAj(a);
        const sz = [...a.items].sort((x, y) => x.sort_order - y.sort_order).map((s) => s.section).filter(Boolean);
        setCelSzekcio((sz[sz.length - 1] as string | undefined) ?? null);
      })
      .catch((e: Error) => setBetoltesHiba(e.message));
    hivas<KatalogusTetel[]>("/catalog/items").then(setKatalogus).catch(() => undefined);
    hivas<Kategoria[]>("/catalog/categories").then(setKategoriak).catch(() => undefined);
    hivas<Megjegyzes[]>("/notes").then(setMegjegyzesek).catch(() => undefined);
  }, [id]);

  // Az ügyfélnek legutóbb adott árak (a katalógus-panel tippje).
  const ugyfelId = aj?.client_id ?? null;
  useEffect(() => {
    if (!ugyfelId) return;
    hivas<UgyfelArak>(`/${id}/client-prices`)
      .then((a) => setArak({ ugyfel: ugyfelId, arak: a }))
      .catch(() => undefined);
  }, [id, ugyfelId]);
  const ugyfelArak = ugyfelId && arak.ugyfel === ugyfelId ? arak.arak : {};

  // Nem mentett változás mellett a böngésző figyelmeztet elnavigáláskor.
  useEffect(() => {
    const figyel = (e: BeforeUnloadEvent) => {
      if (mentes === "valtozott" || mentes === "mentes") e.preventDefault();
    };
    window.addEventListener("beforeunload", figyel);
    return () => window.removeEventListener("beforeunload", figyel);
  }, [mentes]);

  // ── Szerver-műveletek sorban (egyszerre egy megy) ──
  const sorba = useCallback(<T,>(fn: () => Promise<T>): Promise<T> => {
    const p = lanc.current.then(fn, fn);
    lanc.current = p.catch(() => undefined);
    return p;
  }, []);

  const ujratolt = useCallback(async () => {
    try {
      setAj(await hivas<Ajanlat>(`/${id}`));
    } catch {
      /* a hibaüzenet már kint van */
    }
  }, [id]);

  const kiir = useCallback(
    () =>
      sorba(async () => {
        if (idozito.current) {
          clearTimeout(idozito.current);
          idozito.current = null;
        }
        const fej = fuggoFej.current;
        const sorok = new Map(fuggoSorok.current);
        if (Object.keys(fej).length === 0 && sorok.size === 0) return;
        fuggoFej.current = {};
        fuggoSorok.current = new Map();
        setMentes("mentes");
        let utolso: Ajanlat | null = null;
        try {
          if (Object.keys(fej).length) utolso = await kuld<Ajanlat>(`/${id}`, "PATCH", fej);
          for (const [sorId, valtozas] of sorok) utolso = await kuld<Ajanlat>(`/${id}/items/${sorId}`, "PATCH", valtozas);
          setHiba(null);
        } catch (e) {
          setHiba(`A mentés nem sikerült: ${(e as Error).message} - a szerveren lévő állapotot töltöttem vissza.`);
          setMentes("hiba");
          await ujratolt();
          return;
        }
        // Ha mentés közben nem gépeltek tovább, a szerver válasza a mérvadó.
        if (utolso && Object.keys(fuggoFej.current).length === 0 && fuggoSorok.current.size === 0) {
          setAj(utolso);
          setMentes("mentve");
        }
      }),
    [id, sorba, ujratolt],
  );

  const utemez = useCallback(() => {
    setMentes("valtozott");
    if (idozito.current) clearTimeout(idozito.current);
    idozito.current = setTimeout(() => void kiir(), 700);
  }, [kiir]);

  /** Szerkezeti művelet (új sor, törlés, sorrend…): előbb kiírja a függő
   * mezőket, aztán a művelet válasza lesz az új állapot. */
  const muvelet = useCallback(
    async (fn: () => Promise<Ajanlat>, siker?: string) => {
      await kiir();
      setFolyamatban(true);
      try {
        const r = await sorba(fn);
        setAj(r);
        setHiba(null);
        setMentes("mentve");
        if (siker) toast(siker);
        return r;
      } catch (e) {
        setHiba((e as Error).message);
        await ujratolt();
        return null;
      } finally {
        setFolyamatban(false);
      }
    },
    [kiir, sorba, toast, ujratolt],
  );

  // ── Helyi (optimista) módosítás ──
  function fejValtozas(valtozas: Partial<Ajanlat>, kuldendo?: Record<string, unknown>) {
    setAj((a) => {
      if (!a) return a;
      const uj = { ...a, ...valtozas };
      return { ...uj, totals: osszesit(uj) };
    });
    Object.assign(fuggoFej.current, kuldendo ?? valtozas);
    utemez();
  }

  function sorValtozas(sorId: number, valtozas: Partial<AjanlatSor>) {
    setAj((a) => {
      if (!a) return a;
      const items = a.items.map((s) => (s.id === sorId ? { ...s, ...valtozas, line_total: sorOsszeg({ ...s, ...valtozas }) } : s));
      return { ...a, items, totals: osszesit({ ...a, items }) };
    });
    fuggoSorok.current.set(sorId, { ...(fuggoSorok.current.get(sorId) ?? {}), ...valtozas });
    utemez();
  }

  // ── Sorrend / szekciók ──
  function rendezettSorok(): AjanlatSor[] {
    return [...(aj?.items ?? [])].sort((a, b) => a.sort_order - b.sort_order);
  }

  function atrendez(uj: { id: number; section: string | null }[]) {
    if (!aj) return;
    // Optimista: azonnal az új sorrend látszik.
    setAj({
      ...aj,
      items: aj.items.map((s) => {
        const i = uj.findIndex((x) => x.id === s.id);
        return { ...s, sort_order: (i + 1) * 10, section: uj[i].section };
      }),
    });
    void muvelet(() => kuld<Ajanlat>(`/${id}/items/reorder`, "PATCH", { items: uj }));
  }

  /** A `mozgatott` sor a `cel` sor elé kerül (annak szekciójába); `cel` null:
   * a `szekcio` végére. */
  function mozgat(mozgatott: number, cel: number | null, szekcio: string | null) {
    const sorok = rendezettSorok().filter((s) => s.id !== mozgatott);
    const elem = { id: mozgatott, section: szekcio };
    let poz: number;
    if (cel !== null) {
      poz = sorok.findIndex((s) => s.id === cel);
    } else {
      const utolso = sorok.map((s) => (s.section?.trim() || null) === szekcio).lastIndexOf(true);
      poz = utolso >= 0 ? utolso + 1 : sorok.length;
    }
    const uj = sorok.map((s) => ({ id: s.id, section: s.section }));
    uj.splice(poz < 0 ? uj.length : poz, 0, elem);
    atrendez(uj);
  }

  function szekcioAtnevez(regi: string | null, uj: string) {
    const nev = uj.trim() || null;
    if (nev === regi) return;
    if (regi && uresSzekciok.includes(regi)) {
      setUresSzekciok((u) => u.map((x) => (x === regi ? (nev ?? x) : x)));
    }
    if (celSzekcio === regi) setCelSzekcio(nev);
    if (!aj?.items.some((s) => (s.section?.trim() || null) === regi)) return;
    atrendez(rendezettSorok().map((s) => ({ id: s.id, section: (s.section?.trim() || null) === regi ? nev : s.section })));
  }

  async function ujSzekcio() {
    const nev = window.prompt("Az új szekció neve (pl. „Eszközök” vagy „2. nap”):")?.trim();
    if (!nev) return;
    setUresSzekciok((u) => (u.includes(nev) ? u : [...u, nev]));
    setCelSzekcio(nev);
  }

  // ── Műveletek ──
  const katalogusbol = (t: KatalogusTetel) =>
    muvelet(() => kuld<Ajanlat>(`/${id}/items/from-catalog`, "POST", { catalog_item_id: t.id, section: celSzekcio }));

  const ujSor = (szekcio: string | null) =>
    muvelet(() => kuld<Ajanlat>(`/${id}/items`, "POST", { section: szekcio, name: "", unit_price: 0 }));

  async function sablonkent() {
    if (!aj) return;
    const nev = window.prompt("A sablon neve:", aj.project_name || aj.template_name || "")?.trim();
    if (!nev) return;
    await kiir();
    try {
      await kuld(`/templates/from-quote/${id}`, "POST", { name: nev });
      toast(`Sablon mentve: ${nev}`);
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  async function uj(ut: "duplicate" | "new-version") {
    await kiir();
    try {
      const r = await kuld<Ajanlat>(`/${id}/${ut}`, "POST");
      toast(ut === "duplicate" ? `Új variáns: ${r.number}` : `Új verzió: v${r.version}`);
      router.push(`/arajanlatok/${r.id}`);
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  async function exportal(tipus: "xlsx" | "pdf") {
    await kiir();
    try {
      await letoltes(`/${id}/export.${tipus}`, `arajanlat.${tipus}`);
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  async function torol() {
    if (!aj) return;
    if (!(await confirm(`Biztosan törlöd ezt az árajánlatot: ${aj.number}${aj.version > 1 ? ` v${aj.version}` : ""}?`))) return;
    try {
      await kuld(`/${id}`, "DELETE");
      router.push("/arajanlatok");
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  const csop = useMemo(() => csoportok(aj?.items ?? [], uresSzekciok), [aj?.items, uresSzekciok]);
  const szekcioNevek = useMemo(
    () => [...new Set(csop.map((c) => c.szekcio).filter((x): x is string => !!x))],
    [csop],
  );

  if (betoltesHiba) {
    return <p className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{betoltesHiba}</p>;
  }
  if (!aj) return <p className="text-[13px] text-text-muted">Betöltés…</p>;

  const o = aj.totals;
  const alkalomFelirat = aj.occasions_label || "Alkalom";

  return (
    <div className="flex flex-col gap-4">
      {/* Felső sáv */}
      <div className="flex flex-wrap items-center gap-2">
        <Link href="/arajanlatok" className="btn btn-ghost flex items-center gap-1 text-[13px]">
          <ArrowLeft size={14} /> Ajánlatok
        </Link>
        <span className="font-mono text-[15px] font-semibold text-text-primary">{aj.number}</span>
        {aj.version > 1 && <StatusBadge label={`v${aj.version}`} tone="accent" />}
        <select
          value={aj.status}
          disabled={!irhat}
          onChange={(e) => fejValtozas({ status: e.target.value })}
          className="field w-auto py-1 text-[13px]"
          aria-label="Státusz"
        >
          {STATUSZOK.map((x) => (
            <option key={x.ertek} value={x.ertek}>
              {x.cimke}
            </option>
          ))}
        </select>
        <div className="flex overflow-hidden rounded-[var(--radius)] border border-border">
          {MARKAK.map((m) => (
            <button
              key={m.ertek}
              type="button"
              disabled={!irhat || folyamatban}
              onClick={() => m.ertek !== aj.brand && void muvelet(() => kuld<Ajanlat>(`/${id}`, "PATCH", { brand: m.ertek }))}
              className={`px-2.5 py-1 text-[12.5px] ${aj.brand === m.ertek ? "bg-surface-3 text-text-primary" : "text-text-muted hover:bg-surface-2"}`}
            >
              {m.cimke}
            </button>
          ))}
        </div>
        <MentesJelzo allapot={mentes} />
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          {canCreate && (
            <>
              <button type="button" className="btn btn-ghost flex items-center gap-1 text-[12.5px]" onClick={() => uj("duplicate")} title="Új ajánlat (új számmal) ugyanezekkel a sorokkal - pl. 2 vs. 3 kamerás">
                <Copy size={13} /> Duplikálás variánsként
              </button>
              <button type="button" className="btn btn-ghost flex items-center gap-1 text-[12.5px]" onClick={() => uj("new-version")} title="Ugyanazzal a számmal, eggyel nagyobb verzió">
                <GitBranch size={13} /> Új verzió
              </button>
            </>
          )}
          {irhat && (
            <button type="button" className="btn btn-ghost flex items-center gap-1 text-[12.5px]" onClick={sablonkent}>
              <Save size={13} /> Mentés sablonként
            </button>
          )}
          <button type="button" className="btn flex items-center gap-1 text-[12.5px]" onClick={() => exportal("xlsx")}>
            <FileSpreadsheet size={13} /> XLSX
          </button>
          <button type="button" className="btn flex items-center gap-1 text-[12.5px]" onClick={() => exportal("pdf")}>
            <FileText size={13} /> PDF
          </button>
          {canDelete && (
            <button type="button" className="btn btn-ghost p-1.5 text-text-muted hover:text-text-danger" onClick={torol} title="Árajánlat törlése" aria-label="Árajánlat törlése">
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {(aj.versions.length > 1 || aj.parent) && (
        <p className="-mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-text-muted">
          {aj.versions.length > 1 && (
            <>
              Verziók:
              {aj.versions.map((v) =>
                v.id === aj.id ? (
                  <span key={v.id} className="font-medium text-text-primary">v{v.version}</span>
                ) : (
                  <Link key={v.id} href={`/arajanlatok/${v.id}`} className="text-text-accent hover:underline">
                    v{v.version}
                  </Link>
                ),
              )}
            </>
          )}
          {aj.parent && aj.parent.number !== aj.number && (
            <span>
              · variáns ebből:{" "}
              <Link href={`/arajanlatok/${aj.parent.id}`} className="text-text-accent hover:underline">
                {aj.parent.number}
                {aj.parent.version > 1 ? ` v${aj.parent.version}` : ""}
              </Link>
            </span>
          )}
          {aj.template_name && <span>· sablon: {aj.template_name}</span>}
        </p>
      )}

      {hiba && (
        <p className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">
          {hiba}{" "}
          <button type="button" className="underline" onClick={() => setHiba(null)}>
            Bezár
          </button>
        </p>
      )}

      {/* Fejadatok */}
      <div className="grid gap-3 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4 md:grid-cols-2 xl:grid-cols-4">
        <UgyfelValaszto
          ertek={aj.client}
          tiltva={!irhat}
          onValaszt={(u) => fejValtozas({ client_id: u?.id ?? null, client: u ? { id: u.id, nev: u.nev } : null }, { client_id: u?.id ?? null })}
        />
        <Mezo cimke="Projekt neve" className="xl:col-span-2">
          <input className="field" disabled={!irhat} value={aj.project_name} onChange={(e) => fejValtozas({ project_name: e.target.value })} />
        </Mezo>
        <Mezo cimke="Helyszín">
          <input className="field" disabled={!irhat} value={aj.location ?? ""} onChange={(e) => fejValtozas({ location: e.target.value || null })} />
        </Mezo>
        <Mezo cimke="Dátum (-tól / -ig)">
          <div className="flex gap-1.5">
            <input type="date" className="field min-w-0 flex-1" disabled={!irhat} value={aj.event_date_from ?? ""} onChange={(e) => fejValtozas({ event_date_from: e.target.value || null })} />
            <input type="date" className="field min-w-0 flex-1" disabled={!irhat} value={aj.event_date_to ?? ""} min={aj.event_date_from ?? undefined} onChange={(e) => fejValtozas({ event_date_to: e.target.value || null })} />
          </div>
        </Mezo>
        <Mezo cimke="Árazás">
          <div className="flex items-center gap-1.5">
            <select className="field w-auto" disabled={!irhat} value={aj.pricing_mode} onChange={(e) => fejValtozas({ pricing_mode: e.target.value as Ajanlat["pricing_mode"] })}>
              <option value="one_off">Egyszeri</option>
              <option value="monthly">Havidíjas</option>
            </select>
            {aj.pricing_mode === "monthly" && (
              <>
                <SzamMezo ertek={aj.months} tiltva={!irhat} egesz min={1} onErtek={(v) => fejValtozas({ months: Math.max(1, Math.round(v)) })} className="w-16" />
                <span className="text-[12px] text-text-muted">hónap</span>
              </>
            )}
          </div>
        </Mezo>
        <Mezo cimke="Összesítő sor címkéje">
          <input className="field" list="aj-osszesito-cimkek" disabled={!irhat || aj.pricing_mode === "monthly"} value={aj.pricing_mode === "monthly" ? `A PROJECT TELJES KÖLTSÉGE ${aj.months} HÓNAPRA` : aj.summary_label ?? ""} onChange={(e) => fejValtozas({ summary_label: e.target.value })} />
          <datalist id="aj-osszesito-cimkek">
            {OSSZESITO_CIMKEK.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </Mezo>
        <Mezo cimke="Belső megjegyzés (nem kerül az ajánlatra)">
          <input className="field" disabled={!irhat} value={aj.internal_note ?? ""} onChange={(e) => fejValtozas({ internal_note: e.target.value || null })} />
        </Mezo>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        {/* Tételek */}
        <div className="min-w-0 rounded-[var(--radius-lg)] border border-border bg-surface-2">
          <div className="overflow-x-auto">
            <div className="min-w-[760px]">
              <div className="grid grid-cols-[22px_minmax(0,1fr)_78px_84px_118px_118px_34px] items-center gap-2 border-b border-border bg-surface-3 px-3 py-2 text-[12px] font-medium text-text-secondary">
                <span />
                <span>Tétel/Szolgáltatás</span>
                <span className="text-right">{alkalomFelirat}</span>
                <span className="text-right">Mennyiség</span>
                <span className="text-right">Egységár</span>
                <span className="text-right">{aj.pricing_mode === "monthly" ? `Teljes ár (${aj.months} hó)` : "Teljes ár"}</span>
                <span />
              </div>
              {csop.length === 0 && (
                <p className="px-4 py-6 text-center text-[13px] text-text-muted">
                  Még nincs tétel. Kattints a jobb oldali katalógus egy tételére, vagy adj hozzá egyedi sort.
                </p>
              )}
              {csop.map((c, ci) => (
                <div key={`${c.szekcio ?? "-"}-${ci}`}>
                  <SzekcioFej
                    nev={c.szekcio}
                    osszeg={c.sorok.filter((x) => !x.is_optional).reduce((t, x) => t + sorOsszeg(x), 0)}
                    cel={celSzekcio === c.szekcio}
                    irhat={irhat}
                    lathato={c.szekcio !== null || csop.length > 1}
                    onCel={() => setCelSzekcio(c.szekcio)}
                    onAtnevez={(nev) => szekcioAtnevez(c.szekcio, nev)}
                    onDrop={() => huzott !== null && mozgat(huzott, c.sorok[0]?.id ?? null, c.szekcio)}
                  />
                  {c.sorok.map((sor) => (
                    <SorKomponens
                      key={sor.id}
                      sor={sor}
                      irhat={irhat}
                      katalogus={katalogus}
                      szekciok={szekcioNevek}
                      huzott={huzott}
                      onHuzas={setHuzott}
                      onDrop={(celId) => huzott !== null && huzott !== celId && mozgat(huzott, celId, c.szekcio)}
                      onValtozas={(v) => sorValtozas(sor.id, v)}
                      onDuplikal={() => muvelet(() => kuld<Ajanlat>(`/${id}/items/${sor.id}/duplicate`, "POST"))}
                      onTorol={() => muvelet(() => kuld<Ajanlat>(`/${id}/items/${sor.id}`, "DELETE"))}
                      onKatalogusar={() => muvelet(() => kuld<Ajanlat>(`/${id}/refresh-prices`, "POST", { item_ids: [sor.id] }), "Frissítve a katalógusárra.")}
                      onCsere={(t) => muvelet(() => kuld<Ajanlat>(`/${id}/items/${sor.id}`, "PATCH", { catalog_item_id: t.id }))}
                      onAthelyez={(sz) => mozgat(sor.id, null, sz)}
                    />
                  ))}
                  {irhat && (
                    <div
                      className="flex items-center gap-3 border-b border-border px-3 py-1.5 pl-9"
                      onDragOver={(e) => huzott !== null && e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        if (huzott !== null) mozgat(huzott, null, c.szekcio);
                        setHuzott(null);
                      }}
                    >
                      <button type="button" disabled={folyamatban} onClick={() => ujSor(c.szekcio)} className="flex items-center gap-1 text-[12px] text-text-muted hover:text-text-accent disabled:opacity-50">
                        <Plus size={12} /> Egyedi sor{c.szekcio ? ` ide (${c.szekcio})` : ""}
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {irhat && (
                <div className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                  <button type="button" onClick={ujSzekcio} className="btn btn-ghost flex items-center gap-1 text-[12.5px]">
                    <Plus size={13} /> Új szekció
                  </button>
                  {csop.length === 0 && (
                    <button type="button" onClick={() => ujSor(null)} className="btn btn-ghost flex items-center gap-1 text-[12.5px]">
                      <Plus size={13} /> Egyedi sor
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Összesítő */}
          <div className="border-t border-border px-4 py-3">
            <div className="ml-auto flex max-w-[460px] flex-col gap-1.5 text-[13px]">
              <OsszegSor cimke="Részösszeg" ertek={ft(o.reszosszeg)} />
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 text-text-secondary">
                  Kedvezmény
                  <SzamMezo ertek={aj.discount_percent} tiltva={!irhat} min={0} max={100} onErtek={(v) => fejValtozas({ discount_percent: Math.min(100, Math.max(0, v)) })} className="w-14 py-0.5 text-[12.5px]" />
                  % +
                  <SzamMezo ertek={aj.discount_amount} tiltva={!irhat} egesz min={0} penz onErtek={(v) => fejValtozas({ discount_amount: Math.max(0, Math.round(v)) })} className="w-24 py-0.5 text-[12.5px]" />
                </span>
                <span className="font-mono text-text-secondary">{o.kedvezmeny ? `−${ft(o.kedvezmeny)}` : "–"}</span>
              </div>
              <div className="flex items-baseline justify-between gap-2 border-t border-border pt-1.5">
                <span className="font-semibold text-text-primary">
                  {aj.pricing_mode === "monthly" ? `A PROJECT TELJES KÖLTSÉGE ${aj.months} HÓNAPRA` : aj.summary_label || "A PROJECT TELJES KÖLTSÉGE"}
                  <span className="ml-1.5 text-[11px] font-normal text-text-muted">nettó</span>
                </span>
                <span className="font-mono text-[15px] font-semibold text-text-primary">{ft(o.netto)}</span>
              </div>
              {aj.pricing_mode === "monthly" && <OsszegSor cimke="A PROJECT HAVIDÍJA" ertek={ft(o.havidij)} kiemelt />}
              <div className="flex items-center justify-between gap-2 text-text-muted">
                <span className="flex items-center gap-1.5">
                  ÁFA
                  <SzamMezo ertek={aj.vat_percent} tiltva={!irhat} min={0} max={100} onErtek={(v) => fejValtozas({ vat_percent: Math.min(100, Math.max(0, v)) })} className="w-14 py-0.5 text-[12.5px]" />%
                </span>
                <span className="font-mono">{ft(o.afa)}</span>
              </div>
              <OsszegSor cimke="Bruttó" ertek={ft(o.brutto)} halvany />
              {o.opcionalis > 0 && <OsszegSor cimke="Opcionális tételek (nem része)" ertek={ft(o.opcionalis)} halvany />}
            </div>
          </div>
        </div>

        {/* Katalógus-panel */}
        <KatalogusPanel
          tetelek={katalogus}
          kategoriak={kategoriak}
          ugyfelArak={ugyfelArak}
          celSzekcio={celSzekcio}
          szekciok={szekcioNevek}
          onCel={setCelSzekcio}
          tiltva={!irhat || folyamatban}
          onValaszt={katalogusbol}
        />
      </div>

      {/* Megjegyzés */}
      <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-[13px] font-medium text-text-primary">Megjegyzés (az ajánlat alján)</p>
          {irhat && megjegyzesek.length > 0 && (
            <select
              className="field w-auto py-1 text-[12.5px]"
              value=""
              onChange={async (e) => {
                const m = megjegyzesek.find((x) => String(x.id) === e.target.value);
                if (!m) return;
                if (aj.note_text?.trim() && aj.note_text !== m.text && !(await confirm(`Lecseréled a megjegyzést erre: „${m.name}”?`))) return;
                fejValtozas({ note_text: m.text });
              }}
              aria-label="Megjegyzés-sablon"
            >
              <option value="">Megjegyzés-sablon betöltése…</option>
              {megjegyzesek.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          )}
        </div>
        <AutoTextarea
          value={aj.note_text ?? ""}
          disabled={!irhat}
          onChange={(v) => fejValtozas({ note_text: v || null })}
          className="field min-h-[90px] w-full text-[12.5px] leading-relaxed"
        />
      </div>
    </div>
  );
}

// ── Kis építőelemek ─────────────────────────────────────────────────────────

function Mezo({ cimke, className = "", children }: { cimke: string; className?: string; children: ReactNode }) {
  return (
    <label className={`flex flex-col gap-1 text-[12px] text-text-muted ${className}`}>
      {cimke}
      {children}
    </label>
  );
}

function OsszegSor({ cimke, ertek, kiemelt, halvany }: { cimke: string; ertek: string; kiemelt?: boolean; halvany?: boolean }) {
  return (
    <div className={`flex items-baseline justify-between gap-2 ${halvany ? "text-text-muted" : kiemelt ? "font-semibold text-text-primary" : "text-text-secondary"}`}>
      <span>{cimke}</span>
      <span className="font-mono">{ertek}</span>
    </div>
  );
}

function MentesJelzo({ allapot }: { allapot: Mentes }) {
  const szoveg = { mentve: "Mentve", mentes: "Mentés…", valtozott: "Változott…", hiba: "Mentési hiba" }[allapot];
  const szin = allapot === "hiba" ? "text-text-danger" : allapot === "mentve" ? "text-text-muted" : "text-text-warning";
  return <span className={`text-[12px] ${szin}`}>{szoveg}</span>;
}

/** Számmező: gépelés közben a saját szövegét tartja (a „1,” félkész érték se
 * vesszen el), és minden értelmezhető állapotot azonnal továbbad. */
function SzamMezo({
  ertek,
  onErtek,
  tiltva,
  className = "",
  egesz,
  penz,
  min,
  max,
}: {
  ertek: number;
  onErtek: (v: number) => void;
  tiltva?: boolean;
  className?: string;
  egesz?: boolean;
  penz?: boolean;
  min?: number;
  max?: number;
}) {
  const [szoveg, setSzoveg] = useState<string | null>(null);
  const megjelenitett = szoveg ?? (penz ? Math.round(ertek).toLocaleString("hu-HU") : szamSzoveg(ertek));
  return (
    <input
      className={`field text-right tabular-nums ${className}`}
      inputMode={egesz ? "numeric" : "decimal"}
      disabled={tiltva}
      value={megjelenitett}
      onFocus={(e) => {
        setSzoveg(penz ? String(Math.round(ertek)) : szamSzoveg(ertek));
        requestAnimationFrame(() => e.target.select());
      }}
      onBlur={() => setSzoveg(null)}
      onChange={(e) => {
        setSzoveg(e.target.value);
        const v = szamBe(e.target.value);
        if (v === null) return;
        if ((min !== undefined && v < min) || (max !== undefined && v > max)) return;
        onErtek(egesz ? Math.round(v) : v);
      }}
    />
  );
}

function AutoTextarea({
  value,
  onChange,
  className,
  disabled,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
  disabled?: boolean;
  placeholder?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  return (
    <textarea
      ref={ref}
      rows={1}
      value={value}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className={`resize-none overflow-hidden ${className ?? ""}`}
    />
  );
}

function SzekcioFej({
  nev,
  osszeg,
  cel,
  irhat,
  lathato,
  onCel,
  onAtnevez,
  onDrop,
}: {
  nev: string | null;
  osszeg: number;
  cel: boolean;
  irhat: boolean;
  lathato: boolean;
  onCel: () => void;
  onAtnevez: (nev: string) => void;
  onDrop: () => void;
}) {
  const [szoveg, setSzoveg] = useState(nev ?? "");
  const [elozo, setElozo] = useState(nev);
  if (nev !== elozo) {
    setElozo(nev);
    setSzoveg(nev ?? "");
  }
  if (!lathato) return null;
  return (
    <div
      onClick={onCel}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        onDrop();
      }}
      className={`flex cursor-pointer items-center gap-2 border-b border-l-2 border-border bg-surface-3/60 px-3 py-1.5 ${cel ? "border-l-text-accent" : "border-l-transparent"}`}
      title="Kattints: ide kerülnek a katalógusból hozzáadott tételek"
    >
      <input
        value={szoveg}
        disabled={!irhat}
        placeholder="(szekció nélkül)"
        onClick={(e) => e.stopPropagation()}
        onFocus={onCel}
        onChange={(e) => setSzoveg(e.target.value)}
        onBlur={() => onAtnevez(szoveg)}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        className="min-w-0 flex-1 bg-transparent text-[13px] font-semibold text-text-primary outline-none placeholder:font-normal placeholder:text-text-muted"
        aria-label="Szekció neve"
      />
      {cel && <span className="shrink-0 text-[11px] text-text-accent">ide kerül az új tétel</span>}
      <span className="shrink-0 font-mono text-[12px] text-text-muted">{ft(osszeg)}</span>
    </div>
  );
}

function SorKomponens({
  sor,
  irhat,
  katalogus,
  szekciok,
  huzott,
  onHuzas,
  onDrop,
  onValtozas,
  onDuplikal,
  onTorol,
  onKatalogusar,
  onCsere,
  onAthelyez,
}: {
  sor: AjanlatSor;
  irhat: boolean;
  katalogus: KatalogusTetel[];
  szekciok: string[];
  huzott: number | null;
  onHuzas: (id: number | null) => void;
  onDrop: (celId: number) => void;
  onValtozas: (v: Partial<AjanlatSor>) => void;
  onDuplikal: () => void;
  onTorol: () => void;
  onKatalogusar: () => void;
  onCsere: (t: KatalogusTetel) => void;
  onAthelyez: (szekcio: string | null) => void;
}) {
  const [menu, setMenu] = useState(false);
  const [kedvNyitva, setKedvNyitva] = useState(sor.line_discount_percent > 0);
  const [folotte, setFolotte] = useState(false);
  const eltero = sor.catalog_price !== null && sor.catalog_price !== sor.unit_price;
  const variansok = sor.variant_tags.length
    ? katalogus.filter((t) => t.id !== sor.catalog_item_id && t.tags.some((x) => sor.variant_tags.includes(x)))
    : [];

  return (
    <div
      onDragOver={(e) => {
        if (huzott === null || huzott === sor.id) return;
        e.preventDefault();
        setFolotte(true);
      }}
      onDragLeave={() => setFolotte(false)}
      onDrop={(e) => {
        e.preventDefault();
        setFolotte(false);
        onDrop(sor.id);
        onHuzas(null);
      }}
      className={`group relative grid grid-cols-[22px_minmax(0,1fr)_78px_84px_118px_118px_34px] items-start gap-2 border-b border-border px-3 py-2 ${
        sor.is_optional ? "opacity-60" : ""
      } ${folotte ? "shadow-[inset_0_2px_0_var(--text-accent)]" : ""} ${huzott === sor.id ? "opacity-40" : ""}`}
    >
      <span
        draggable={irhat}
        onDragStart={(e) => {
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", String(sor.id));
          onHuzas(sor.id);
        }}
        onDragEnd={() => onHuzas(null)}
        className={`mt-1.5 text-text-muted ${irhat ? "cursor-grab active:cursor-grabbing" : "opacity-30"}`}
        title="Húzd a sorrendhez"
      >
        <GripVertical size={14} />
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <input
            value={sor.name}
            disabled={!irhat}
            placeholder="Tétel megnevezése"
            onChange={(e) => onValtozas({ name: e.target.value })}
            className="min-w-0 flex-1 rounded bg-transparent px-1 py-0.5 text-[13.5px] font-medium text-text-primary outline-none hover:bg-surface-3 focus:bg-surface-3"
          />
          {sor.is_optional && <span className="shrink-0 rounded bg-bg-blue px-1.5 py-px text-[10.5px] text-text-blue">+ opció</span>}
          {sor.unit && <span className="shrink-0 text-[11px] text-text-muted">{egysegCimke(sor.unit)}</span>}
        </div>
        <AutoTextarea
          value={sor.description ?? ""}
          disabled={!irhat}
          placeholder={irhat ? "+ leírás" : ""}
          onChange={(v) => onValtozas({ description: v || null })}
          className="mt-0.5 block w-full rounded bg-transparent px-1 py-0.5 text-[12.5px] leading-snug text-text-secondary outline-none placeholder:text-text-muted/60 hover:bg-surface-3 focus:bg-surface-3"
        />
      </div>
      <SzamMezo ertek={sor.occasions} tiltva={!irhat} min={0} onErtek={(v) => onValtozas({ occasions: v })} className="py-1 text-[13px]" />
      <SzamMezo ertek={sor.quantity} tiltva={!irhat} min={0} onErtek={(v) => onValtozas({ quantity: v })} className="py-1 text-[13px]" />
      <div className="flex flex-col items-end gap-0.5">
        <SzamMezo ertek={sor.unit_price} tiltva={!irhat} egesz penz min={0} onErtek={(v) => onValtozas({ unit_price: v })} className="w-full py-1 text-[13px]" />
        {eltero && (
          <button
            type="button"
            disabled={!irhat}
            onClick={onKatalogusar}
            className="text-right text-[11px] leading-tight text-text-warning hover:underline disabled:no-underline"
            title="A katalógusár azóta változott (vagy átírtad) - kattintásra erre áll"
          >
            Katalógusár: {ft(sor.catalog_price)} – frissít?
          </button>
        )}
        {kedvNyitva && (
          <span className="flex items-center gap-1 text-[11px] text-text-muted">
            −
            <SzamMezo ertek={sor.line_discount_percent} tiltva={!irhat} min={0} max={100} onErtek={(v) => onValtozas({ line_discount_percent: v })} className="w-12 py-0 text-[11.5px]" />%
          </span>
        )}
      </div>
      <div className="pt-1 text-right font-mono text-[13px] tabular-nums text-text-primary">
        {ft(sorOsszeg(sor))}
        {sor.line_discount_percent > 0 && <div className="text-[10.5px] text-text-muted">−{szamSzoveg(sor.line_discount_percent)}%</div>}
      </div>
      <div className="relative">
        {irhat && (
          <button type="button" onClick={() => setMenu((m) => !m)} className="rounded p-1 text-text-muted hover:bg-surface-3" aria-label="Sor műveletei">
            <MoreHorizontal size={15} />
          </button>
        )}
        {menu && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setMenu(false)} />
            <div className="absolute right-0 top-7 z-40 w-60 rounded-[var(--radius)] border border-border bg-surface-1 py-1 text-[13px] shadow-lg">
              <MenuPont onClick={() => (setMenu(false), onValtozas({ is_optional: !sor.is_optional }))}>
                {sor.is_optional ? "Beszámít a végösszegbe" : "Opcionálissá tétel"}
              </MenuPont>
              <MenuPont onClick={() => (setMenu(false), onDuplikal())}>Duplikálás</MenuPont>
              <MenuPont
                onClick={() => {
                  setMenu(false);
                  if (kedvNyitva && sor.line_discount_percent > 0) onValtozas({ line_discount_percent: 0 });
                  setKedvNyitva((k) => !k);
                }}
              >
                {kedvNyitva ? "Sorkedvezmény törlése" : "Sorkedvezmény…"}
              </MenuPont>
              {sor.catalog_item_id && (
                <MenuPont onClick={() => (setMenu(false), onKatalogusar())}>Vissza a katalógusárra</MenuPont>
              )}
              {variansok.length > 0 && (
                <>
                  <p className="px-3 pb-0.5 pt-1.5 text-[11px] uppercase tracking-wide text-text-muted">Csere erre</p>
                  {variansok.map((t) => (
                    <MenuPont key={t.id} onClick={() => (setMenu(false), onCsere(t))}>
                      <span className="flex justify-between gap-2">
                        <span className="truncate">{t.name}</span>
                        <span className="shrink-0 text-text-muted">{ft(t.base_price)}</span>
                      </span>
                    </MenuPont>
                  ))}
                </>
              )}
              {szekciok.length > 0 && (
                <>
                  <p className="px-3 pb-0.5 pt-1.5 text-[11px] uppercase tracking-wide text-text-muted">Áthelyezés</p>
                  {szekciok
                    .filter((x) => x !== (sor.section?.trim() || null))
                    .map((x) => (
                      <MenuPont key={x} onClick={() => (setMenu(false), onAthelyez(x))}>
                        → {x}
                      </MenuPont>
                    ))}
                </>
              )}
              <div className="my-1 border-t border-border" />
              <MenuPont veszelyes onClick={() => (setMenu(false), onTorol())}>
                <span className="flex items-center gap-1.5">
                  <Trash2 size={13} /> Törlés
                </span>
              </MenuPont>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function MenuPont({ onClick, children, veszelyes }: { onClick: () => void; children: ReactNode; veszelyes?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full px-3 py-1.5 text-left hover:bg-surface-3 ${veszelyes ? "text-text-danger" : "text-text-primary"}`}
    >
      {children}
    </button>
  );
}

function KatalogusPanel({
  tetelek,
  kategoriak,
  ugyfelArak,
  celSzekcio,
  szekciok,
  onCel,
  tiltva,
  onValaszt,
}: {
  tetelek: KatalogusTetel[];
  kategoriak: Kategoria[];
  ugyfelArak: UgyfelArak;
  celSzekcio: string | null;
  szekciok: string[];
  onCel: (sz: string | null) => void;
  tiltva: boolean;
  onValaszt: (t: KatalogusTetel) => void;
}) {
  const [kereses, setKereses] = useState("");
  const [kat, setKat] = useState<number | null>(null);
  const k = kereses.trim().toLowerCase();
  const lathato = tetelek.filter(
    (t) =>
      (kat === null || t.category_id === kat) &&
      (!k || t.name.toLowerCase().includes(k) || (t.default_description ?? "").toLowerCase().includes(k)),
  );

  return (
    <aside className="flex max-h-[calc(100vh-120px)] flex-col rounded-[var(--radius-lg)] border border-border bg-surface-2 xl:sticky xl:top-4">
      <div className="border-b border-border p-3">
        <p className="mb-2 text-[13px] font-medium text-text-primary">Katalógus</p>
        <div className="relative">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input className="field w-full pl-7" placeholder="Keresés…" value={kereses} onChange={(e) => setKereses(e.target.value)} />
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          <Chip aktiv={kat === null} onClick={() => setKat(null)}>
            Mind
          </Chip>
          {kategoriak.map((c) => (
            <Chip key={c.id} aktiv={kat === c.id} onClick={() => setKat(c.id)}>
              {c.name}
            </Chip>
          ))}
        </div>
        <label className="mt-2 flex items-center gap-1.5 text-[12px] text-text-muted">
          Ide kerül:
          <select className="field min-w-0 flex-1 py-0.5 text-[12px]" value={celSzekcio ?? ""} onChange={(e) => onCel(e.target.value || null)}>
            <option value="">(szekció nélkül)</option>
            {szekciok.map((sz) => (
              <option key={sz} value={sz}>
                {sz}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="min-h-[160px] flex-1 overflow-y-auto">
        {tetelek.length === 0 && (
          <p className="p-3 text-[12.5px] text-text-muted">A katalógus üres - a Katalógus fülön tölthetők be az alapadatok.</p>
        )}
        {lathato.map((t) => {
          const tipp = ugyfelArak[String(t.id)];
          const sav = t.price_min !== null && t.price_max !== null ? `Ársáv: ${ft(t.price_min)} – ${ft(t.price_max)}` : "";
          const cim = [sav, tipp ? `Legutóbb ennek az ügyfélnek: ${ft(tipp.unit_price)} (${tipp.quote_number})` : "", t.default_description ?? ""]
            .filter(Boolean)
            .join("\n");
          return (
            <button
              key={t.id}
              type="button"
              disabled={tiltva}
              onClick={() => onValaszt(t)}
              title={cim || undefined}
              className="group flex w-full items-start justify-between gap-2 border-b border-border/60 px-3 py-2 text-left hover:bg-surface-3 disabled:opacity-60"
            >
              <span className="min-w-0">
                <span className="block text-[13px] text-text-primary">{t.name}</span>
                <span className="block text-[11px] text-text-muted">
                  {egysegCimke(t.unit)}
                  {sav && <span className="hidden group-hover:inline"> · {sav}</span>}
                </span>
                {tipp && tipp.unit_price !== t.base_price && (
                  <span className="block text-[11px] text-text-accent">legutóbb neki: {ft(tipp.unit_price)}</span>
                )}
              </span>
              <span className="shrink-0 font-mono text-[12.5px] text-text-secondary">{ft(t.base_price)}</span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

function Chip({ aktiv, onClick, children }: { aktiv: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-2 py-0.5 text-[11.5px] ${aktiv ? "border-text-accent bg-bg-accent text-text-accent" : "border-border text-text-secondary hover:bg-surface-3"}`}
    >
      {children}
    </button>
  );
}
