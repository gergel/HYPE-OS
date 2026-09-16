"use client";

/** ANYAGBEKÉRÉSEK - admin lista + létrehozás (a Media Portal oldalcsalád
 * része, ugyanazzal a jogosultsággal). A részletes nézet külön oldalon:
 * /media-portal/anyagbekeres/[id]. */

import { useMemo, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";

export type BekeresSor = {
  id: number;
  nev: string;
  project_id: number | null;
  client_id: number | null;
  partner_nev: string | null;
  hatarido: string | null;
  felelos_id: number | null;
  allapot: string;
  lejart: boolean;
  link_lejarat: string | null;
  jelszos: boolean;
  kell_brief: boolean;
  engedett_tipusok: string | null;
  meret_keret_bajt: number | null;
  elore_mappak: string[];
  udvozlo_szoveg: string | null;
  link: string;
  leadasok_szama: number;
  piszkozatok_szama: number;
  ossz_meret_bajt: number;
  utolso_aktivitas: string | null;
};

export type Valaszto = { id: number; nev: string };

const BASE = "/api/v1/anyagbekeresek";

export function meretSzoveg(bajt: number): string {
  if (bajt >= 1024 ** 3) return `${(bajt / 1024 ** 3).toFixed(2)} GB`;
  if (bajt >= 1024 ** 2) return `${(bajt / 1024 ** 2).toFixed(1)} MB`;
  if (bajt >= 1024) return `${Math.round(bajt / 1024)} kB`;
  return `${bajt} B`;
}

export function datumSzoveg(iso: string | null): string {
  if (!iso) return "–";
  return new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleString("hu-HU", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function allapotCimke(b: { allapot: string; lejart: boolean }): { szoveg: string; szin: string } {
  if (b.allapot === "lezart") return { szoveg: "Lezárt", szin: "text-text-muted" };
  if (b.lejart) return { szoveg: "Lejárt link", szin: "text-text-warning" };
  return { szoveg: "Nyitott", szin: "text-text-success" };
}

export function AnyagbekeresekPanel({
  kezdeti,
  projektek,
  ugyfelek,
  munkatarsak,
  canCreate,
}: {
  kezdeti: BekeresSor[];
  projektek: Valaszto[];
  ugyfelek: Valaszto[];
  munkatarsak: Valaszto[];
  canCreate: boolean;
}) {
  const [sorok, setSorok] = useState(kezdeti);
  const [kereses, setKereses] = useState("");
  const [allapotSzuro, setAllapotSzuro] = useState("");
  const [projektSzuro, setProjektSzuro] = useState("");
  const [nyitva, setNyitva] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [urlap, setUrlap] = useState({
    nev: "",
    udvozlo_szoveg: "",
    project_id: "",
    client_id: "",
    partner_nev: "",
    hatarido: "",
    felelos_id: "",
    jelszo: "",
    link_lejarat: "",
    kell_brief: true,
    meret_keret_gb: "",
    engedett_tipusok: "",
    elore_mappak: "Nyers videók\nFotók\nHang\nLogók és arculat\nReferenciák",
  });

  const projektNev = useMemo(() => new Map(projektek.map((p) => [p.id, p.nev])), [projektek]);
  const ugyfelNev = useMemo(() => new Map(ugyfelek.map((u) => [u.id, u.nev])), [ugyfelek]);
  const munkatarsNev = useMemo(() => new Map(munkatarsak.map((m) => [m.id, m.nev])), [munkatarsak]);

  const szurt = sorok.filter((s) => {
    if (kereses.trim()) {
      const q = kereses.trim().toLocaleLowerCase("hu-HU");
      const szoveg = `${s.nev} ${projektNev.get(s.project_id ?? -1) ?? ""} ${ugyfelNev.get(s.client_id ?? -1) ?? s.partner_nev ?? ""}`;
      if (!szoveg.toLocaleLowerCase("hu-HU").includes(q)) return false;
    }
    if (allapotSzuro === "nyitott" && (s.allapot !== "nyitott" || s.lejart)) return false;
    if (allapotSzuro === "lezart" && s.allapot !== "lezart") return false;
    if (allapotSzuro === "lejart" && !(s.allapot === "nyitott" && s.lejart)) return false;
    if (projektSzuro && String(s.project_id ?? "") !== projektSzuro) return false;
    return true;
  });

  async function letrehozas() {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(BASE, {
        method: "POST",
        body: JSON.stringify({
          nev: urlap.nev,
          udvozlo_szoveg: urlap.udvozlo_szoveg || null,
          project_id: urlap.project_id ? Number(urlap.project_id) : null,
          client_id: urlap.client_id ? Number(urlap.client_id) : null,
          partner_nev: urlap.partner_nev || null,
          hatarido: urlap.hatarido || null,
          felelos_id: urlap.felelos_id ? Number(urlap.felelos_id) : null,
          jelszo: urlap.jelszo || null,
          link_lejarat: urlap.link_lejarat || null,
          kell_brief: urlap.kell_brief,
          meret_keret_gb: urlap.meret_keret_gb ? Number(urlap.meret_keret_gb) : null,
          engedett_tipusok: urlap.engedett_tipusok || null,
          elore_mappak: urlap.elore_mappak.split("\n").map((s) => s.trim()).filter(Boolean),
        }),
      });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        setHiba(`Sikertelen létrehozás: ${adat?.detail ?? res.status}`);
        return;
      }
      setSorok((elozo) => [adat as BekeresSor, ...elozo]);
      setNyitva(false);
      setUrlap({ ...urlap, nev: "", udvozlo_szoveg: "", jelszo: "" });
      void navigator.clipboard?.writeText(adat.link).catch(() => {});
    } catch (e) {
      setHiba(`Hálózati hiba: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  const input = "w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none";

  return (
    <div className="p-4 md:p-8">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-[18px] font-semibold text-text-primary">Anyagbekérések</h1>
        <Link href="/media-portal" className="text-[13px] text-text-muted hover:text-text-secondary hover:underline">← Média Portálok</Link>
        {canCreate && (
          <button type="button" onClick={() => setNyitva((n) => !n)} className="ml-auto rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent hover:opacity-90">
            {nyitva ? "Mégse" : "+ Új anyagbekérés"}
          </button>
        )}
      </div>

      {nyitva && (
        <div className="mb-5 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <label className="text-[12px] text-text-muted">Anyagbekérés neve *
              <input className={input} value={urlap.nev} onChange={(e) => setUrlap({ ...urlap, nev: e.target.value })} placeholder='pl. "Fesztivál 2026 - nyersanyag leadás"' />
            </label>
            <label className="text-[12px] text-text-muted">Kapcsolódó projekt
              <select className={input} value={urlap.project_id} onChange={(e) => setUrlap({ ...urlap, project_id: e.target.value })}>
                <option value="">– nincs –</option>
                {projektek.map((p) => <option key={p.id} value={p.id}>{p.nev}</option>)}
              </select>
            </label>
            <label className="text-[12px] text-text-muted">Ügyfél
              <select className={input} value={urlap.client_id} onChange={(e) => setUrlap({ ...urlap, client_id: e.target.value })}>
                <option value="">– nincs –</option>
                {ugyfelek.map((u) => <option key={u.id} value={u.id}>{u.nev}</option>)}
              </select>
            </label>
            <label className="text-[12px] text-text-muted">Vagy partner neve (szabad szöveg)
              <input className={input} value={urlap.partner_nev} onChange={(e) => setUrlap({ ...urlap, partner_nev: e.target.value })} />
            </label>
            <label className="text-[12px] text-text-muted">Leadási határidő
              <input type="datetime-local" className={input} value={urlap.hatarido} onChange={(e) => setUrlap({ ...urlap, hatarido: e.target.value })} />
            </label>
            <label className="text-[12px] text-text-muted">Belső felelős
              <select className={input} value={urlap.felelos_id} onChange={(e) => setUrlap({ ...urlap, felelos_id: e.target.value })}>
                <option value="">– nincs –</option>
                {munkatarsak.map((m) => <option key={m.id} value={m.id}>{m.nev}</option>)}
              </select>
            </label>
            <label className="text-[12px] text-text-muted">Jelszó (nem kötelező)
              <input className={input} value={urlap.jelszo} onChange={(e) => setUrlap({ ...urlap, jelszo: e.target.value })} placeholder="A beküldőknek külön elküldendő" />
            </label>
            <label className="text-[12px] text-text-muted">Link lejárata
              <input type="datetime-local" className={input} value={urlap.link_lejarat} onChange={(e) => setUrlap({ ...urlap, link_lejarat: e.target.value })} />
            </label>
            <label className="text-[12px] text-text-muted">Feltöltési keret (GB, üres = nincs)
              <input type="number" min={0} className={input} value={urlap.meret_keret_gb} onChange={(e) => setUrlap({ ...urlap, meret_keret_gb: e.target.value })} />
            </label>
            <label className="text-[12px] text-text-muted">Megengedett fájltípusok (vesszővel, üres = bármi)
              <input className={input} value={urlap.engedett_tipusok} onChange={(e) => setUrlap({ ...urlap, engedett_tipusok: e.target.value })} placeholder="mp4,mov,mxf,wav,jpg,png" />
            </label>
            <label className="flex items-end gap-2 pb-1 text-[13px] text-text-primary">
              <input type="checkbox" checked={urlap.kell_brief} onChange={(e) => setUrlap({ ...urlap, kell_brief: e.target.checked })} />
              Videós briefet is kérünk (nem csak fájlleadást)
            </label>
            <label className="text-[12px] text-text-muted md:col-span-2">Üdvözlőszöveg és feltöltési instrukciók
              <textarea className={input} rows={2} value={urlap.udvozlo_szoveg} onChange={(e) => setUrlap({ ...urlap, udvozlo_szoveg: e.target.value })} />
            </label>
            <label className="text-[12px] text-text-muted">Előre létrehozott mappák (soronként egy)
              <textarea className={input} rows={3} value={urlap.elore_mappak} onChange={(e) => setUrlap({ ...urlap, elore_mappak: e.target.value })} />
            </label>
          </div>
          {hiba && <p className="mt-2 text-[13px] text-text-danger">{hiba}</p>}
          <button type="button" disabled={busy || !urlap.nev.trim()} onClick={() => void letrehozas()} className="mt-3 rounded-[var(--radius)] bg-bg-accent px-4 py-2 text-[13px] font-medium text-text-accent hover:opacity-90 disabled:opacity-40">
            {busy ? "Létrehozás…" : "Létrehozás (a link a vágólapra kerül)"}
          </button>
        </div>
      )}

      <div className="mb-3 flex flex-wrap gap-2">
        <input className={`${input} max-w-xs`} placeholder="Keresés név, projekt, ügyfél szerint…" value={kereses} onChange={(e) => setKereses(e.target.value)} />
        <select className={`${input} w-40`} value={allapotSzuro} onChange={(e) => setAllapotSzuro(e.target.value)}>
          <option value="">Minden állapot</option>
          <option value="nyitott">Nyitott</option>
          <option value="lejart">Lejárt link</option>
          <option value="lezart">Lezárt</option>
        </select>
        <select className={`${input} w-56`} value={projektSzuro} onChange={(e) => setProjektSzuro(e.target.value)}>
          <option value="">Minden projekt</option>
          {projektek.map((p) => <option key={p.id} value={p.id}>{p.nev}</option>)}
        </select>
      </div>

      {szurt.length === 0 ? (
        <p className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6 text-center text-[13px] text-text-muted">
          {sorok.length === 0 ? "Még nincs anyagbekérés - hozd létre az elsőt a jobb felső gombbal." : "Nincs a szűrésnek megfelelő anyagbekérés."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-surface-2 text-[11.5px] uppercase tracking-wide text-text-muted">
              <tr>
                <th className="px-3 py-2">Név</th>
                <th className="px-3 py-2">Projekt</th>
                <th className="px-3 py-2">Ügyfél / partner</th>
                <th className="px-3 py-2">Határidő</th>
                <th className="px-3 py-2">Állapot</th>
                <th className="px-3 py-2 text-right">Leadások</th>
                <th className="px-3 py-2 text-right">Méret</th>
                <th className="px-3 py-2">Utolsó aktivitás</th>
                <th className="px-3 py-2">Felelős</th>
              </tr>
            </thead>
            <tbody>
              {szurt.map((s) => {
                const a = allapotCimke(s);
                return (
                  <tr key={s.id} className="border-t border-border hover:bg-surface-2">
                    <td className="px-3 py-2">
                      <Link href={`/media-portal/anyagbekeres/${s.id}`} className="font-medium text-text-primary hover:underline">{s.nev}</Link>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">{projektNev.get(s.project_id ?? -1) ?? "–"}</td>
                    <td className="px-3 py-2 text-text-secondary">{ugyfelNev.get(s.client_id ?? -1) ?? s.partner_nev ?? "–"}</td>
                    <td className="px-3 py-2 text-text-secondary">{datumSzoveg(s.hatarido)}</td>
                    <td className={`px-3 py-2 ${a.szin}`}>{a.szoveg}</td>
                    <td className="px-3 py-2 text-right text-text-secondary">{s.leadasok_szama}{s.piszkozatok_szama > 0 ? ` (+${s.piszkozatok_szama} piszkozat)` : ""}</td>
                    <td className="px-3 py-2 text-right text-text-secondary">{meretSzoveg(s.ossz_meret_bajt)}</td>
                    <td className="px-3 py-2 text-text-muted">{datumSzoveg(s.utolso_aktivitas)}</td>
                    <td className="px-3 py-2 text-text-secondary">{munkatarsNev.get(s.felelos_id ?? -1) ?? "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
