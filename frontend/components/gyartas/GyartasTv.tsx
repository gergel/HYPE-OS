"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";
import type { GyartasTv as Adat, TvEmber, TvForgatas, TvVagas } from "@/lib/api";

/** GYÁRTÁS-TV (kliens) — a gyártási szoba TV-je.
 *
 * ÉLŐ: 10 másodpercenként a háttérben újra lekéri az adatot (a képernyő nem
 * villan, csak a változás látszik), óránként pedig az egész oldalt újratölti,
 * hogy a munkamenet megújuljon és az új verzió is felkerüljön. A képernyőt
 * ébren tartja (Wake Lock), a túl hosszú oszlopok lassan maguktól görögnek.
 * Hálózati hibánál a legutóbbi adat marad kint, és jelzi, hogy újrapróbálja. */

const FRISSITES_MS = 10_000;
const OLDAL_UJRATOLTES_MS = 60 * 60 * 1000;

const OSZLOPOK: { kulcs: keyof Adat["vagasok"]; cim: string; al: string; szin: string }[] = [
  { kulcs: "vagas", cim: "Épp vágják", al: "ki mit vág", szin: "#4f8cff" },
  { kulcs: "ellenorzes", cim: "Ellenőrzésen", al: "beérkező, ellenőrzés", szin: "#b07cff" },
  { kulcs: "kikuldheto", cim: "Kiküldhető", al: "mehet a megrendelőnek", szin: "#3fbf7f" },
  { kulcs: "gyartasra_var", cim: "Gyártásra vár", al: "válasz kell tőlünk", szin: "#f0a53a" },
];

const HONAP = ["jan.", "febr.", "márc.", "ápr.", "máj.", "jún.", "júl.", "aug.", "szept.", "okt.", "nov.", "dec."];

function datumRovid(iso: string | null): string {
  if (!iso) return "";
  const [, h, n] = iso.split("-").map(Number);
  return `${HONAP[h - 1]} ${n}.`;
}

function hetSzama(d: Date): number {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const nap = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - nap);
  const ev = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil(((t.getTime() - ev.getTime()) / 86400000 + 1) / 7);
}

function mennyiIdeje(iso: string | null, most: number): string | null {
  if (!iso) return null;
  const perc = Math.max(0, Math.round((most - new Date(iso).getTime()) / 60000));
  if (perc < 60) return `${perc} perce`;
  const ora = Math.round(perc / 60);
  if (ora < 24) return `${ora} órája`;
  return `${Math.round(ora / 24)} napja`;
}

export function GyartasTv({ kezdo }: { kezdo: Adat | null }) {
  const [adat, setAdat] = useState<Adat | null>(kezdo);
  const [frissitve, setFrissitve] = useState<number>(() => Date.now());
  const [hiba, setHiba] = useState<"halozat" | "lejart" | null>(null);
  const [most, setMost] = useState<number>(() => Date.now());
  const [egerMozog, setEgerMozog] = useState(false);

  // Mindig sötét: a TV-n a világos téma vakítana.
  useEffect(() => {
    const html = document.documentElement;
    const regi = html.dataset.theme;
    html.dataset.theme = "dark";
    return () => {
      if (regi) html.dataset.theme = regi;
    };
  }, []);

  const lekeres = useCallback(async () => {
    try {
      const res = await authFetch("/api/v1/gyartas/tv", { cache: "no-store" });
      if (res.status === 401) {
        setHiba("lejart");
        return;
      }
      if (!res.ok) throw new Error(String(res.status));
      setAdat((await res.json()) as Adat);
      setFrissitve(Date.now());
      setHiba(null);
    } catch {
      setHiba("halozat");
    }
  }, []);

  useEffect(() => {
    const t = setInterval(lekeres, FRISSITES_MS);
    const ora = setInterval(() => setMost(Date.now()), 1000);
    const ujra = setTimeout(() => window.location.reload(), OLDAL_UJRATOLTES_MS);
    return () => {
      clearInterval(t);
      clearInterval(ora);
      clearTimeout(ujra);
    };
  }, [lekeres]);

  // A képernyő ne aludjon el (ahol a böngésző támogatja).
  useEffect(() => {
    let zar: { release: () => Promise<void> } | null = null;
    const ker = async () => {
      try {
        const nav = navigator as Navigator & { wakeLock?: { request: (t: "screen") => Promise<{ release: () => Promise<void> }> } };
        if (nav.wakeLock && document.visibilityState === "visible") zar = await nav.wakeLock.request("screen");
      } catch {
        /* nem támogatott / nem engedélyezett — nem baj */
      }
    };
    void ker();
    document.addEventListener("visibilitychange", ker);
    return () => {
      document.removeEventListener("visibilitychange", ker);
      void zar?.release().catch(() => undefined);
    };
  }, []);

  // Egérmozgásra előjön a vezérlés (teljes képernyő, vissza), utána eltűnik a kurzorral együtt.
  useEffect(() => {
    let t: ReturnType<typeof setTimeout> | undefined;
    const mozog = () => {
      setEgerMozog(true);
      clearTimeout(t);
      t = setTimeout(() => setEgerMozog(false), 3000);
    };
    window.addEventListener("mousemove", mozog);
    return () => {
      window.removeEventListener("mousemove", mozog);
      clearTimeout(t);
    };
  }, []);

  const d = new Date(most);
  const maiDatum = d.toLocaleDateString("hu-HU", { year: "numeric", month: "long", day: "numeric", weekday: "long" });
  const ora = d.toLocaleTimeString("hu-HU", { hour: "2-digit", minute: "2-digit" });
  const mp = String(d.getSeconds()).padStart(2, "0");
  const kesesMp = Math.round((most - frissitve) / 1000);

  return (
    <div
      className={`flex h-screen flex-col gap-[1.4vh] bg-[var(--bg,#0b0c0f)] px-[1.4vw] py-[1.6vh] text-text-primary ${
        egerMozog ? "" : "cursor-none"
      }`}
      style={{ fontSize: "clamp(13px, 0.95vw, 30px)" }}
    >
      {/* FEJLÉC */}
      <header className="flex items-end justify-between gap-[2vw]">
        <div>
          <p className="text-[0.8em] uppercase tracking-[0.28em] text-text-muted">
            HYPE · Gyártás <span className="text-text-muted/70">· {hetSzama(d)}. hét</span>
          </p>
          <p className="text-[1.9em] font-semibold leading-tight tracking-[-0.01em]">{maiDatum}</p>
        </div>
        {adat && (
          <div className="flex flex-wrap items-center justify-center gap-[0.8vw] text-[0.95em]">
            <Osszeg szam={adat.osszesito.forgatas_a_heten ?? 0} cim="forgatás a héten" />
            {OSZLOPOK.map((o) => (
              <Osszeg key={o.kulcs} szam={adat.vagasok[o.kulcs].length} cim={o.cim.toLowerCase()} szin={o.szin} />
            ))}
          </div>
        )}
        <div className="text-right">
          <p className="font-mono text-[2.6em] font-medium leading-none tabular-nums">
            {ora}
            <span className="text-[0.45em] text-text-muted">:{mp}</span>
          </p>
          <p className="mt-[0.4vh] flex items-center justify-end gap-[0.4em] text-[0.8em] text-text-muted">
            {hiba === "halozat" ? (
              <>
                <span className="inline-block h-[0.6em] w-[0.6em] rounded-full bg-[#f0a53a]" /> Kapcsolat megszakadt —
                újrapróbálom
              </>
            ) : (
              <>
                <span className="inline-block h-[0.6em] w-[0.6em] animate-pulse rounded-full bg-[#3fbf7f]" /> Élő ·
                frissítve {kesesMp < 5 ? "most" : `${kesesMp} mp-e`}
              </>
            )}
          </p>
        </div>
      </header>

      {hiba === "lejart" && (
        <div className="rounded-[var(--radius)] bg-bg-danger px-4 py-3 text-[1.1em] text-text-danger">
          A bejelentkezés lejárt ezen a képernyőn.{" "}
          <Link href="/login?next=/gyartas" className="underline">
            Jelentkezz be újra
          </Link>
          , és a Gyártás oldal utána magától fut tovább.
        </div>
      )}

      {!adat ? (
        <p className="text-[1.3em] text-text-secondary">Az adatok most nem érhetők el — újrapróbálom…</p>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[32%_1fr] gap-[1.2vw]">
          {/* A HÉT FORGATÁSAI */}
          <section className="flex min-h-0 flex-col rounded-[1.2vh] border border-border bg-surface-2 p-[1.4vh_1vw]">
            <div className="mb-[1vh] flex items-baseline justify-between">
              <h2 className="text-[1.35em] font-semibold">A héten</h2>
              <span className="text-[0.85em] text-text-muted">
                {datumRovid(adat.het.tol)} – {datumRovid(adat.het.ig)}
              </span>
            </div>
            {adat.ma_forgat.length > 0 && (
              <div className="mb-[1vh] rounded-[0.8vh] bg-surface-3 px-[0.8vw] py-[0.8vh]">
                <p className="mb-[0.4vh] text-[0.8em] uppercase tracking-[0.14em] text-text-muted">Ma forgat</p>
                <Emberek emberek={adat.ma_forgat} />
              </div>
            )}
            <AutoGorgeto>
              <ul className="flex flex-col gap-[1vh]">
                {adat.napok.map((n) => (
                  <li
                    key={n.datum}
                    className={`rounded-[0.8vh] border px-[0.8vw] py-[0.9vh] ${
                      n.ma ? "border-[#4f8cff] bg-[#4f8cff]/10" : "border-border"
                    } ${n.multbeli ? "opacity-45" : ""}`}
                  >
                    <p className="flex items-baseline justify-between">
                      <span className={`text-[1.1em] font-semibold ${n.ma ? "text-[#8fb5ff]" : ""}`}>
                        {n.nev}
                        {n.ma ? " · ma" : ""}
                      </span>
                      <span className="text-[0.85em] text-text-muted">{datumRovid(n.datum)}</span>
                    </p>
                    {n.forgatasok.length === 0 ? (
                      <p className="mt-[0.3vh] text-[0.9em] text-text-muted">nincs forgatás</p>
                    ) : (
                      <ul className="mt-[0.6vh] flex flex-col gap-[0.8vh]">
                        {n.forgatasok.map((f) => (
                          <Forgatas key={`${n.datum}-${f.id}`} f={f} tomor={n.multbeli} />
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </AutoGorgeto>
          </section>

          {/* VÁGÁSOK */}
          <section className="flex min-h-0 flex-col gap-[1.2vh]">
            {adat.most_vag.length > 0 && (
              <div className="flex flex-wrap items-center gap-[0.6vw] rounded-[1.2vh] border border-border bg-surface-2 px-[1vw] py-[1vh]">
                <span className="text-[0.8em] uppercase tracking-[0.14em] text-text-muted">Most vág</span>
                {adat.most_vag.map((e) => (
                  <span key={e.id} className="flex items-center gap-[0.4em] text-[1em]">
                    <Pont szin={e.szin} el />
                    <b className="font-semibold">{e.nev}</b>
                    <span className="text-text-secondary">— {e.projekt}</span>
                  </span>
                ))}
              </div>
            )}
            <div className="grid min-h-0 flex-1 grid-cols-4 gap-[0.9vw]">
              {OSZLOPOK.map((o) => (
                <div key={o.kulcs} className="flex min-h-0 flex-col rounded-[1.2vh] border border-border bg-surface-2">
                  <div className="border-b border-border px-[0.8vw] py-[1vh]" style={{ boxShadow: `inset 0 3px 0 ${o.szin}` }}>
                    <p className="flex items-baseline justify-between">
                      <span className="text-[1.2em] font-semibold">{o.cim}</span>
                      <span className="font-mono text-[1.4em] tabular-nums" style={{ color: o.szin }}>
                        {adat.vagasok[o.kulcs].length}
                      </span>
                    </p>
                    <p className="text-[0.8em] text-text-muted">{o.al}</p>
                  </div>
                  <AutoGorgeto>
                    <ul className="flex flex-col gap-[0.8vh] p-[0.8vh_0.6vw]">
                      {adat.vagasok[o.kulcs].length === 0 && (
                        <li className="px-[0.3vw] py-[1vh] text-[0.95em] text-text-muted">nincs ilyen anyag</li>
                      )}
                      {adat.vagasok[o.kulcs].map((v) => (
                        <Vagas key={v.id} v={v} oszlop={o.kulcs} most={most} />
                      ))}
                    </ul>
                  </AutoGorgeto>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {egerMozog && (
        <div className="fixed bottom-[2vh] right-[1.4vw] flex gap-2 text-[13px]">
          <Link href="/dashboard" className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-text-secondary">
            ← Vissza a HYPE OS-be
          </Link>
          <button
            type="button"
            onClick={() =>
              document.fullscreenElement ? void document.exitFullscreen() : void document.documentElement.requestFullscreen()
            }
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 font-medium text-text-accent"
          >
            Teljes képernyő
          </button>
        </div>
      )}
    </div>
  );
}

function Osszeg({ szam, cim, szin }: { szam: number; cim: string; szin?: string }) {
  return (
    <span className="rounded-full border border-border px-[0.9em] py-[0.25em] text-text-secondary">
      <b className="font-mono tabular-nums" style={szin ? { color: szin } : undefined}>
        {szam}
      </b>{" "}
      {cim}
    </span>
  );
}

function Pont({ szin, el }: { szin: string | null; el?: boolean }) {
  return (
    <span
      className={`inline-block h-[0.65em] w-[0.65em] shrink-0 rounded-full ${el ? "animate-pulse" : ""}`}
      style={{ background: szin || "#7a808c" }}
    />
  );
}

function Emberek({ emberek, kicsi }: { emberek: TvEmber[]; kicsi?: boolean }) {
  return (
    <span className={`flex flex-wrap gap-x-[0.8em] gap-y-[0.2em] ${kicsi ? "text-[0.88em]" : "text-[1em]"}`}>
      {emberek.map((e) => (
        <span key={e.id} className="inline-flex items-center gap-[0.35em] text-text-primary">
          <Pont szin={e.szin} />
          {e.nev}
        </span>
      ))}
    </span>
  );
}

function Forgatas({ f, tomor }: { f: TvForgatas; tomor?: boolean }) {
  const ido = f.kezdes ? `${f.kezdes}${f.veg ? `–${f.veg}` : ""}` : null;
  return (
    <li className={`border-l-2 pl-[0.6vw] ${f.meeting ? "border-[#b07cff]" : "border-[#4f8cff]"}`}>
      <p className="text-[1.02em] font-medium leading-snug">
        {ido && <span className="mr-[0.4em] font-mono text-[0.9em] text-text-secondary">{ido}</span>}
        {f.nev}
        {f.meeting && <span className="ml-[0.4em] text-[0.8em] text-[#c4a3ff]">meeting</span>}
      </p>
      {!tomor && (
      <p className="text-[0.85em] text-text-muted">
        {[f.projektkod, f.megrendelo, f.helyszin].filter(Boolean).join(" · ")}
        {f.datum_vege && f.datum_vege !== f.datum ? ` · ${datumRovid(f.datum)}–${datumRovid(f.datum_vege)}` : ""}
      </p>
      )}
      {!tomor && f.stab.length > 0 && (
        <div className="mt-[0.3vh]">
          <Emberek emberek={f.stab} kicsi />
        </div>
      )}
    </li>
  );
}

function Vagas({ v, oszlop, most }: { v: TvVagas; oszlop: string; most: number }) {
  const var_ = oszlop === "gyartasra_var" ? mennyiIdeje(v.ota, most) : null;
  return (
    <li
      className={`rounded-[0.8vh] border bg-surface-3 px-[0.7vw] py-[0.9vh] ${
        v.fut.length ? "border-[#4f8cff]" : v.kesik ? "border-[#e5484d]/70" : "border-border"
      }`}
    >
      <p className="text-[1.02em] font-semibold leading-snug">
        {v.prioritas && <span className="mr-[0.3em] text-[#f0a53a]">★</span>}
        {v.projekt}
      </p>
      <p className="mt-[0.2vh] flex flex-wrap items-center gap-x-[0.5em] text-[0.82em] text-text-muted">
        {v.projektkod && <span>{v.projektkod}</span>}
        {v.allapot && (
          <span
            className="rounded-full px-[0.6em] py-[0.05em] text-text-secondary"
            style={{ background: v.szin ? `${v.szin}33` : "rgba(255,255,255,0.06)" }}
          >
            {v.allapot}
          </span>
        )}
      </p>
      {v.emberek.length > 0 && (
        <div className="mt-[0.4vh]">
          <Emberek emberek={v.emberek} kicsi />
        </div>
      )}
      {v.fut.length > 0 && (
        <p className="mt-[0.3vh] text-[0.85em] font-medium text-[#8fb5ff]">
          ● most dolgozik rajta: {v.fut.map((e) => e.nev).join(", ")}
        </p>
      )}
      {(v.hatarido || var_) && (
        <p className={`mt-[0.3vh] text-[0.82em] ${v.kesik ? "font-semibold text-[#ff8a8e]" : "text-text-muted"}`}>
          {var_ ? `vár ${var_}` : ""}
          {var_ && v.hatarido ? " · " : ""}
          {v.hatarido ? `határidő: ${datumRovid(v.hatarido)}${v.kesik ? " — lejárt" : ""}` : ""}
        </p>
      )}
    </li>
  );
}

/** Ha a tartalom nem fér ki, lassan legörget az aljára, ott megáll, majd
 * visszaugrik a tetejére — a TV-t senki nem görgeti kézzel. */
function AutoGorgeto({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    let utolso = performance.now();
    let varakozas = 4000;
    let irany: "le" | "fel" = "le";
    const lep = (t: number) => {
      const dt = t - utolso;
      utolso = t;
      const tulfolyik = el.scrollHeight - el.clientHeight > 4;
      if (!tulfolyik) {
        el.scrollTop = 0;
      } else if (varakozas > 0) {
        varakozas -= dt;
      } else if (irany === "le") {
        el.scrollTop += (dt / 1000) * 28;
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - 1) {
          irany = "fel";
          varakozas = 5000;
        }
      } else {
        el.scrollTo({ top: 0, behavior: "smooth" });
        irany = "le";
        varakozas = 6000;
      }
      raf = requestAnimationFrame(lep);
    };
    raf = requestAnimationFrame(lep);
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <div ref={ref} className="min-h-0 flex-1 overflow-hidden">
      {children}
    </div>
  );
}
