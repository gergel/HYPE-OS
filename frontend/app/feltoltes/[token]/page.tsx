"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Folder as FolderIcon, FolderPlus, Loader2, Upload } from "lucide-react";
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
 * portal_public.py "feltoltes" végpontjai).
 *
 * A megjelenés az admin "Tartalom" feltöltő-zónáját követi (szaggatott
 * húzd-ide sáv, lucide ikonok) - ugyanaz a design-nyelv, emoji nélkül. */
export default function FeltoltesPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [adatok, setAdatok] = useState<FeltoltesAdatok | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [ujMappaNyitva, setUjMappaNyitva] = useState(false);
  const [ujMappa, setUjMappa] = useState("");
  const [busy, setBusy] = useState(false);
  const [allapot, setAllapot] = useState<string | null>(null);
  const [dragCel, setDragCel] = useState<number | "root" | null>(null);
  // CSAK BELSŐ ELLENŐRZÉSRE (a felhasználó kérése): bejelölve a feltöltött
  // videókat az ügyfél nem látja a portálon, amíg admin láthatóra nem
  // állítja - pl. amikor a vágó ellenőrzésre tölt fel egy anyagot.
  const [belsoEllenorzesre, setBelsoEllenorzesre] = useState(false);

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
      setUjMappaNyitva(false);
      betolt();
    } catch (e) {
      alert(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function feltolt(files: FileList | File[] | null, folderId: number | null) {
    const lista = files ? Array.from(files) : [];
    if (lista.length === 0) return;
    setBusy(true);
    try {
      let kesz = 0;
      for (const file of lista) {
        setAllapot(`Feltöltés: ${file.name} (${kesz + 1}/${lista.length})…`);
        const eredmeny = await feltoltesFajl(token, file, folderId, belsoEllenorzesre);
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

  /** Húzd-ide kezelés egy célra (a fő zóna vagy egy mappa). */
  const dropProps = (cel: number | "root", folderId: number | null) => ({
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
      setDragCel(cel);
    },
    onDragLeave: () => setDragCel((d) => (d === cel ? null : d)),
    onDrop: (e: React.DragEvent) => {
      e.preventDefault();
      setDragCel(null);
      void feltolt(e.dataTransfer.files, folderId);
    },
  });

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
        <main className="flex min-h-screen items-center justify-center">
          <span className="font-mono text-xs uppercase tracking-eyebrow text-mist">Betöltés…</span>
        </main>
      </div>
    );
  }

  return (
    <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
      {/* RAGADÓS fejléc a portál nevével (a felhasználó kérése): telefonon,
          hosszú mappalistában görgetve is mindig látszik, hova tölt fel az
          ember. */}
      <div className="sticky top-0 z-40 border-b border-ink-line bg-ink/95 px-6 py-2.5 backdrop-blur">
        <p className="mx-auto max-w-3xl truncate text-sm text-bone">
          <span className="mr-2 font-mono text-[11px] uppercase tracking-eyebrow text-mist">Feltöltés ide:</span>
          {adatok.title}
        </p>
      </div>
      <main className="mx-auto max-w-3xl px-6 py-10">
        <p className="mb-1 font-mono text-xs uppercase tracking-eyebrow text-mist">Fájl-feltöltés</p>
        <h1 className="mb-2 break-words font-display text-3xl text-bone">{adatok.title}</h1>
        <p className="mb-8 text-sm leading-relaxed text-mist">
          Ezen az oldalon mappákba rendezve tölthetsz fel videókat és képeket. Törölni innen nem lehet – ha
          valami rossz helyre került, szólj annak, akitől a linket kaptad.
        </p>

        {allapot && (
          <p className="mb-5 flex items-center gap-2 rounded-2xl border border-ink-line bg-ink-card px-4 py-3 text-sm text-bone">
            {busy && <Loader2 className="h-4 w-4 animate-spin text-mist" />}
            {allapot}
          </p>
        )}

        {/* CSAK BELSŐ ELLENŐRZÉSRE (a felhasználó kérése): bejelölve az itt
            feltöltött videókat az ügyfél nem látja a portálon, amíg az admin
            láthatóra nem állítja - pl. amikor a vágó ellenőrzésre tölt fel. */}
        <label className="mb-6 flex cursor-pointer items-start gap-3 rounded-2xl border border-ink-line bg-ink-card px-4 py-3">
          <input
            type="checkbox"
            checked={belsoEllenorzesre}
            onChange={(e) => setBelsoEllenorzesre(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer"
          />
          <span>
            <span className="block text-sm text-bone">Csak belső ellenőrzésre töltöm fel</span>
            <span className="block text-[13px] leading-relaxed text-mist">
              A így feltöltött videókat az ügyfél nem látja a portálon, amíg az admin láthatóra nem állítja.
            </span>
          </span>
        </label>

        {/* Fejléc: Tartalom + Új mappa - ugyanaz a minta, mint az adminon. */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="font-display text-xl text-bone">Tartalom</h2>
          {!adatok.csak_mappa && (
            <button
              type="button"
              onClick={() => setUjMappaNyitva((n) => !n)}
              className="flex items-center gap-2 rounded-xl border border-ink-line px-3.5 py-2 text-sm text-bone transition hover:border-bone/40"
            >
              <FolderPlus className="h-4 w-4" />
              Új mappa
            </button>
          )}
        </div>
        {!adatok.csak_mappa && (
          <p className="mb-4 text-sm text-mist">
            Nyiss meg egy mappát, vagy tölts fel ide videókat és képeket mappa nélkül.
          </p>
        )}

        {ujMappaNyitva && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <input
              value={ujMappa}
              onChange={(e) => setUjMappa(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void mappaLetrehozas()}
              placeholder="Új mappa neve…"
              autoFocus
              className="min-w-0 flex-1 rounded-xl border border-ink-line bg-transparent px-3.5 py-2 text-sm text-bone placeholder:text-mist focus:border-bone/40 focus:outline-none"
            />
            <button
              type="button"
              onClick={mappaLetrehozas}
              disabled={busy || !ujMappa.trim()}
              className="rounded-xl border border-ink-line px-3.5 py-2 text-sm text-bone transition hover:border-bone/40 disabled:opacity-50"
            >
              Létrehozás
            </button>
          </div>
        )}

        {/* A fő feltöltő-zóna: húzd ide, vagy kattints a tallózáshoz. */}
        {!adatok.csak_mappa && (
          <label
            {...dropProps("root", null)}
            className={`mb-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed px-6 py-12 text-center transition ${
              dragCel === "root" ? "border-bone/70 bg-ink-card" : "border-ink-line hover:border-bone/40"
            } ${busy ? "pointer-events-none opacity-60" : ""}`}
          >
            <Upload className="h-6 w-6 text-mist" />
            <span className="text-base text-bone">Húzd ide a fájlokat</span>
            <span className="text-sm text-mist">Vagy kattints a tallózáshoz – videók és képek mehetnek.</span>
            <input
              type="file"
              multiple
              accept="video/*,image/*"
              className="hidden"
              disabled={busy}
              onChange={(e) => {
                void feltolt(e.target.files, null);
                e.target.value = "";
              }}
            />
          </label>
        )}

        {/* Mappák: mindegyik saját húzd-ide céllal és feltöltés gombbal. */}
        <div className="space-y-3">
          {adatok.folders.length === 0 && (
            <p className="text-sm text-mist">
              {adatok.csak_mappa ? "A kijelölt mappa nem található." : "Még nincs mappa – hozz létre egyet fent."}
            </p>
          )}
          {adatok.folders.map((f) => (
            <div
              key={f.id}
              {...dropProps(f.id, f.id)}
              className={`flex flex-wrap items-center justify-between gap-3 rounded-2xl border px-4 py-3.5 transition ${
                dragCel === f.id ? "border-bone/70 bg-ink-card" : "border-ink-line"
              }`}
            >
              <div className="flex min-w-0 items-center gap-3">
                <FolderIcon className="h-5 w-5 shrink-0 text-mist" />
                <div className="min-w-0">
                  <p className="truncate text-base text-bone">{f.name || "Névtelen mappa"}</p>
                  <p className="font-mono text-[11px] uppercase tracking-eyebrow text-mist">
                    {f.video_db} videó · {f.kep_db} kép
                  </p>
                </div>
              </div>
              <label
                className={`flex cursor-pointer items-center gap-2 rounded-xl border border-ink-line px-3.5 py-2 text-sm text-bone transition hover:border-bone/40 ${
                  busy ? "pointer-events-none opacity-50" : ""
                }`}
              >
                <Upload className="h-4 w-4" />
                Feltöltés ide
                <input
                  type="file"
                  multiple
                  accept="video/*,image/*"
                  className="hidden"
                  disabled={busy}
                  onChange={(e) => {
                    void feltolt(e.target.files, f.id);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
