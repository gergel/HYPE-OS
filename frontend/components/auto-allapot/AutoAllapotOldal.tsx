"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Camera, Check, Copy, Link2, Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { vagolapra } from "@/lib/vagolap";
import { AutoKorvonal, reszCimke, type Karosszeria } from "@/components/auto-allapot/AutoKorvonal";
import { FotoNezo, type NezettFoto } from "@/components/auto-allapot/FotoNezo";

type Foto = { id: number; oldal: string; keszult_at: string; keszito: string | null; url: string; belyeg_url: string };
type Bekeres = { id: number; token: string; letrejott_at: string; visszavonva_at: string | null; mai_db: number };
/** Egy nap egy fotózási köre (egy link aznapi képei). */
type Nap = { datum: string; bekeres_id: number | null; kezdet: string; fotok: Record<string, Foto>; db: number; osszes: number };
type Allapot = {
  auto: {
    id: number;
    rendszam: string;
    megnevezes: string | null;
    tipus: string | null;
    karosszeria: Karosszeria;
    karosszeria_beallitva: boolean;
  };
  karosszeriak: Record<Karosszeria, string>;
  oldalak: { kulcs: string; cimke: string }[];
  bekeresek: Bekeres[];
  napok: Nap[];
};

const API = "/api/v1/autok";

function napCimke(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("hu-HU", { year: "numeric", month: "long", day: "numeric", weekday: "long" });
}

function idopont(iso: string): string {
  return new Date(iso).toLocaleString("hu-HU", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** Egy autó ÁLLAPOT OLDALA (a felhasználó kérése): az állapotfotók napról
 * napra (melyik nap melyik nézetről készült kép), és a bekérő linkek.
 *
 * TESZT JELLEG: a bekérő linket kézzel kell kiküldeni - a diszpóval nem megy
 * ki automatikusan. */
export function AutoAllapotOldal({ autoId }: { autoId: number }) {
  const [adat, setAdat] = useState<Allapot | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [masolva, setMasolva] = useState<number | null>(null);
  const [regiLinkek, setRegiLinkek] = useState(false);
  /** Az épp létrehozott link (kiemelve, és automatikusan kimásolva). */
  const [ujLinkId, setUjLinkId] = useState<number | null>(null);
  /** A felugró képnéző: az adott kör képei, és melyik látszik. */
  const [nezo, setNezo] = useState<{ fotok: NezettFoto[]; index: number } | null>(null);

  const betolt = useCallback(() => {
    authFetch(`${API}/${autoId}/allapot`)
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (!r.ok) throw new Error(typeof d?.detail === "string" ? d.detail : `HTTP ${r.status}`);
        setAdat(d as Allapot);
        setHiba(null);
      })
      .catch((e) => setHiba(String(e?.message ?? e)));
  }, [autoId]);

  useEffect(() => {
    betolt();
  }, [betolt]);

  async function hivas(url: string, method: string, hibaCimke: string): Promise<boolean> {
    setBusy(true);
    try {
      const r = await authFetch(url, { method });
      if (!r.ok) {
        const d = await r.json().catch(() => null);
        alert(`${hibaCimke}: ${d?.detail ?? r.status}`);
        return false;
      }
      betolt();
      return true;
    } finally {
      setBusy(false);
    }
  }

  function linkje(b: Bekeres): string {
    return `${window.location.origin}/auto-allapot/${b.token}`;
  }

  async function masol(b: Bekeres) {
    if (await vagolapra(linkje(b))) {
      setMasolva(b.id);
      setTimeout(() => setMasolva(null), 1500);
    }
  }

  /** Új link = új fotózási kör: üresen indul, a korábbi élő link lezárul
   * (a képei megmaradnak). Az új link rögtön a vágólapra kerül. */
  async function ujLink() {
    setBusy(true);
    try {
      const r = await authFetch(`${API}/${autoId}/allapot/bekeres`, { method: "POST" });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        alert(`Nem sikerült: ${d?.detail ?? r.status}`);
        return;
      }
      setUjLinkId(d.id);
      betolt();
      if (await vagolapra(linkje(d as Bekeres))) {
        setMasolva(d.id);
        setTimeout(() => setMasolva(null), 2500);
      }
    } finally {
      setBusy(false);
    }
  }

  if (hiba && !adat) {
    return <p className="text-[13.5px] text-text-danger">Nem sikerült betölteni: {hiba}</p>;
  }
  if (!adat) return <p className="text-[13px] text-text-muted">Betöltés…</p>;

  const kar = adat.auto.karosszeria;
  const cimke = (o: { kulcs: string; cimke: string }) => reszCimke(o.kulcs, kar, o.cimke);

  async function karosszeriaMentes(ertek: string) {
    setBusy(true);
    try {
      const r = await authFetch(`${API}/${autoId}/karosszeria`, {
        method: "PUT",
        body: JSON.stringify({ karosszeria: ertek || null }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => null);
        alert(`Nem sikerült: ${d?.detail ?? r.status}`);
        return;
      }
      betolt();
    } finally {
      setBusy(false);
    }
  }

  /** Egy kör képeinek megnyitása a felugró nézőben (a kattintott képnél). */
  function megnyit(n: Nap, fotoId: number) {
    const fotok = adat!.oldalak.flatMap((o) => {
      const f = n.fotok[o.kulcs];
      if (!f) return [];
      const ido = new Date(f.keszult_at).toLocaleString("hu-HU", {
        month: "long", day: "numeric", hour: "2-digit", minute: "2-digit",
      });
      return [{ id: f.id, url: f.url, cimke: cimke(o), alcim: `${ido}${f.keszito ? ` · ${f.keszito}` : ""}` }];
    });
    setNezo({ fotok, index: Math.max(0, fotok.findIndex((f) => f.id === fotoId)) });
  }

  const elok = adat.bekeresek.filter((b) => !b.visszavonva_at);
  const visszavontak = adat.bekeresek.filter((b) => b.visszavonva_at);

  return (
    <div className="space-y-6">
      <div>
        <Link href="/autok" className="mb-2 inline-flex items-center gap-1 text-[12.5px] text-text-muted hover:text-text-primary">
          <ArrowLeft size={13} /> Autók
        </Link>
        <h1 className="text-[22px] font-semibold text-text-primary">
          {adat.auto.rendszam} – állapotfotók
        </h1>
        {(adat.auto.megnevezes || adat.auto.tipus) && (
          <p className="text-[13px] text-text-muted">{adat.auto.megnevezes || adat.auto.tipus}</p>
        )}
        {/* A fotózáskor ennek az autónak a KÖRVONALÁN kell kiválasztani a
            részt (a felhasználó kérése) - a forma a karosszériától függ. */}
        <label className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px] text-text-muted">
          Karosszéria (a fotózási körvonalhoz):
          <select
            value={adat.auto.karosszeria_beallitva ? kar : ""}
            disabled={busy}
            onChange={(e) => void karosszeriaMentes(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary"
          >
            <option value="">Automatikus (a típusnévből: {adat.karosszeriak[kar]})</option>
            {Object.entries(adat.karosszeriak).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* BEKÉRŐ LINK - teszt jelleggel kézzel kiküldve. */}
      <section className="space-y-3 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[14px] font-medium text-text-primary">Bekérő link</p>
            <p className="text-[12.5px] text-text-muted">
              Aki megkapja, bejelentkezés nélkül feltöltheti a {adat.oldalak.length} képet. Minden új link új fotózási
              kör: üresen indul, a korábbi link pedig lezárul (a képei megmaradnak). Egyelőre teszt: a linket kézzel
              küldd ki – a diszpóval nem megy ki automatikusan.
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void ujLink()}
            className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            <Link2 size={14} /> Új bekérő link
          </button>
        </div>
        {elok.length === 0 ? (
          <p className="text-[12.5px] text-text-muted">Nincs élő bekérő link.</p>
        ) : (
          <ul className="space-y-2">
            {elok.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-1 px-3 py-2">
                <code className="min-w-0 flex-1 truncate text-[12.5px] text-text-secondary">{linkje(b)}</code>
                {b.id === ujLinkId && (
                  <span className="rounded-full bg-surface-3 px-2 py-0.5 text-[11.5px] font-medium text-text-success">
                    Új link{masolva === b.id ? " – kimásolva" : ""}
                  </span>
                )}
                <span className="text-[12px] text-text-muted">Ma: {b.mai_db} / {adat.oldalak.length}</span>
                <button
                  type="button"
                  onClick={() => void masol(b)}
                  className="flex items-center gap-1 rounded-[var(--radius)] border border-border px-2 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3"
                >
                  {masolva === b.id ? <Check size={13} className="text-text-success" /> : <Copy size={13} />}
                  {masolva === b.id ? "Másolva" : "Másolás"}
                </button>
                <a
                  href={linkje(b)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3"
                >
                  Megnyitás
                </a>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm("Visszavonod ezt a linket? Utána nem lehet vele feltölteni (a képek megmaradnak)."))
                      void hivas(`${API}/${autoId}/allapot/bekeres/${b.id}`, "DELETE", "Nem sikerült");
                  }}
                  className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                >
                  Visszavonás
                </button>
              </li>
            ))}
          </ul>
        )}
        {visszavontak.length > 0 && (
          <button type="button" onClick={() => setRegiLinkek((n) => !n)} className="text-[12px] text-text-muted hover:underline">
            {regiLinkek ? "Visszavont linkek elrejtése" : `Visszavont linkek (${visszavontak.length})`}
          </button>
        )}
        {regiLinkek && (
          <ul className="space-y-1 text-[12px] text-text-muted">
            {visszavontak.map((b) => (
              <li key={b.id}>
                Létrehozva: {idopont(b.letrejott_at)} · visszavonva: {idopont(b.visszavonva_at!)}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ÁLLAPOT NAPRÓL NAPRA */}
      <section className="space-y-4">
        <p className="text-[14px] font-medium text-text-primary">Állapot napról napra</p>
        {adat.napok.length === 0 && (
          <p className="rounded-[var(--radius)] border border-border bg-surface-2 px-4 py-6 text-center text-[13px] text-text-muted">
            Még nem készült állapotfotó erről az autóról.
          </p>
        )}
        {adat.napok.map((n) => (
          <div key={`${n.datum}-${n.bekeres_id ?? "x"}`} className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <AutoKorvonal
                  karosszeria={kar}
                  kesz={Object.fromEntries(Object.keys(n.fotok).map((o) => [o, true]))}
                  cimkek={false}
                  className="w-[38px] shrink-0"
                />
                <p className="text-[14px] font-medium text-text-primary">
                  {napCimke(n.datum)}
                  {/* Ha aznap több fotózási kör (link) is volt, a kezdésük különbözteti meg őket. */}
                  {adat.napok.filter((m) => m.datum === n.datum).length > 1 && (
                    <span className="ml-2 text-[12.5px] font-normal text-text-muted">
                      {new Date(n.kezdet).toLocaleTimeString("hu-HU", { hour: "2-digit", minute: "2-digit" })}-kor kezdett kör
                    </span>
                  )}
                </p>
              </div>
              <span className={`text-[12.5px] ${n.db === n.osszes ? "text-text-success" : "text-text-warning"}`}>
                {n.db === n.osszes ? `Mind a ${n.osszes} kép megvan` : `${n.db} / ${n.osszes} kép`}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
              {adat.oldalak.map((o) => {
                const f = n.fotok[o.kulcs];
                return (
                  <figure key={o.kulcs} className="overflow-hidden rounded-[var(--radius)] border border-border bg-surface-1">
                    {f ? (
                      <button
                        type="button"
                        onClick={() => megnyit(n, f.id)}
                        title="Megnyitás nagyban"
                        className="block w-full cursor-zoom-in"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={f.belyeg_url} alt={cimke(o)} className="aspect-[4/3] w-full object-cover" />
                      </button>
                    ) : (
                      <div className="flex aspect-[4/3] items-center justify-center bg-surface-3 text-text-muted">
                        <Camera size={18} />
                      </div>
                    )}
                    <figcaption className="space-y-0.5 px-2 py-1.5">
                      <p className="text-[12.5px] font-medium text-text-primary">{cimke(o)}</p>
                      {f ? (
                        <div className="flex items-center justify-between gap-1 text-[11px] text-text-muted">
                          <span className="truncate">
                            {new Date(f.keszult_at).toLocaleTimeString("hu-HU", { hour: "2-digit", minute: "2-digit" })}
                            {f.keszito ? ` · ${f.keszito}` : ""}
                          </span>
                          <button
                            type="button"
                            disabled={busy}
                            title="Kép törlése"
                            aria-label={`${o.cimke} képének törlése`}
                            onClick={() => {
                              if (window.confirm(`Törlöd ezt a képet (${o.cimke}, ${n.datum})?`))
                                void hivas(`${API}/${autoId}/allapot/fotok/${f.id}`, "DELETE", "Nem sikerült törölni");
                            }}
                            className="shrink-0 rounded p-0.5 hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ) : (
                        <p className="text-[11px] text-text-warning">Nem készült kép</p>
                      )}
                    </figcaption>
                  </figure>
                );
              })}
            </div>
          </div>
        ))}
      </section>

      {nezo && (
        <FotoNezo
          fotok={nezo.fotok}
          index={nezo.index}
          onLapoz={(index) => setNezo({ ...nezo, index })}
          onBezar={() => setNezo(null)}
        />
      )}
    </div>
  );
}
