"use client";

/** EGY ANYAGBEKÉRÉS admin nézete: beállítások/link-műveletek, a beküldők
 * leadásai, és a kiválasztott leadás részletei - bal oldalon mappafa,
 * középen fájllista, jobb oldalon a kijelölt mappa/fájl megjegyzései és
 * videóigényei, alatta a teljes "Kért videók" nézet. */

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";
import { allapotCimke, datumSzoveg, meretSzoveg, type BekeresSor, type Valaszto } from "./AnyagbekeresekPanel";

const BASE = "/api/v1/anyagbekeresek";

type LeadasSor = {
  id: number;
  bekuldo_nev: string;
  bekuldo_email: string;
  bekuldo_ceg: string | null;
  allapot: string;
  leadva_at: string | null;
  letrehozva: string | null;
  fajlok_szama: number;
  ossz_meret_bajt: number;
  igenyek_szama: number;
  felelos_id: number | null;
};

type MappaT = { id: number; szulo_id: number | null; nev: string; utvonal: string; leiras: string | null };
type FajlT = {
  id: number;
  mappa_id: number | null;
  nev: string;
  relativ_utvonal: string | null;
  meret_bajt: number;
  content_type: string | null;
  allapot: string;
  kesz_at: string | null;
};
type IgenyT = {
  id: number;
  nev: string;
  leiras: string | null;
  hossz: string | null;
  felulet: string | null;
  keparany: string | null;
  hatarido: string | null;
  teljes_anyagbol: boolean;
  reszletek: Record<string, string>;
  idokodok: { fajl_id: number | null; szoveg: string }[];
  mappa_idk: number[];
  fajl_idk: number[];
};

type LeadasReszlet = LeadasSor & {
  belso_megjegyzes: string | null;
  mappak: MappaT[];
  fajlok: FajlT[];
  igenyek: IgenyT[];
};

type Reszletek = BekeresSor & {
  leadasok: LeadasSor[];
  esemenyek: { tipus: string; leadas_id: number | null; adat: Record<string, unknown> | null; created_at: string }[];
};

const LEADAS_ALLAPOTOK: [string, string][] = [
  ["piszkozat", "Piszkozat"],
  ["leadva", "Leadva"],
  ["feldolgozas", "Feldolgozás alatt"],
  ["kesz", "Kész"],
];

const RESZLET_CIMKEK: Record<string, string> = {
  cel: "Cél és célközönség",
  stilus: "Stílus és hangulat",
  kotelezo: "Kötelező jelenetek/személyek/termékek",
  kihagyando: "Kihagyandó részek",
  felirat: "Feliratigény és nyelv",
  szovegek: "Képernyőszövegek és CTA",
  zene: "Zene és narráció",
  referenciak: "Referenciák",
  technikai: "Technikai elvárások",
  egyeb: "Egyéb",
};

export function AnyagbekeresReszletek({
  kezdeti,
  munkatarsak,
  canEdit,
  canDelete,
}: {
  kezdeti: Reszletek;
  munkatarsak: Valaszto[];
  canEdit: boolean;
  canDelete: boolean;
}) {
  const [adat, setAdat] = useState(kezdeti);
  const [nyitottLeadas, setNyitottLeadas] = useState<LeadasReszlet | null>(null);
  const [kijeloltMappa, setKijeloltMappa] = useState<number | null>(null);
  const [kijeloltFajl, setKijeloltFajl] = useState<number | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [masolva, setMasolva] = useState<string | null>(null);
  const [exportJob, setExportJob] = useState<{ id: string; state: string; bytes_done: number; total_bytes: number; url: string | null; error: string | null } | null>(null);
  const exportIdozito = useRef<ReturnType<typeof setInterval> | null>(null);
  const munkatarsNev = useMemo(() => new Map(munkatarsak.map((m) => [m.id, m.nev])), [munkatarsak]);

  async function frissites() {
    const r = await authFetch(`${BASE}/${adat.id}`);
    if (r.ok) setAdat(await r.json());
  }

  async function leadasNyitas(id: number) {
    const r = await authFetch(`${BASE}/${adat.id}/leadas/${id}`);
    if (r.ok) {
      setNyitottLeadas(await r.json());
      setKijeloltMappa(null);
      setKijeloltFajl(null);
      setExportJob(null);
    }
  }

  async function bekeresMuvelet(utvonal: string, body?: unknown) {
    setHiba(null);
    const r = await authFetch(`${BASE}/${adat.id}${utvonal}`, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) {
      setHiba(d?.detail ?? `Hiba (${r.status})`);
      return null;
    }
    await frissites();
    return d;
  }

  async function leadasModositas(leadasId: number, valtozas: Record<string, unknown>) {
    const r = await authFetch(`${BASE}/${adat.id}/leadas/${leadasId}`, { method: "PATCH", body: JSON.stringify(valtozas) });
    if (!r.ok) {
      setHiba((await r.json().catch(() => null))?.detail ?? `Hiba (${r.status})`);
      return;
    }
    await frissites();
    if (nyitottLeadas?.id === leadasId) {
      setNyitottLeadas((elozo) => (elozo ? { ...elozo, ...valtozas } : elozo));
    }
  }

  async function igenyTorles(leadasId: number, igeny: IgenyT) {
    if (!window.confirm(`Biztosan törlöd a(z) "${igeny.nev || "névtelen"}" kért videót? A művelet nem visszavonható.`)) return;
    setHiba(null);
    const r = await authFetch(`${BASE}/${adat.id}/leadas/${leadasId}/igeny/${igeny.id}`, { method: "DELETE" });
    if (!r.ok) {
      setHiba((await r.json().catch(() => null))?.detail ?? `Hiba (${r.status})`);
      return;
    }
    // Frissítjük a nyitott leadás igényeit és a lista számlálóját.
    setNyittottLeadasIgenyFrissites(leadasId, igeny.id);
    await frissites();
  }

  function setNyittottLeadasIgenyFrissites(leadasId: number, igenyId: number) {
    setNyitottLeadas((elozo) =>
      elozo && elozo.id === leadasId
        ? { ...elozo, igenyek: elozo.igenyek.filter((x) => x.id !== igenyId) }
        : elozo,
    );
  }

  async function bekeresTorles() {
    const uzenet = `Biztosan törlöd a(z) "${adat.nev}" anyagbekérést?\n\nEzzel minden leadás, feltöltött fájl és kért videó véglegesen törlődik. A művelet nem visszavonható.`;
    if (!window.confirm(uzenet)) return;
    const r = await authFetch(`${BASE}/${adat.id}`, { method: "DELETE" });
    if (!r.ok) {
      setHiba((await r.json().catch(() => null))?.detail ?? `Hiba (${r.status})`);
      return;
    }
    window.location.href = "/media-portal/anyagbekeresek";
  }

  async function fajlLetoltes(leadasId: number, fajlId: number) {
    const r = await authFetch(`${BASE}/${adat.id}/leadas/${leadasId}/fajl/${fajlId}/letoltes`);
    const d = await r.json().catch(() => null);
    if (!r.ok) {
      setHiba(d?.detail ?? "A letöltő link nem készült el.");
      return;
    }
    window.open(d.url, "_blank");
  }

  /** Az adott fájlra mutató, megosztható (7 napig élő) letöltő link a
   * vágólapra - a felhasználó kérése, hogy egy konkrét anyaghoz linket
   * lehessen küldeni. */
  async function fajlLinkMasolas(leadasId: number, fajlId: number) {
    setHiba(null);
    const r = await authFetch(`${BASE}/${adat.id}/leadas/${leadasId}/fajl/${fajlId}/letoltes?megosztas=true`);
    const d = await r.json().catch(() => null);
    if (!r.ok) {
      setHiba(d?.detail ?? "A megosztó link nem készült el.");
      return;
    }
    masol(d.url, `fajl-${fajlId}`);
  }

  async function exportInditas(leadasId: number, mappaId: number | null) {
    setHiba(null);
    const r = await authFetch(`${BASE}/${adat.id}/leadas/${leadasId}/export`, {
      method: "POST",
      body: JSON.stringify({ mappa_id: mappaId }),
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) {
      setHiba(d?.detail ?? "A csomag nem indult el.");
      return;
    }
    setExportJob(d);
    if (exportIdozito.current) clearInterval(exportIdozito.current);
    exportIdozito.current = setInterval(async () => {
      const rr = await authFetch(`${BASE}/export/${d.id}`);
      if (rr.ok) {
        const j = await rr.json();
        setExportJob(j);
        if (j.state === "ready" || j.state === "failed") {
          if (exportIdozito.current) clearInterval(exportIdozito.current);
        }
      }
    }, 2500);
  }

  useEffect(() => () => {
    if (exportIdozito.current) clearInterval(exportIdozito.current);
  }, []);

  const a = allapotCimke(adat);
  const gomb = "rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-40";
  const input = "rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none";

  function masol(szoveg: string, cimke: string) {
    void navigator.clipboard?.writeText(szoveg).then(() => {
      setMasolva(cimke);
      setTimeout(() => setMasolva(null), 2000);
    });
  }

  const briefSzoveg = (l: LeadasReszlet) =>
    l.igenyek
      .map((i) => {
        const mappaNevek = i.mappa_idk.map((id) => l.mappak.find((m) => m.id === id)?.utvonal ?? `#${id}`);
        const fajlNevek = i.fajl_idk.map((id) => l.fajlok.find((f) => f.id === id)?.nev ?? `#${id}`);
        const sorok = [
          `## ${i.nev}`,
          i.leiras ?? "",
          [i.keparany && `Képarány: ${i.keparany}`, i.hossz && `Hossz: ${i.hossz}`, i.felulet && `Felület: ${i.felulet}`, i.hatarido && `Határidő: ${i.hatarido.slice(0, 10)}`].filter(Boolean).join(" · "),
          i.teljes_anyagbol ? "Forrás: a teljes leadott anyag" : `Forrás: ${[...mappaNevek, ...fajlNevek].join(", ") || "-"}`,
          ...Object.entries(i.reszletek).map(([k, v]) => `${RESZLET_CIMKEK[k] ?? k}: ${v}`),
          ...i.idokodok.map((x) => `Időkód${x.fajl_id ? ` (${l.fajlok.find((f) => f.id === x.fajl_id)?.nev ?? x.fajl_id})` : ""}: ${x.szoveg}`),
        ];
        return sorok.filter(Boolean).join("\n");
      })
      .join("\n\n");

  return (
    <div className="p-4 md:p-8">
      {/* Fejléc + fő műveletek */}
      <div className="mb-1 flex flex-wrap items-center gap-3">
        <Link href="/media-portal/anyagbekeresek" className="text-[13px] text-text-muted hover:underline">← Anyagbekérések</Link>
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-[18px] font-semibold text-text-primary">{adat.nev}</h1>
        <span className={`text-[13px] ${a.szin}`}>{a.szoveg}</span>
        <span className="text-[13px] text-text-muted">{adat.leadasok_szama} leadás · {meretSzoveg(adat.ossz_meret_bajt)}</span>
        <div className="ml-auto flex flex-wrap gap-2">
          <button type="button" className={gomb} onClick={() => masol(adat.link, "link")}>{masolva === "link" ? "Kimásolva ✓" : "Link másolása"}</button>
          <a href={adat.link} target="_blank" rel="noopener noreferrer" className={gomb}>Beküldői oldal előnézete</a>
          {canEdit && (
            <>
              <button type="button" className={gomb} onClick={() => void bekeresMuvelet("/allapot", { allapot: adat.allapot === "nyitott" ? "lezart" : "nyitott" })}>
                {adat.allapot === "nyitott" ? "Bekérés lezárása" : "Újranyitás"}
              </button>
              <button
                type="button"
                className={gomb}
                title="A régi link azonnal érvénytelen lesz; a már elkezdett leadások megmaradnak."
                onClick={() => void bekeresMuvelet("/token-ujra")}
              >
                Link visszavonása + új link
              </button>
            </>
          )}
          {canDelete && (
            <button
              type="button"
              className="rounded-[var(--radius)] border border-text-danger/40 px-2.5 py-1 text-[12.5px] text-text-danger hover:bg-bg-danger/15"
              onClick={() => void bekeresTorles()}
            >
              Bekérés törlése
            </button>
          )}
        </div>
      </div>
      {hiba && <p className="mb-3 rounded-[var(--radius)] border border-text-danger/40 bg-bg-danger/30 px-3 py-2 text-[13px] text-text-danger">{hiba}</p>}

      {/* Leadások listája */}
      <div className="mb-5 overflow-x-auto rounded-[var(--radius-lg)] border border-border">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-surface-2 text-[11.5px] uppercase tracking-wide text-text-muted">
            <tr>
              <th className="px-3 py-2">Beküldő</th>
              <th className="px-3 py-2">Állapot</th>
              <th className="px-3 py-2">Leadva</th>
              <th className="px-3 py-2 text-right">Fájlok</th>
              <th className="px-3 py-2 text-right">Méret</th>
              <th className="px-3 py-2 text-right">Videóigények</th>
              <th className="px-3 py-2">Felelős</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {adat.leadasok.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-5 text-center text-text-muted">Még nincs leadás - küldd el a linket a beküldőknek.</td></tr>
            )}
            {adat.leadasok.map((l) => (
              <tr key={l.id} className={`border-t border-border ${nyitottLeadas?.id === l.id ? "bg-bg-accent/20" : "hover:bg-surface-2"}`}>
                <td className="px-3 py-2">
                  <button type="button" onClick={() => void leadasNyitas(l.id)} className="font-medium text-text-primary hover:underline">{l.bekuldo_nev}</button>
                  <span className="ml-2 text-text-muted">{l.bekuldo_email}{l.bekuldo_ceg ? ` · ${l.bekuldo_ceg}` : ""}</span>
                </td>
                <td className="px-3 py-2 text-text-secondary">{LEADAS_ALLAPOTOK.find(([k]) => k === l.allapot)?.[1] ?? l.allapot}</td>
                <td className="px-3 py-2 text-text-secondary">{l.leadva_at ? datumSzoveg(l.leadva_at) : "–"}</td>
                <td className="px-3 py-2 text-right text-text-secondary">{l.fajlok_szama}</td>
                <td className="px-3 py-2 text-right text-text-secondary">{meretSzoveg(l.ossz_meret_bajt)}</td>
                <td className="px-3 py-2 text-right text-text-secondary">{l.igenyek_szama}</td>
                <td className="px-3 py-2 text-text-secondary">{munkatarsNev.get(l.felelos_id ?? -1) ?? "–"}</td>
                <td className="px-3 py-2 text-right">
                  <button type="button" className={gomb} onClick={() => void leadasNyitas(l.id)}>Megnyitás</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* A kiválasztott leadás részletei */}
      {nyitottLeadas && (
        <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <p className="text-[15px] font-medium text-text-primary">
              Leadás #{nyitottLeadas.id} - {nyitottLeadas.bekuldo_nev}
            </p>
            {canEdit && (
              <>
                <select
                  className={input}
                  value={nyitottLeadas.allapot}
                  onChange={(e) => void leadasModositas(nyitottLeadas.id, { allapot: e.target.value })}
                >
                  {LEADAS_ALLAPOTOK.map(([k, c]) => <option key={k} value={k}>{c}</option>)}
                </select>
                <select
                  className={input}
                  value={nyitottLeadas.felelos_id ?? ""}
                  onChange={(e) => void leadasModositas(nyitottLeadas.id, { felelos_id: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">– felelős –</option>
                  {munkatarsak.map((m) => <option key={m.id} value={m.id}>{m.nev}</option>)}
                </select>
              </>
            )}
            <div className="ml-auto flex flex-wrap gap-2">
              <button type="button" className={gomb} onClick={() => masol(briefSzoveg(nyitottLeadas), "brief")}>
                {masolva === "brief" ? "Kimásolva ✓" : "Brief másolása"}
              </button>
              <button type="button" className={gomb} onClick={() => void exportInditas(nyitottLeadas.id, null)}>
                Teljes leadás letöltése (ZIP)
              </button>
              {kijeloltMappa !== null && (
                <button type="button" className={gomb} onClick={() => void exportInditas(nyitottLeadas.id, kijeloltMappa)}>
                  Kijelölt mappa letöltése (ZIP)
                </button>
              )}
            </div>
          </div>

          {exportJob && (
            <p className="mb-3 rounded-[var(--radius)] border border-border bg-surface-1 px-3 py-2 text-[13px] text-text-secondary">
              Csomag: {exportJob.state === "ready" ? (
                <a href={exportJob.url ?? "#"} className="text-text-accent hover:underline">kész - letöltés (a link 48 óráig él)</a>
              ) : exportJob.state === "failed" ? (
                <span className="text-text-danger">{exportJob.error ?? "sikertelen"}</span>
              ) : (
                <>készül… {meretSzoveg(exportJob.bytes_done)} / {meretSzoveg(exportJob.total_bytes)}</>
              )}
            </p>
          )}

          <div className="grid gap-4 lg:grid-cols-[220px_1fr_300px]">
            {/* Mappafa */}
            <div>
              <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">Mappák</p>
              <button
                type="button"
                onClick={() => { setKijeloltMappa(null); setKijeloltFajl(null); }}
                className={`block w-full rounded px-2 py-1 text-left text-[13px] ${kijeloltMappa === null ? "bg-bg-accent text-text-accent" : "text-text-secondary hover:bg-surface-3"}`}
              >
                (minden fájl)
              </button>
              {nyitottLeadas.mappak.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => { setKijeloltMappa(m.id); setKijeloltFajl(null); }}
                  style={{ paddingLeft: `${8 + (m.utvonal.split("/").length - 1) * 14}px` }}
                  className={`block w-full rounded py-1 pr-2 text-left text-[13px] ${kijeloltMappa === m.id ? "bg-bg-accent text-text-accent" : "text-text-secondary hover:bg-surface-3"}`}
                >
                  📁 {m.nev}
                </button>
              ))}
            </div>

            {/* Fájllista */}
            <div className="min-w-0">
              <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">Fájlok</p>
              <div className="grid gap-1">
                {nyitottLeadas.fajlok
                  .filter((f) => kijeloltMappa === null || f.mappa_id === kijeloltMappa)
                  .map((f) => (
                    <div
                      key={f.id}
                      className={`flex items-center gap-2 rounded border px-2.5 py-1.5 text-[13px] ${kijeloltFajl === f.id ? "border-text-accent/50 bg-bg-accent/20" : "border-border bg-surface-1"}`}
                    >
                      <button type="button" onClick={() => setKijeloltFajl(f.id)} className="min-w-0 flex-1 truncate text-left text-text-primary" title={f.relativ_utvonal ?? f.nev}>
                        {kijeloltMappa === null ? f.relativ_utvonal ?? f.nev : f.nev}
                      </button>
                      <span className="text-text-muted">{meretSzoveg(f.meret_bajt)}</span>
                      {f.allapot !== "kesz" && <span className="text-text-warning">{f.allapot === "hibas" ? "hibás" : "folyamatban"}</span>}
                      {f.allapot === "kesz" && (
                        <>
                          <button type="button" className="text-[12.5px] text-text-accent hover:underline" onClick={() => void fajlLetoltes(nyitottLeadas.id, f.id)}>
                            Letöltés
                          </button>
                          <button type="button" className="text-[12.5px] text-text-secondary hover:underline" onClick={() => void fajlLinkMasolas(nyitottLeadas.id, f.id)}>
                            {masolva === `fajl-${f.id}` ? "Kimásolva ✓" : "Link"}
                          </button>
                        </>
                      )}
                    </div>
                  ))}
                {nyitottLeadas.fajlok.filter((f) => kijeloltMappa === null || f.mappa_id === kijeloltMappa).length === 0 && (
                  <p className="text-[13px] text-text-muted">Nincs fájl ebben a nézetben.</p>
                )}
              </div>
            </div>

            {/* Jobb panel: megjegyzések + kapcsolt igények */}
            <div>
              <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">Megjegyzések és kapcsolatok</p>
              {kijeloltMappa !== null && (() => {
                const m = nyitottLeadas.mappak.find((x) => x.id === kijeloltMappa)!;
                const kapcsolt = nyitottLeadas.igenyek.filter((i) => i.mappa_idk.includes(m.id) || i.teljes_anyagbol);
                return (
                  <div className="grid gap-2 text-[13px]">
                    <p className="font-medium text-text-primary">📁 {m.utvonal}</p>
                    <p className="whitespace-pre-line text-text-secondary">{m.leiras || "Nincs beküldői megjegyzés."}</p>
                    <p className="mt-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">Ehhez kapcsolt videóigények</p>
                    {kapcsolt.length === 0 ? <p className="text-text-muted">Nincs.</p> : kapcsolt.map((i) => <p key={i.id} className="text-text-secondary">• {i.nev}{i.teljes_anyagbol ? " (teljes anyagból)" : ""}</p>)}
                  </div>
                );
              })()}
              {kijeloltFajl !== null && (() => {
                const f = nyitottLeadas.fajlok.find((x) => x.id === kijeloltFajl)!;
                const kapcsolt = nyitottLeadas.igenyek.filter((i) => i.fajl_idk.includes(f.id) || i.teljes_anyagbol);
                const idokodok = nyitottLeadas.igenyek.flatMap((i) => i.idokodok.filter((x) => x.fajl_id === f.id).map((x) => ({ igeny: i.nev, szoveg: x.szoveg })));
                return (
                  <div className="mt-3 grid gap-2 text-[13px]">
                    <p className="font-medium text-text-primary">🎬 {f.nev}</p>
                    <p className="text-text-muted">{meretSzoveg(f.meret_bajt)}{f.content_type ? ` · ${f.content_type}` : ""}</p>
                    <p className="mt-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">Ehhez kapcsolt videóigények</p>
                    {kapcsolt.length === 0 ? <p className="text-text-muted">Nincs.</p> : kapcsolt.map((i) => <p key={i.id} className="text-text-secondary">• {i.nev}</p>)}
                    {idokodok.length > 0 && (
                      <>
                        <p className="mt-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">Időkódos megjegyzések</p>
                        {idokodok.map((x, xi) => <p key={xi} className="text-text-secondary">• {x.szoveg} <span className="text-text-muted">({x.igeny})</span></p>)}
                      </>
                    )}
                  </div>
                );
              })()}
              {kijeloltMappa === null && kijeloltFajl === null && (
                <p className="text-[13px] text-text-muted">Válassz mappát vagy fájlt a részletekhez.</p>
              )}

              {/* Belső megjegyzés - a beküldő nem látja */}
              <p className="mb-1 mt-4 text-[12px] font-medium uppercase tracking-wide text-text-muted">Belső megjegyzés (a beküldő nem látja)</p>
              <textarea
                className="w-full rounded-[var(--radius)] border border-border bg-surface-1 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
                rows={3}
                defaultValue={nyitottLeadas.belso_megjegyzes ?? ""}
                disabled={!canEdit}
                onBlur={(e) => void leadasModositas(nyitottLeadas.id, { belso_megjegyzes: e.target.value })}
              />
            </div>
          </div>

          {/* Kért videók nézet */}
          <div className="mt-5 border-t border-border pt-4">
            <p className="mb-2 text-[15px] font-medium text-text-primary">Kért videók ({nyitottLeadas.igenyek.length})</p>
            {nyitottLeadas.igenyek.length === 0 && <p className="text-[13px] text-text-muted">Ehhez a leadáshoz nem érkezett videóigény - csak fájlleadás.</p>}
            <div className="grid gap-3 lg:grid-cols-2">
              {nyitottLeadas.igenyek.map((i) => (
                <div key={i.id} className="rounded-[var(--radius)] border border-border bg-surface-1 p-3 text-[13px]">
                  <div className="flex items-start gap-2">
                    <p className="min-w-0 flex-1 text-[14px] font-medium text-text-primary">{i.nev}</p>
                    {canDelete && (
                      <button
                        type="button"
                        onClick={() => void igenyTorles(nyitottLeadas.id, i)}
                        className="shrink-0 rounded-[var(--radius)] px-2 py-0.5 text-[12px] text-text-danger hover:bg-bg-danger/15"
                        title="Kért videó törlése"
                      >
                        Törlés
                      </button>
                    )}
                  </div>
                  <p className="mt-0.5 text-text-muted">
                    {[i.keparany, i.hossz, i.felulet, i.hatarido ? `határidő: ${i.hatarido.slice(0, 10)}` : null].filter(Boolean).join(" · ") || "–"}
                  </p>
                  {i.leiras && <p className="mt-1.5 whitespace-pre-line text-text-secondary">{i.leiras}</p>}
                  <p className="mt-1.5 text-text-secondary">
                    <b className="text-text-primary">Forrás:</b>{" "}
                    {i.teljes_anyagbol
                      ? "a teljes leadott anyag"
                      : [
                          ...i.mappa_idk.map((id) => `📁 ${nyitottLeadas.mappak.find((m) => m.id === id)?.utvonal ?? id}`),
                          ...i.fajl_idk.map((id) => nyitottLeadas.fajlok.find((f) => f.id === id)?.nev ?? String(id)),
                        ].join(", ") || "–"}
                  </p>
                  {Object.entries(i.reszletek).length > 0 && (
                    <div className="mt-1.5 grid gap-0.5">
                      {Object.entries(i.reszletek).map(([k, v]) => (
                        <p key={k} className="text-text-secondary"><b className="text-text-primary">{RESZLET_CIMKEK[k] ?? k}:</b> {v}</p>
                      ))}
                    </div>
                  )}
                  {i.idokodok.length > 0 && (
                    <div className="mt-1.5">
                      {i.idokodok.map((x, xi) => (
                        <p key={xi} className="text-text-secondary">
                          ⏱ {x.fajl_id ? `${nyitottLeadas.fajlok.find((f) => f.id === x.fajl_id)?.nev ?? x.fajl_id}: ` : ""}{x.szoveg}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
