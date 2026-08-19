"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { ModalReteg } from "@/components/ModalReteg";
import { useConfirm } from "@/components/ConfirmProvider";
import { KeresosSelect } from "@/components/KeresosSelect";
import { UjFajlValaszto } from "@/components/UjFajlValaszto";
import { toltsdFelAFajlokat } from "@/lib/csatolmany";
import type { KrumpelloForras, KrumpelloKiadas } from "@/lib/api";

const FORRAS_CIMKEK: { value: KrumpelloForras; label: string; sublabel: string }[] = [
  { value: "utalas", label: "Utalás / bankkártya", sublabel: "A bankszámláról megy ki" },
  { value: "keszpenz", label: "Készpénz", sublabel: "A kasszából megy ki" },
  { value: "extra", label: "Extra – nincs hozzá számla", sublabel: "Nincs számla, ami megmagyarázná" },
];

/** Egy kiadás felvitele, javítása és törlése. */
export function KiadasSzerkeszto({ kiadas }: { kiadas?: KrumpelloKiadas }) {
  const [nyitva, setNyitva] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className={kiadas ? "text-[12.5px] text-text-accent hover:underline" : "btn btn-primary !text-[13px]"}
      >
        {kiadas ? "Szerkesztés" : "+ Új kiadás"}
      </button>
      {nyitva && <KiadasUrlap kiadas={kiadas} onBezar={() => setNyitva(false)} />}
    </>
  );
}

function KiadasUrlap({ kiadas, onBezar }: { kiadas?: KrumpelloKiadas; onBezar: () => void }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [forras, setForras] = useState<KrumpelloForras>(kiadas?.forras ?? "utalas");
  const [kedvezmenyezett, setKedvezmenyezett] = useState(kiadas?.kedvezmenyezett ?? "");
  const [datum, setDatum] = useState(kiadas?.datum ?? "");
  const [megnevezes, setMegnevezes] = useState(kiadas?.megnevezes ?? "");
  const [netto, setNetto] = useState(kiadas?.netto != null ? String(kiadas.netto) : "");
  const [afa, setAfa] = useState(kiadas?.afa != null ? String(kiadas.afa) : "");
  const [brutto, setBrutto] = useState(kiadas?.brutto != null ? String(kiadas.brutto) : "");
  const [megjegyzes, setMegjegyzes] = useState(kiadas?.megjegyzes ?? "");
  // A számla akkor van kéznél, amikor a tételt felvezetik - ezért itt is
  // kiválasztható. Feltölteni viszont csak mentés UTÁN lehet: a csatolmány
  // végpontnak kell a tétel id-je (lásd lib/csatolmany.ts).
  const [ujFajlok, setUjFajlok] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  // Az extránál nincs számla, tehát nincs miből nettót és áfát olvasni -
  // egyetlen összeg van. A mezők elrejtése itt nem kényelmi kérdés: kitöltve
  // azt sugallnák, hogy van mögötte bizonylat.
  const extra = forras === "extra";

  async function mentes() {
    if (!kedvezmenyezett.trim()) {
      setHiba("Add meg, kinek fizettünk.");
      return;
    }
    setBusy(true);
    setHiba(null);
    const szam = (v: string) => (v.trim() === "" ? null : Number(v));
    try {
      const res = await authFetch(
        kiadas ? `/api/v1/krumpello/kiadasok/${kiadas.id}` : "/api/v1/krumpello/kiadasok",
        {
          method: kiadas ? "PATCH" : "POST",
          body: JSON.stringify({
            forras,
            kedvezmenyezett: kedvezmenyezett.trim(),
            datum: datum || null,
            megnevezes: megnevezes.trim() || null,
            netto: extra ? null : szam(netto),
            afa: extra ? null : szam(afa),
            brutto: szam(brutto),
            megjegyzes: megjegyzes.trim() || null,
          }),
        },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      if (ujFajlok.length > 0) {
        const mentett = (await res.json().catch(() => null)) as { id?: number } | null;
        const id = mentett?.id ?? kiadas?.id;
        // A tétel MÁR elmentve: ha a fájl nem megy fel, az ablak nyitva marad
        // az üzenettel, de a mentést nem vonjuk vissza - a sor mellől
        // bármikor újra megpróbálható.
        const fajlHiba = id ? await toltsdFelAFajlokat("krumpelloKiadas", id, ujFajlok) : null;
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

  async function torles() {
    if (!kiadas) return;
    if (!(await confirm(`Biztosan törlöd ezt a kiadást: „${kiadas.kedvezmenyezett}”?`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/krumpello/kiadasok/${kiadas.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen törlés (HTTP ${res.status})`);
        return;
      }
      onBezar();
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen törlés (hálózati hiba): ${err}`);
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
          <h3 className="text-[14px] font-medium text-text-primary">{kiadas ? "Kiadás javítása" : "Új kiadás"}</h3>
        </div>

        <div className="max-h-[65vh] overflow-y-auto p-5">
          {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label className="text-[11px] text-text-muted">Forrás *</label>
              <KeresosSelect
                value={forras}
                options={FORRAS_CIMKEK}
                onChange={(v) => setForras((v as KrumpelloForras) ?? "utalas")}
                disabled={busy}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">Kedvezményezett *</label>
              <input
                value={kedvezmenyezett}
                onChange={(e) => setKedvezmenyezett(e.target.value)}
                disabled={busy}
                placeholder="Kinek fizettünk"
                className={mezoClass}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">Dátum</label>
              <input type="date" value={datum} onChange={(e) => setDatum(e.target.value)} disabled={busy} className={mezoClass} />
            </div>
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label className="text-[11px] text-text-muted">Tétel neve</label>
              <input
                value={megnevezes}
                onChange={(e) => setMegnevezes(e.target.value)}
                disabled={busy}
                placeholder="Mire ment el"
                className={mezoClass}
              />
            </div>
            {!extra && (
              <>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-text-muted">Nettó</label>
                  <input type="number" value={netto} onChange={(e) => setNetto(e.target.value)} disabled={busy} className={mezoClass} />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-text-muted">ÁFA</label>
                  <input type="number" value={afa} onChange={(e) => setAfa(e.target.value)} disabled={busy} className={mezoClass} />
                </div>
              </>
            )}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">{extra ? "Összeg" : "Bruttó"}</label>
              <input type="number" value={brutto} onChange={(e) => setBrutto(e.target.value)} disabled={busy} className={mezoClass} />
              {extra && <p className="text-[11px] text-text-muted">Nincs számla, ezért nincs nettó/ÁFA bontás.</p>}
            </div>
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label className="text-[11px] text-text-muted">Megjegyzés</label>
              <input value={megjegyzes} onChange={(e) => setMegjegyzes(e.target.value)} disabled={busy} className={mezoClass} />
            </div>
            <div className="sm:col-span-2">
              <UjFajlValaszto fajlok={ujFajlok} onValtozas={setUjFajlok} disabled={busy} />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-5 py-3">
          {kiadas && (
            <button type="button" onClick={torles} disabled={busy} className="btn btn-danger mr-auto">
              Törlés
            </button>
          )}
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
