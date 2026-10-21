"use client";

import { useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";

type Tetel = {
  equipment_id: number;
  nev: string;
  kategoria: string | null;
  qty: number;
  track_mode: string;
  forras: string;
  gyakorisag: string | null;
  helyettesiti?: { nev: string } | null;
  szerep?: string;
  mire_jo?: string | null;
  hasonlosag?: number;
};

export type FelismertFeladat = {
  tipus: string;
  tipus_cimke: string;
  kimenetek: string[];
  jellemzok: string[];
  feladat_leiras: string | null;
  osszegzes: string;
  bizonyossag: number | null;
  bizonyitek?: string[];
  forras: "szabaly" | "modell" | "ember";
};

export type FeladatTapasztalat = {
  cimke: string;
  forgatasok: number;
  technikas_forgatasok: number;
  szerepek: { szerep: string; arany: number; db: number; proj: number; n: number; pelda: string[] }[];
  jellemzo_szerepek: { jellemzo: string; szerep: string; arany: number; alap_arany: number; db: number; proj: number; n: number }[];
  visszatero_instrukciok: string[];
};

type Tapasztalat = {
  felismert_feladat: FelismertFeladat;
  feladat_tapasztalat: FeladatTapasztalat;
  hasonlo_forgatasok: { id: number; nev: string; datum: string; okok: string[] }[];
  technika: { tetelek: Tetel[]; figyelmeztetesek: string[]; tapasztalat_forgatasok: number; feladat_forgatasok?: number };
  visszatero_instrukciok: string[];
  diszpo_szoveg: {
    mezok: Record<string, { ertek: string; indoklas: string }>;
    forras_diszpok: number;
    figyelmeztetesek: string[];
  };
};

const FELISMERES_FORRAS: Record<string, string> = {
  szabaly: "kulcsszavak alapján",
  modell: "AI pontosította",
  ember: "ember javította",
};

/** Lara felismerése a forgatás feladatáról + amit az ilyen feladatú korábbi
 * forgatásokról tud (szerepenként, arányokkal). */
export function FeladatBlokk({ f, t, javitasLink }: { f: FelismertFeladat; t: FeladatTapasztalat | null; javitasLink?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="font-medium text-text-primary">Mi a feladat? (Lara felismerése)</p>
      <p className="text-text-primary">{f.feladat_leiras || f.osszegzes}</p>
      {f.feladat_leiras && <p className="text-[12px] text-text-secondary">{f.osszegzes}</p>}
      <p className="text-[12px] text-text-muted">
        {FELISMERES_FORRAS[f.forras] ?? f.forras}
        {f.bizonyossag != null ? ` · ${Math.round(f.bizonyossag * 100)}% biztos` : ""}
        {f.bizonyitek && f.bizonyitek.length > 0 ? ` · ${f.bizonyitek.join(", ")}` : ""}
        {javitasLink && (
          <>
            {" · "}
            <Link href={javitasLink} className="underline">
              javítás
            </Link>
          </>
        )}
      </p>
      {t && t.forgatasok > 0 && (
        <div className="mt-1">
          <p className="text-text-secondary">
            Az ilyen („{t.cimke.toLowerCase()}”) korábbi forgatások: {t.forgatasok}, ebből {t.technikas_forgatasok} ismert
            technikával.
          </p>
          {t.szerepek.length > 0 && (
            <ul className="list-disc pl-5 text-text-secondary">
              {t.szerepek.slice(0, 10).map((s) => (
                <li key={s.szerep}>
                  <span className="text-text-primary">{s.szerep}</span> — {s.proj}/{s.n} forgatáson (
                  {Math.round(s.arany * 100)}%), jellemzően {s.db} db
                  {s.pelda.length > 0 ? ` · pl. ${s.pelda.join(", ")}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {t && t.jellemzo_szerepek.length > 0 && (
        <div className="mt-1">
          <p className="text-text-secondary">Ehhez a feladathoz kötődő eszközök (a korábbi forgatásokból felfedezve):</p>
          <ul className="list-disc pl-5 text-text-secondary">
            {t.jellemzo_szerepek.slice(0, 8).map((s) => (
              <li key={`${s.jellemzo}-${s.szerep}`}>
                {s.jellemzo} → <span className="text-text-primary">{s.szerep}</span> — {Math.round(s.arany * 100)}% (máshol{" "}
                {Math.round(s.alap_arany * 100)}%)
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function hibaSzoveg(status: number, d: { detail?: unknown }): string {
  if (status === 423) return "Lara most le van állítva (vészleállítás).";
  if (status === 403) return "Ehhez Lara-jogosultság kell.";
  return typeof d.detail === "string" ? d.detail : `Sikertelen (${status}).`;
}

/** A projekt Eszközök kártyáján: Lara a korábbi hasonló forgatások
 * tapasztalatából megírja a briefet és összeállítja a technikát. A javaslat
 * jóváhagyásra kerül; jóváhagyás után Lara az eszközöket ténylegesen hozzá is
 * rendeli a projekthez (ugyanazon az úton, mint a „hozzáadás”), és lefuttatja a
 * „Technika ready” ellenőrzést. A diszpót nem küldi ki. */
export function LaraDiszpoGomb({ projectId }: { projectId: number }) {
  const [brief, setBrief] = useState(true);
  const [diszpoSzoveg, setDiszpoSzoveg] = useState(true);
  const [technika, setTechnika] = useState(true);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [kesz, setKesz] = useState<{ taskId: number; szoveg: string } | null>(null);
  const [tap, setTap] = useState<Tapasztalat | null>(null);

  async function tervezet() {
    setBusy(true);
    setHiba(null);
    setKesz(null);
    try {
      const res = await authFetch(`/api/v1/admin-agent/diszpo/${projectId}/tervezet`, {
        method: "POST",
        body: JSON.stringify({ brief, technika, diszpo_szoveg: diszpoSzoveg }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(hibaSzoveg(res.status, d));
        return;
      }
      const szoveg =
        d.decision === "needs_approval"
          ? "Elkészült, jóváhagyásra vár."
          : d.decision === "blocked"
            ? "Elkészült árnyék-javaslatként (Lara bizalmi szintje / kapcsolói miatt most nem hajtható végre - a Beállításokban emelhető)."
            : "Elkészült.";
      setKesz({ taskId: d.task?.id, szoveg });
    } finally {
      setBusy(false);
    }
  }

  async function elonezet() {
    if (tap) {
      setTap(null);
      return;
    }
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/admin-agent/diszpo/${projectId}/tapasztalat`);
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(hibaSzoveg(res.status, d));
        return;
      }
      setTap(d as Tapasztalat);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 text-[13px]">
      <p className="text-text-secondary">
        <strong className="text-text-primary">Lara:</strong> felismeri, mi a feladat a forgatáson, és ehhez írja meg a diszpó
        szövegét, a briefet és a technikai listát a korábbi hasonló és ugyanilyen feladatú forgatások alapján (az eszközöket jóváhagyás után hozzá is rendeli - foglalt eszköz helyett hasonlót).
      </p>
      <div className="flex flex-wrap items-center gap-3 text-text-secondary">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={diszpoSzoveg} onChange={(e) => setDiszpoSzoveg(e.target.checked)} /> diszpó szöveg
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={brief} onChange={(e) => setBrief(e.target.checked)} /> brief
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={technika} onChange={(e) => setTechnika(e.target.checked)} /> technika
        </label>
        <button
          type="button"
          disabled={busy || (!brief && !technika && !diszpoSzoveg)}
          onClick={tervezet}
          className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 font-medium text-text-accent disabled:opacity-50"
        >
          {busy ? "Dolgozom…" : "Kérem Larától"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={elonezet}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {tap ? "Előnézet elrejtése" : "Mit tanult Lara ehhez?"}
        </button>
      </div>
      {hiba && <p className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-text-danger">{hiba}</p>}
      {kesz && (
        <p className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-text-success">
          {kesz.szoveg}{" "}
          {kesz.taskId && (
            <Link href={`/admin-agent/munkasor/${kesz.taskId}`} className="underline">
              Megnyitás →
            </Link>
          )}
        </p>
      )}
      {tap && (
        <div className="flex flex-col gap-2 rounded-[var(--radius)] border border-border p-3">
          <FeladatBlokk
            f={tap.felismert_feladat}
            t={tap.feladat_tapasztalat}
            javitasLink={`/admin-agent/forgatasok?forgatas=${projectId}`}
          />
          <div>
            <p className="font-medium text-text-primary">Hasonló korábbi forgatások ({tap.hasonlo_forgatasok.length})</p>
            {tap.hasonlo_forgatasok.length === 0 ? (
              <p className="text-text-muted">Nincs még hasonló forgatás a rendszerben.</p>
            ) : (
              <ul className="list-disc pl-5 text-text-secondary">
                {tap.hasonlo_forgatasok.slice(0, 6).map((h) => (
                  <li key={h.id}>
                    {h.nev} ({h.datum}) — {h.okok.join(", ")}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p className="font-medium text-text-primary">
              Javasolt technika ({tap.technika.tapasztalat_forgatasok} hasonló forgatás
              {tap.technika.feladat_forgatasok ? ` + ${tap.technika.feladat_forgatasok} ilyen feladatú forgatás` : ""} kivitt
              eszközei alapján)
            </p>
            {tap.technika.tetelek.length === 0 ? (
              <p className="text-text-muted">Nincs elég tapasztalat a technikai csomaghoz.</p>
            ) : (
              <ul className="list-disc pl-5 text-text-secondary">
                {tap.technika.tetelek.map((t) => (
                  <li key={t.equipment_id}>
                    {t.track_mode === "stock" ? `${t.qty} db ` : ""}
                    <span className="text-text-primary">{t.nev}</span>
                    {t.szerep ? ` — ${t.szerep}` : t.kategoria ? ` (${t.kategoria})` : ""}
                    {t.helyettesiti
                      ? ` · ${t.helyettesiti.nev} helyett${t.hasonlosag != null ? ` (${Math.round(t.hasonlosag * 100)}% hasonló)` : ""}`
                      : ""}
                    {t.gyakorisag ? ` · ${t.gyakorisag}` : ""}
                    {t.forras === "feladat" && (
                      <span className="ml-1 rounded bg-bg-accent px-1 text-[11px] text-text-accent">a feladatból</span>
                    )}
                    {t.mire_jo && <span className="block text-[12px] text-text-muted">{t.mire_jo}</span>}
                  </li>
                ))}
              </ul>
            )}
            {tap.technika.figyelmeztetesek.map((f, i) => (
              <p key={i} className="text-text-warning">
                {f}
              </p>
            ))}
          </div>
          <div>
            <p className="font-medium text-text-primary">
              Diszpó szövege a tapasztalatból ({tap.diszpo_szoveg.forras_diszpok} hasonló diszpó)
            </p>
            {Object.keys(tap.diszpo_szoveg.mezok).length === 0 ? (
              <p className="text-text-muted">Nincs elég kitöltött, hasonló diszpó - a sablon marad.</p>
            ) : (
              <ul className="list-disc pl-5 text-text-secondary">
                {Object.entries(tap.diszpo_szoveg.mezok).map(([k, v]) => (
                  <li key={k}>
                    <span className="text-text-primary">{k}: {v.ertek}</span> — {v.indoklas}
                  </li>
                ))}
              </ul>
            )}
            {tap.diszpo_szoveg.figyelmeztetesek.map((f, i) => (
              <p key={i} className="text-text-warning">
                {f}
              </p>
            ))}
          </div>
          {tap.visszatero_instrukciok.length > 0 && (
            <div>
              <p className="font-medium text-text-primary">Visszatérő brief-instrukciók</p>
              <ul className="list-disc pl-5 text-text-secondary">
                {tap.visszatero_instrukciok.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
