"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** Alapszínek egy kattintásra - a színválasztóval bármilyen RGB szín
 * beállítható. Telített árnyalatok, amik sötét és világos témán is olvashatók
 * szövegszínként. */
const SZIN_MINTAK = ["#e07a5f", "#e0a24a", "#6d9f72", "#5f9ea0", "#7f8ec4", "#b06a8f", "#c05555"];

/** Mekkora négyzetre kicsinyítjük a profilképet a böngészőben, mielőtt a
 * szerverre küldenénk. 256px az avatár-méretekhez (32-80px) bőven elég, és a
 * data-URL így pár tíz kB marad - a szerver a 400 kB felettit elutasítja. */
const KEP_MERET = 256;

/** A kiválasztott képfájl kicsinyítése és középre vágása (cover) a
 * böngészőben, canvas-szal - a szerverre már csak a kész, kicsi JPEG megy. */
async function kepetKicsinyit(fajl: File): Promise<string> {
  const url = URL.createObjectURL(fajl);
  try {
    const kep = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("A képet nem sikerült beolvasni."));
      img.src = url;
    });
    const vaszon = document.createElement("canvas");
    vaszon.width = KEP_MERET;
    vaszon.height = KEP_MERET;
    const ctx = vaszon.getContext("2d");
    if (!ctx) throw new Error("A böngésző nem támogatja a kép feldolgozását.");
    // Középre vágás: a rövidebb oldal adja a kivágott négyzetet.
    const oldal = Math.min(kep.width, kep.height);
    const sx = (kep.width - oldal) / 2;
    const sy = (kep.height - oldal) / 2;
    ctx.drawImage(kep, sx, sy, oldal, oldal, 0, 0, KEP_MERET, KEP_MERET);
    return vaszon.toDataURL("image/jpeg", 0.85);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function monogram(nev: string): string {
  const darabok = nev.trim().split(/\s+/).filter(Boolean);
  if (darabok.length === 0) return "?";
  if (darabok.length === 1) return darabok[0].slice(0, 2).toUpperCase();
  return (darabok[0][0] + darabok[darabok.length - 1][0]).toUpperCase();
}

/** A saját profil szerkesztője (a felhasználó kérése): profilkép + saját szín.
 * A szín a név megjelenítési színe a felületen (pl. az utómunka kártyák
 * "Kiosztva" sora), a kép a fejléc avatárjában jelenik meg. */
export function ProfilSzerkeszto({
  nev,
  email,
  kezdetiSzin,
  kezdetiKep,
}: {
  nev: string;
  email: string | null;
  kezdetiSzin: string | null;
  kezdetiKep: string | null;
}) {
  const router = useRouter();
  const fajlRef = useRef<HTMLInputElement>(null);
  const [szin, setSzin] = useState<string | null>(kezdetiSzin);
  const [kep, setKep] = useState<string | null>(kezdetiKep);
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<{ hiba: boolean; szoveg: string } | null>(null);

  async function fajlValasztva(fajl: File | undefined) {
    if (!fajl) return;
    setUzenet(null);
    try {
      setKep(await kepetKicsinyit(fajl));
    } catch (err) {
      setUzenet({ hiba: true, szoveg: err instanceof Error ? err.message : String(err) });
    }
  }

  async function mentes() {
    setBusy(true);
    setUzenet(null);
    try {
      const res = await authFetch("/api/v1/auth/me/profil", {
        method: "PUT",
        body: JSON.stringify({ szin, profilkep: kep }),
      });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        setUzenet({ hiba: true, szoveg: `A mentés nem sikerült: ${adat?.detail ?? res.status}` });
        return;
      }
      setUzenet({ hiba: false, szoveg: "Elmentve. A színed mostantól a kártyákon is így jelenik meg." });
      // A fejléc avatárja szerver-oldalon renderelődik - frissítjük.
      router.refresh();
    } catch (err) {
      setUzenet({ hiba: true, szoveg: `A mentés nem sikerült (hálózati hiba): ${err}` });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Fejléc: avatár + név a saját színen (élő előnézet). */}
      <div className="flex items-center gap-4">
        {kep ? (
          // Az avatár data-URL-t mutat, nem külső képet - a next/image itt
          // nem adna semmit (nincs mit optimalizálnia).
          // eslint-disable-next-line @next/next/no-img-element
          <img src={kep} alt="Profilkép" className="h-20 w-20 shrink-0 rounded-full border border-border object-cover" />
        ) : (
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-bg-accent text-[24px] font-medium text-text-accent">
            {monogram(nev)}
          </div>
        )}
        <div className="min-w-0">
          <p
            className="truncate text-[17px] font-semibold"
            style={szin ? { color: szin } : undefined}
          >
            {nev}
          </p>
          {email && <p className="truncate text-[13px] text-text-muted">{email}</p>}
          <p className="mt-0.5 text-[12px] text-text-muted">
            Így jelenik meg a neved a felületen{szin ? "" : " (még nincs saját színed)"}.
          </p>
        </div>
      </div>

      {/* Profilkép */}
      <div>
        <p className="mb-1 text-[13px] font-medium text-text-primary">Profilkép</p>
        <p className="mb-2 text-[12px] text-text-muted">
          A kép a böngészőben kicsinyítve ({KEP_MERET}×{KEP_MERET}) kerül mentésre - bármilyen képfájl jó.
        </p>
        <input
          ref={fajlRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            void fajlValasztva(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <div className="flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => fajlRef.current?.click()}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            {kep ? "Kép cseréje…" : "Kép feltöltése…"}
          </button>
          {kep && (
            <button
              type="button"
              disabled={busy}
              onClick={() => setKep(null)}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:text-text-danger disabled:opacity-50"
            >
              Kép törlése
            </button>
          )}
        </div>
      </div>

      {/* Saját szín */}
      <div>
        <p className="mb-1 text-[13px] font-medium text-text-primary">A színem</p>
        <p className="mb-2 text-[12px] text-text-muted">
          A neved ezen a színen jelenik meg a felületen - például az utómunka kártyák &quot;Kiosztva&quot; sorában.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="color"
            value={szin ?? "#8a8a8a"}
            onChange={(e) => setSzin(e.target.value)}
            aria-label="Saját szín"
            className="h-8 w-12 cursor-pointer rounded border border-border bg-transparent"
          />
          {SZIN_MINTAK.map((minta) => (
            <button
              key={minta}
              type="button"
              onClick={() => setSzin(minta)}
              aria-label={`Szín: ${minta}`}
              style={{ background: minta }}
              className={`h-6 w-6 rounded-full border ${szin === minta ? "border-text-primary" : "border-border"}`}
            />
          ))}
          {szin && (
            <button
              type="button"
              onClick={() => setSzin(null)}
              className="text-[12.5px] text-text-secondary hover:text-text-primary hover:underline"
            >
              szín nélkül
            </button>
          )}
        </div>
      </div>

      {uzenet && (
        <p className={`text-[13px] ${uzenet.hiba ? "text-text-danger" : "text-text-success"}`}>{uzenet.szoveg}</p>
      )}

      <div className="flex items-center gap-2 border-t border-border pt-4">
        <button type="button" disabled={busy} onClick={() => void mentes()} className="btn btn-primary disabled:opacity-50">
          {busy ? "Mentés…" : "Mentés"}
        </button>
      </div>
    </div>
  );
}
