"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { SelectDropdown } from "@/components/SelectDropdown";
import { authFetch } from "@/lib/authFetch";
import { HU_HONAPOK } from "@/lib/huDate";

/** Egy hónap összes számlája egyetlen ZIP-ben - a könyvelésnek szánt csomag,
 * hogy ne kelljen egyenként végigkattintani a TIG-eket és a bevételeket.
 *
 * A ZIP-ben "bejovo" (a TIG-ekhez feltöltött alvállalkozói számlák) és
 * "kimeno" (a bevételekhez feltöltött megrendelői számlák) mappa van, plusz
 * egy tartalom.txt, amiből visszafejthető, melyik fájl honnan jött. */
export function SzamlaCsomagLetoltes() {
  const ma = new Date();
  const [ev, setEv] = useState(ma.getFullYear());
  const [honap, setHonap] = useState(ma.getMonth() + 1);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  const evek = [ma.getFullYear(), ma.getFullYear() - 1, ma.getFullYear() - 2];

  async function letolt() {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/finance/szamlak-zip?ev=${ev}&honap=${honap}`);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen letöltés (HTTP ${res.status})`);
        return;
      }
      // A böngésző letöltésként mentse, ne navigáljon el - a végpont
      // bejelentkezést igényel, ezért nem lehet sima <a href>.
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `szamlak_${ev}_${String(honap).padStart(2, "0")}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <SelectDropdown
          value={String(ev)}
          options={evek.map(String)}
          onChange={(value) => value && setEv(Number(value))}
          placeholder="Év"
        />
        <SelectDropdown
          value={HU_HONAPOK[honap - 1]}
          options={[...HU_HONAPOK]}
          onChange={(value) => {
            // A HU_HONAPOK literál-tömb, ezért a keresés előtt sima string-listaként nézzük.
            const index = (HU_HONAPOK as readonly string[]).indexOf(value ?? "");
            if (index >= 0) setHonap(index + 1);
          }}
          placeholder="Hónap"
        />
        <button
          type="button"
          disabled={busy}
          onClick={letolt}
          className="flex items-center gap-1.5 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
        >
          <Download size={13} />
          {busy ? "Csomagolás…" : "Számlák letöltése (ZIP)"}
        </button>
      </div>
      <p className="mt-2 text-[12px] text-text-muted">
        A csomagban a <b>bejovo</b> mappában a TIG-ekhez feltöltött alvállalkozói számlák vannak (a feltöltés hónapja
        szerint), a <b>kimeno</b> mappában a bevételekhez feltöltött megrendelői számlák (a számla kiállításának hónapja
        szerint).
      </p>
      {hiba && <p className="mt-1 text-[13px] text-text-danger">{hiba}</p>}
    </div>
  );
}
