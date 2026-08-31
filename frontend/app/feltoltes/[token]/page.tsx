"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  feltoltesFajl,
  feltoltesMappa,
  getFeltoltesAdatok,
  type FeltoltesAdatok,
} from "@/lib/portalApi";

/** A PORTÁL FELTÖLTŐ LINKJÉNEK oldala (a felhasználó kérése).
 *
 * Akinek ezt a linket küldjük, az bejelentkezés nélkül tud mappát létrehozni
 * és fájlokat feltölteni a portálra (vagy csak a kijelölt mappájába) - de
 * SEMMIT nem tud törölni és nem lát bele az admin felületbe. A token maga a
 * belépő; visszavonása után az oldal nem él tovább (lásd backend
 * portal_public.py "feltoltes" végpontjai). */
export default function FeltoltesPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [adatok, setAdatok] = useState<FeltoltesAdatok | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [ujMappa, setUjMappa] = useState("");
  const [busy, setBusy] = useState(false);
  const [allapot, setAllapot] = useState<string | null>(null);

  const betolt = useCallback(() => {
    getFeltoltesAdatok(token)
      .then((a) => {
        setAdatok(a);
        setHiba(null);
      })
      .catch((e) => setHiba(String(e?.message ?? e)));
  }, [token]);

  useEffect(() => {
    betolt();
  }, [betolt]);

  async function mappaLetrehozas() {
    if (!ujMappa.trim()) return;
    setBusy(true);
    try {
      await feltoltesMappa(token, ujMappa.trim());
      setUjMappa("");
      betolt();
    } catch (e) {
      alert(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function feltolt(files: FileList | null, folderId: number | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    try {
      let kesz = 0;
      for (const file of Array.from(files)) {
        setAllapot(`Feltöltés: ${file.name} (${kesz + 1}/${files.length})…`);
        const eredmeny = await feltoltesFajl(token, file, folderId);
        if (!eredmeny.ok) {
          alert(`${file.name}: ${eredmeny.hiba}`);
          break;
        }
        kesz += 1;
      }
      setAllapot(kesz > 0 ? `${kesz} fájl feltöltve. A videók feldolgozása pár percet vehet igénybe.` : null);
      betolt();
    } finally {
      setBusy(false);
    }
  }

  // Ugyanaz a sötét portál-téma, mint a /p/{slug} ügyfél-nézeten - a linket
  // külsős kapja, neki a portál kinézete az ismerős, nem a belső appé.
  if (hiba) {
    return (
      <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
        <main className="mx-auto max-w-xl px-6 py-20 text-center">
          <h1 className="mb-2 font-display text-2xl text-bone">A feltöltő link nem él</h1>
          <p className="text-mist">{hiba}</p>
        </main>
      </div>
    );
  }
  if (!adatok) {
    return (
      <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
        <main className="mx-auto max-w-xl px-6 py-20 text-center text-mist">Betöltés…</main>
      </div>
    );
  }

  const fajlBemenet = (folderId: number | null, cimke: string) => (
    <label
      className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border border-current/30 px-3 py-1.5 text-[13px] ${busy ? "pointer-events-none opacity-50" : "hover:opacity-80"}`}
    >
      ⬆ {cimke}
      <input
        type="file"
        multiple
        accept="video/*,image/*"
        className="hidden"
        disabled={busy}
        onChange={(e) => {
          void feltolt(e.target.files, folderId);
          e.target.value = "";
        }}
      />
    </label>
  );

  return (
    <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
    <main className="mx-auto max-w-2xl px-6 py-12">
      <p className="mb-1 text-[12px] uppercase tracking-wide opacity-60">Fájl-feltöltés</p>
      <h1 className="mb-2 text-[24px] font-semibold">{adatok.title}</h1>
      <p className="mb-8 text-[13.5px] opacity-70">
        Ezen az oldalon mappákba rendezve tölthetsz fel videókat és képeket. Törölni innen nem lehet – ha
        valami rossz helyre került, szólj annak, akitől a linket kaptad.
      </p>

      {allapot && <p className="mb-4 rounded-lg border border-current/20 px-3 py-2 text-[13px]">{allapot}</p>}

      {!adatok.csak_mappa && (
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <input
            value={ujMappa}
            onChange={(e) => setUjMappa(e.target.value)}
            placeholder="Új mappa neve…"
            className="rounded-lg border border-current/30 bg-transparent px-3 py-1.5 text-[13.5px] focus:outline-none"
          />
          <button
            type="button"
            onClick={mappaLetrehozas}
            disabled={busy || !ujMappa.trim()}
            className="rounded-lg border border-current/30 px-3 py-1.5 text-[13px] hover:opacity-80 disabled:opacity-50"
          >
            + Mappa létrehozása
          </button>
          {fajlBemenet(null, "Feltöltés mappán kívülre")}
        </div>
      )}

      <div className="space-y-3">
        {adatok.folders.length === 0 && (
          <p className="text-[13.5px] opacity-70">
            {adatok.csak_mappa ? "A kijelölt mappa nem található." : "Még nincs mappa – hozz létre egyet fent."}
          </p>
        )}
        {adatok.folders.map((f) => (
          <div key={f.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-current/20 px-4 py-3">
            <div>
              <p className="text-[14.5px] font-medium">📁 {f.name || "Névtelen mappa"}</p>
              <p className="text-[12px] opacity-60">
                {f.video_db} videó · {f.kep_db} kép
              </p>
            </div>
            {fajlBemenet(f.id, "Feltöltés ide")}
          </div>
        ))}
      </div>
    </main>
    </div>
  );
}
