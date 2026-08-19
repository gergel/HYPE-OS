"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { ModalReteg } from "@/components/ModalReteg";
import { UjFajlValaszto } from "@/components/UjFajlValaszto";
import { toltsdFelAFajlokat } from "@/lib/csatolmany";
import type { KrumpelloNap } from "@/lib/api";

const MEZOK: { kulcs: keyof Ertekek; cimke: string; sugo?: string }[] = [
  { kulcs: "brutto_kp", cimke: "Bruttó bevétel – készpénz" },
  { kulcs: "brutto_kartya", cimke: "Bruttó bevétel – kártya" },
  { kulcs: "netto_kp", cimke: "Nettó bevétel – készpénz" },
  { kulcs: "netto_kartya", cimke: "Nettó bevétel – kártya" },
  { kulcs: "borravalo_kp", cimke: "Borravaló – készpénz", sugo: "A dolgozóké, nem árbevétel." },
  { kulcs: "borravalo_kartya", cimke: "Borravaló – kártya" },
  { kulcs: "extra", cimke: "Extra bevétel", sugo: "Amihez NINCS számla, ami megmagyarázná, honnan jött." },
];

type Ertekek = {
  brutto_kp: string;
  brutto_kartya: string;
  netto_kp: string;
  netto_kartya: string;
  borravalo_kp: string;
  borravalo_kartya: string;
  extra: string;
};

function ertekekbol(nap?: KrumpelloNap): Ertekek {
  const sz = (v: number | null | undefined) => (v == null ? "" : String(v));
  return {
    brutto_kp: sz(nap?.brutto_kp),
    brutto_kartya: sz(nap?.brutto_kartya),
    netto_kp: sz(nap?.netto_kp),
    netto_kartya: sz(nap?.netto_kartya),
    borravalo_kp: sz(nap?.borravalo_kp),
    borravalo_kartya: sz(nap?.borravalo_kartya),
    extra: sz(nap?.extra),
  };
}

/** Egy nap kassza-zárásának felvitele vagy javítása.
 *
 * Ugyanaz a komponens szolgálja mindkettőt, mert a backenden is ugyanaz a
 * művelet (PUT, dátum szerinti upsert): naponta egy zárás van, tehát a
 * "rögzítés" és a "javítás" ugyanaz a mozdulat. Két külön űrlap csak azt a
 * hamis érzetet keltené, hogy kétszer is fel lehet vinni ugyanazt a napot. */
export function NapSzerkeszto({ nap }: { nap?: KrumpelloNap }) {
  const [nyitva, setNyitva] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className={nap ? "text-[12.5px] text-text-accent hover:underline" : "btn btn-primary !text-[13px]"}
      >
        {nap ? "Szerkesztés" : "+ Új nap rögzítése"}
      </button>
      {/* Feltételes renderelés: minden megnyitás friss példány, üres űrlappal. */}
      {nyitva && <NapUrlap nap={nap} onBezar={() => setNyitva(false)} />}
    </>
  );
}

function NapUrlap({ nap, onBezar }: { nap?: KrumpelloNap; onBezar: () => void }) {
  const router = useRouter();
  const [datum, setDatum] = useState(nap?.datum ?? new Date().toISOString().slice(0, 10));
  const [ertekek, setErtekek] = useState<Ertekek>(() => ertekekbol(nap));
  const [megjegyzes, setMegjegyzes] = useState(nap?.megjegyzes ?? "");
  // A napi jelentés a zárás pillanatában van kéznél - ezért itt is
  // kiválasztható. Feltölteni csak mentés UTÁN lehet: a csatolmány végpontnak
  // kell a nap id-je (lásd lib/csatolmany.ts).
  const [ujFajlok, setUjFajlok] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function mentes() {
    if (!datum) {
      setHiba("Add meg a napot.");
      return;
    }
    setBusy(true);
    setHiba(null);
    try {
      // Az üres mező NULL-t jelent, nem nullát: a "nem írtam be" és a
      // "tényleg nulla volt" két különböző állítás.
      const szam = (v: string) => (v.trim() === "" ? null : Number(v));
      const res = await authFetch("/api/v1/krumpello/napok", {
        method: "PUT",
        body: JSON.stringify({
          datum,
          brutto_kp: szam(ertekek.brutto_kp),
          brutto_kartya: szam(ertekek.brutto_kartya),
          netto_kp: szam(ertekek.netto_kp),
          netto_kartya: szam(ertekek.netto_kartya),
          borravalo_kp: szam(ertekek.borravalo_kp),
          borravalo_kartya: szam(ertekek.borravalo_kartya),
          extra: szam(ertekek.extra),
          megjegyzes: megjegyzes.trim() || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      if (ujFajlok.length > 0) {
        const mentett = (await res.json().catch(() => null)) as { id?: number } | null;
        const id = mentett?.id ?? nap?.id;
        // A nap MÁR elmentve: ha a fájl nem megy fel, az ablak nyitva marad az
        // üzenettel, de a mentést nem vonjuk vissza - a sor mellől bármikor
        // újra megpróbálható.
        const fajlHiba = id ? await toltsdFelAFajlokat("krumpelloNap", id, ujFajlok) : null;
        if (fajlHiba) {
          setHiba(fajlHiba);
          setUjFajlok([]);
          router.refresh();
          return;
        }
      }
      onBezar();
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  const mezoClass =
    "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

  return (
    <ModalReteg onClose={busy ? undefined : onBezar}>
      <div
        role="dialog"
        aria-modal="true"
        className="krumpello-root w-full max-w-lg rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">
            {nap ? `Nap javítása – ${nap.datum}` : "Új nap rögzítése"}
          </h3>
          <p className="mt-0.5 text-[12px] text-text-muted">
            Ha erre a napra már van zárás, ez felülírja. Az üresen hagyott mező „nincs megadva”, nem nulla.
          </p>
        </div>

        <div className="max-h-[65vh] overflow-y-auto p-5">
          {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}
          <div className="mb-4 flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Nap *</label>
            <input
              type="date"
              value={datum}
              onChange={(e) => setDatum(e.target.value)}
              disabled={busy || !!nap}
              className={mezoClass}
            />
            {nap && <p className="text-[11px] text-text-muted">A nap dátuma nem módosítható – töröld és vidd fel újra.</p>}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {MEZOK.map((m) => (
              <div key={m.kulcs} className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">{m.cimke}</label>
                <input
                  type="number"
                  value={ertekek[m.kulcs]}
                  onChange={(e) => setErtekek((elozo) => ({ ...elozo, [m.kulcs]: e.target.value }))}
                  disabled={busy}
                  className={mezoClass}
                />
                {m.sugo && <p className="text-[11px] text-text-muted">{m.sugo}</p>}
              </div>
            ))}
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label className="text-[11px] text-text-muted">Megjegyzés</label>
              <input
                value={megjegyzes}
                onChange={(e) => setMegjegyzes(e.target.value)}
                disabled={busy}
                className={mezoClass}
              />
            </div>
            <div className="sm:col-span-2">
              <UjFajlValaszto fajlok={ujFajlok} onValtozas={setUjFajlok} cimke="Számla / bizonylat" disabled={busy} />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-5 py-3">
          <button type="button" onClick={onBezar} disabled={busy} className="btn btn-ghost">
            Mégse
          </button>
          <button type="button" onClick={mentes} disabled={busy} className="btn btn-primary">
            {busy ? "Mentés…" : "Mentés"}
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
