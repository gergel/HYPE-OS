"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, ExternalLink, Plus, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { LinkeltSzoveg } from "@/components/LinkeltSzoveg";
import { elsoLink } from "@/lib/linkek";
import { KotelezettsegUrlapModal } from "@/components/kotelezettseg/KotelezettsegKezelo";
import { PapirFeltoltes } from "@/components/kotelezettseg/PapirFeltoltes";
import { authFetch } from "@/lib/authFetch";
import { huDatum } from "@/lib/huDate";
import { formatHuf } from "@/lib/penz";
import type { Kotelezettseg } from "@/lib/api";

type Ciklus = "havi" | "eves" | "egyszeri";

/** A szekciók sorrendje (a felhasználó kérése: a havi és az éves előfizetések
 * külön szekcióban). A szekció fejléce a hozzá illő összeget mutatja: a havi
 * előfizetéseknél a havi, az éveseknél az éves költséget. */
const SZEKCIOK: { kulcs: Ciklus; cim: string; pont: string; osszegCimke: string; osszeg: (k: Kotelezettseg) => number }[] = [
  { kulcs: "havi", cim: "Havi előfizetések", pont: "bg-text-accent", osszegCimke: "havonta", osszeg: (k) => k.huf_becsles_honap ?? 0 },
  { kulcs: "eves", cim: "Éves előfizetések", pont: "bg-text-success", osszegCimke: "évente", osszeg: (k) => k.huf_becsles_ev ?? 0 },
  { kulcs: "egyszeri", cim: "Egyszeri / határozott idejű", pont: "bg-text-muted", osszegCimke: "összesen", osszeg: (k) => k.huf_becsles_ev ?? 0 },
];

function penzzel(osszeg: number | null, penznem: string): string {
  if (osszeg == null) return "–";
  if (penznem === "HUF") return formatHuf(osszeg);
  return `${osszeg.toLocaleString("hu-HU")} ${penznem}`;
}

function napKulonbseg(ma: string, nap: string): number {
  return Math.round((new Date(`${nap}T00:00:00`).getTime() - new Date(`${ma}T00:00:00`).getTime()) / 86_400_000);
}

/** E-REZSI: az előfizetések (a felhasználó kérése, 2026-10: olyan szép és
 * átlátható, mint a TO-DO). Felül az összesítő (havi / éves előfizetések
 * száma és költsége - kattintva szűr), alatta kereső és szűrők, az
 * előfizetések pedig CIKLUS szerint külön, összecsukható szekciókban (havi,
 * éves, egyszeri). A lejárat dátuma nem kötelező - megadva csak tájékoztat
 * (lejárat-figyelés az előfizetéseknél nincs, lásd backend
 * services/kotelezettseg.py). A felvitel/szerkesztés a közös űrlapon megy
 * (KotelezettsegUrlapModal). */
export function ERezsiLista({
  kotelezettsegek,
  emberek,
  canEdit,
  canCreate,
  canDelete,
  ma,
}: {
  kotelezettsegek: Kotelezettseg[];
  emberek: { id: number; full_name: string }[];
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
  /** A mai nap (YYYY-MM-DD) - a szerver adja. */
  ma: string;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [tab, setTab] = useState<"aktiv" | "inaktiv">("aktiv");
  const [ciklusSzuro, setCiklusSzuro] = useState<Ciklus | "">("");
  const [q, setQ] = useState("");
  const [felelos, setFelelos] = useState("");
  const [fizetesiMod, setFizetesiMod] = useState("");
  const [csukott, setCsukott] = useState<Set<string>>(new Set());
  const [nyitott, setNyitott] = useState<number | null>(null);
  const [urlapKezdo, setUrlapKezdo] = useState<Kotelezettseg | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);

  const aktivak = kotelezettsegek.filter((k) => k.aktiv);
  const inaktivak = kotelezettsegek.filter((k) => !k.aktiv);
  const ciklusa = (k: Kotelezettseg): Ciklus => (k.ciklus === "havi" || k.ciklus === "eves" ? k.ciklus : "egyszeri");
  const havi = aktivak.filter((k) => ciklusa(k) === "havi");
  const eves = aktivak.filter((k) => ciklusa(k) === "eves");
  const haviKoltseg = aktivak.reduce((s, k) => s + (k.huf_becsles_honap ?? 0), 0);
  const evesKoltseg = aktivak.reduce((s, k) => s + (k.huf_becsles_ev ?? 0), 0);

  const felelosValasztek = useMemo(() => {
    const idk = new Set(kotelezettsegek.map((k) => k.felelos_id).filter((x): x is number => x != null));
    return emberek.filter((e) => idk.has(e.id));
  }, [kotelezettsegek, emberek]);
  const fizetesiModok = useMemo(
    () => [...new Set(kotelezettsegek.map((k) => k.fizetesi_mod).filter((x): x is string => !!x))].sort(),
    [kotelezettsegek],
  );

  const qn = q.trim().toLowerCase();
  const szurt = (tab === "aktiv" ? aktivak : inaktivak).filter((k) => {
    if (qn && !`${k.nev} ${k.csomag ?? ""} ${k.megjegyzes ?? ""} ${k.kartya ?? ""}`.toLowerCase().includes(qn)) return false;
    if (felelos === "-" ? k.felelos_id != null : felelos && k.felelos_id !== Number(felelos)) return false;
    if (fizetesiMod === "-" ? !!k.fizetesi_mod : fizetesiMod && k.fizetesi_mod !== fizetesiMod) return false;
    if (ciklusSzuro && ciklusa(k) !== ciklusSzuro) return false;
    return true;
  });
  // Szekción belül a legdrágább elöl - ott érdemes először spórolni.
  const szekciok = SZEKCIOK.map((sz) => ({
    ...sz,
    tetelek: szurt.filter((k) => ciklusa(k) === sz.kulcs).sort((a, b) => sz.osszeg(b) - sz.osszeg(a) || a.nev.localeCompare(b.nev, "hu")),
  })).filter((sz) => sz.tetelek.length > 0);

  const osszesito: { kulcs: Ciklus | ""; cim: string; ertek: string; al: string; szur: boolean }[] = [
    { kulcs: "havi", cim: "Havi előfizetések", ertek: String(havi.length), al: `${formatHuf(havi.reduce((s, k) => s + (k.huf_becsles_honap ?? 0), 0))} / hó`, szur: true },
    { kulcs: "eves", cim: "Éves előfizetések", ertek: String(eves.length), al: `${formatHuf(eves.reduce((s, k) => s + (k.huf_becsles_ev ?? 0), 0))} / év`, szur: true },
    { kulcs: "", cim: "Havi költség összesen", ertek: formatHuf(haviKoltseg), al: `${aktivak.length} aktív előfizetés`, szur: false },
    { kulcs: "", cim: "Éves szumma", ertek: formatHuf(evesKoltseg), al: "minden aktív előfizetés", szur: false },
  ];

  function csukas(kulcs: string) {
    setCsukott((c) => {
      const u = new Set(c);
      if (u.has(kulcs)) u.delete(kulcs);
      else u.add(kulcs);
      return u;
    });
  }

  async function torol(k: Kotelezettseg) {
    if (!(await confirm(`Törlöd ezt az előfizetést: "${k.nev}"? A hozzá feltöltött dokumentumok is elvesznek.`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/kotelezettsegek/${k.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  const szuroAktiv = !!(qn || felelos || fizetesiMod || ciklusSzuro);
  const gomb = (aktiv: boolean) =>
    `rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${aktiv ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"}`;
  const valaszto =
    "rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-secondary";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="t-page">E-Rezsi</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            {aktivak.length} aktív · {inaktivak.length} inaktív előfizetés · havi {formatHuf(haviKoltseg)} · éves{" "}
            {formatHuf(evesKoltseg)}
          </p>
        </div>
        {canCreate && (
          <button type="button" onClick={() => setUrlapKezdo(null)} className="btn btn-primary">
            <Plus size={13} /> Új előfizetés
          </button>
        )}
      </div>

      {/* Összesítő - a havi / éves csempe kattintva szűr (újra kattintva visszavonja). */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {osszesito.map((o) => {
          const aktiv = o.szur && tab === "aktiv" && ciklusSzuro === o.kulcs;
          const tartalom = (
            <>
              <p className="t-label">{o.cim}</p>
              <p className="mt-1 text-[22px] font-semibold tabular-nums text-text-primary">{o.ertek}</p>
              <p className="mt-0.5 text-[12px] text-text-muted">{o.al}</p>
            </>
          );
          return o.szur ? (
            <button
              key={o.cim}
              type="button"
              aria-pressed={aktiv}
              onClick={() => {
                setTab("aktiv");
                setCiklusSzuro(aktiv ? "" : o.kulcs);
              }}
              className={`rounded-[var(--radius-lg)] border px-4 py-3 text-left transition-colors ${
                aktiv ? "border-text-accent bg-surface-3" : "border-border bg-surface-2 hover:bg-surface-3"
              }`}
            >
              {tartalom}
            </button>
          ) : (
            <div key={o.cim} className="rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3">
              {tartalom}
            </div>
          );
        })}
      </div>

      {/* Fülek és szűrők egy dobozban. */}
      <div className="flex flex-col gap-3 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setTab("aktiv")} className={gomb(tab === "aktiv")}>
            Aktív ({aktivak.length})
          </button>
          <button type="button" onClick={() => setTab("inaktiv")} className={gomb(tab === "inaktiv")}>
            Inaktív ({inaktivak.length})
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Keresés (név, csomag, kártya, megjegyzés)…"
            className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none sm:w-[300px]"
          />
          <select value={ciklusSzuro} onChange={(e) => setCiklusSzuro(e.target.value as Ciklus | "")} className={valaszto} aria-label="Gyakoriság">
            <option value="">Minden gyakoriság</option>
            <option value="havi">Havi</option>
            <option value="eves">Éves</option>
            <option value="egyszeri">Egyszeri</option>
          </select>
          <select value={felelos} onChange={(e) => setFelelos(e.target.value)} className={valaszto} aria-label="Felelős">
            <option value="">Minden felelős</option>
            {felelosValasztek.map((e) => (
              <option key={e.id} value={e.id}>
                {e.full_name}
              </option>
            ))}
            <option value="-">Felelős nélkül</option>
          </select>
          <select value={fizetesiMod} onChange={(e) => setFizetesiMod(e.target.value)} className={valaszto} aria-label="Fizetési mód">
            <option value="">Minden fizetési mód</option>
            {fizetesiModok.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
            <option value="-">Nincs megadva</option>
          </select>
          {szuroAktiv && (
            <button
              type="button"
              onClick={() => {
                setQ("");
                setFelelos("");
                setFizetesiMod("");
                setCiklusSzuro("");
              }}
              className="text-[12.5px] text-text-accent hover:underline"
            >
              Szűrők törlése
            </button>
          )}
          <span className="ml-auto text-[12px] text-text-muted">{szurt.length} találat</span>
        </div>
      </div>

      {szekciok.length === 0 ? (
        <p className="rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-8 text-center text-[13px] text-text-muted">
          {kotelezettsegek.length === 0 ? "Még nincs felvett előfizetés." : "Nincs a szűrőknek megfelelő előfizetés."}
        </p>
      ) : (
        szekciok.map((sz) => {
          const csukva = csukott.has(sz.kulcs);
          const osszeg = sz.tetelek.filter((k) => k.aktiv).reduce((s, k) => s + sz.osszeg(k), 0);
          return (
            <section key={sz.kulcs} className="overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface-2">
              <button
                type="button"
                onClick={() => csukas(sz.kulcs)}
                aria-expanded={!csukva}
                className="flex w-full items-center gap-2.5 border-b border-border px-4 py-2.5 text-left hover:bg-surface-3"
              >
                <span className={`inline-block h-2.5 w-2.5 rounded-full ${sz.pont}`} />
                <span className="text-[14px] font-semibold text-text-primary">{sz.cim}</span>
                <span className="rounded-full bg-surface-3 px-2 text-[12px] tabular-nums text-text-secondary">{sz.tetelek.length}</span>
                {tab === "aktiv" && (
                  <span className="text-[12.5px] tabular-nums text-text-secondary">
                    {formatHuf(osszeg)} {sz.osszegCimke}
                  </span>
                )}
                <span className="ml-auto text-[12px] text-text-muted">{csukva ? "▸ kinyit" : "▾"}</span>
              </button>
              {!csukva && (
                <>
                  <div className="hidden grid-cols-[minmax(0,1fr)_150px_120px_120px_160px_120px_110px] gap-4 border-b border-border px-4 py-1.5 text-[11.5px] uppercase tracking-wide text-text-muted lg:grid">
                    <span>Előfizetés</span>
                    <span className="text-right">Nettó ár</span>
                    <span className="text-right">Havi (Ft)</span>
                    <span className="text-right">Éves (Ft)</span>
                    <span>Felelős</span>
                    <span>Lejárat</span>
                    <span />
                  </div>
                  <ul className="divide-y divide-border">
                    {sz.tetelek.map((k) => {
                      const nyitva = nyitott === k.id;
                      const lejaratNap = k.kovetkezo_fordulo ? napKulonbseg(ma, k.kovetkezo_fordulo) : null;
                      const letoltoLink = elsoLink(k.szamla_forras);
                      return (
                        <li key={k.id}>
                          <div className="grid grid-cols-1 gap-2 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_150px_120px_120px_160px_120px_110px] lg:items-start lg:gap-4">
                            <div className="min-w-0">
                              <button
                                type="button"
                                onClick={() => setNyitott(nyitva ? null : k.id)}
                                className="flex min-w-0 items-start gap-1.5 text-left"
                              >
                                {nyitva ? (
                                  <ChevronDown size={14} className="mt-1 shrink-0 text-text-muted" />
                                ) : (
                                  <ChevronRight size={14} className="mt-1 shrink-0 text-text-muted" />
                                )}
                                <span className="min-w-0">
                                  <span className="block break-words text-[14px] font-medium text-text-primary hover:text-text-accent">
                                    {k.nev}
                                  </span>
                                  <span className="mt-0.5 flex flex-wrap gap-x-3 text-[12px] text-text-muted">
                                    {k.csomag && <span>{k.csomag}</span>}
                                    {k.fizetesi_mod && <span>{k.fizetesi_mod}</span>}
                                    {k.kartya && <span>kártya: {k.kartya}</span>}
                                    {k.papir_db > 0 && <span>📎 {k.papir_db}</span>}
                                  </span>
                                </span>
                              </button>
                              {/* A számla letöltő linkje egy kattintásra, kinyitás nélkül. */}
                              {letoltoLink && (
                                <a
                                  href={letoltoLink}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  title={letoltoLink}
                                  className="ml-5 mt-1 inline-flex items-center gap-1 text-[12px] text-text-accent hover:underline"
                                >
                                  <ExternalLink size={12} /> Számla letöltése
                                </a>
                              )}
                            </div>
                            <div className="text-[13px] text-text-secondary lg:text-right">
                              <span className="t-label mr-2 lg:hidden">Nettó ár</span>
                              {penzzel(k.ar_osszeg, k.ar_penznem)}
                              {k.ar_plusz_afa && (
                                <span className="block text-[11px] text-text-muted">+ ÁFA → {penzzel(k.ar_brutto, k.ar_penznem)}</span>
                              )}
                            </div>
                            <div className="text-[13px] tabular-nums text-text-secondary lg:text-right">
                              <span className="t-label mr-2 lg:hidden">Havi</span>
                              {k.huf_becsles_honap != null ? formatHuf(k.huf_becsles_honap) : "–"}
                            </div>
                            <div className="text-[13px] tabular-nums text-text-primary lg:text-right">
                              <span className="t-label mr-2 lg:hidden">Éves</span>
                              {k.huf_becsles_ev != null ? formatHuf(k.huf_becsles_ev) : "–"}
                            </div>
                            <div className="text-[13px] text-text-secondary">
                              <span className="t-label mr-2 lg:hidden">Felelős</span>
                              {k.felelos_nev ?? "–"}
                            </div>
                            <div className="text-[13px] text-text-secondary">
                              <span className="t-label mr-2 lg:hidden">Lejárat</span>
                              {k.kovetkezo_fordulo ? huDatum(k.kovetkezo_fordulo) : <span className="text-text-muted">–</span>}
                              {lejaratNap != null && lejaratNap < 0 && (
                                <span className="block text-[11.5px] text-text-danger">{-lejaratNap} napja lejárt</span>
                              )}
                              {lejaratNap != null && lejaratNap >= 0 && lejaratNap <= 30 && (
                                <span className="block text-[11.5px] text-text-warning">{lejaratNap} nap múlva</span>
                              )}
                            </div>
                            <div className="flex items-start gap-1 lg:justify-end">
                              {canEdit && (
                                <button
                                  type="button"
                                  onClick={() => setUrlapKezdo(k)}
                                  className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3"
                                >
                                  Szerkesztés
                                </button>
                              )}
                              {canDelete && (
                                <button
                                  type="button"
                                  onClick={() => torol(k)}
                                  disabled={busy}
                                  title="Törlés"
                                  className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                                >
                                  <Trash2 size={13} />
                                </button>
                              )}
                            </div>
                          </div>
                          {nyitva && (
                            <div className="border-t border-border bg-surface-3/40 px-4 py-3 pl-9">
                              <div className="mb-3 grid grid-cols-1 gap-x-8 gap-y-1 text-[12.5px] text-text-muted sm:grid-cols-2">
                                {k.szamla_forras && (
                                  <p className="whitespace-pre-line sm:col-span-2">
                                    Számla forrása:{" "}
                                    <span className="text-text-secondary">
                                      <LinkeltSzoveg szoveg={k.szamla_forras} laza />
                                    </span>
                                  </p>
                                )}
                                {k.megjegyzes && (
                                  <p className="whitespace-pre-line sm:col-span-2">
                                    Megjegyzés:{" "}
                                    <span className="text-text-secondary">
                                      <LinkeltSzoveg szoveg={k.megjegyzes} />
                                    </span>
                                  </p>
                                )}
                                {!k.szamla_forras && !k.megjegyzes && <p>Nincs megjegyzés vagy számla-forrás.</p>}
                              </div>
                              <p className="t-label mb-1.5">Dokumentumok (szerződés, számla, bármi)</p>
                              <PapirFeltoltes entityType="kotelezettseg" entityId={k.id} canEdit={canEdit} canDelete={canDelete} />
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </section>
          );
        })
      )}

      {urlapKezdo !== undefined && (
        <KotelezettsegUrlapModal
          kezdo={urlapKezdo}
          alapTipus="elofizetes"
          fordulokNelkul
          emberek={emberek}
          onBezar={() => setUrlapKezdo(undefined)}
        />
      )}
    </div>
  );
}
