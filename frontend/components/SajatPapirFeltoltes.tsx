"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

/** "Saját papír feltöltése" gomb - a generálás és kiküldés HELYETT.
 *
 * Nem minden papír itt készül: van, amit máshol írtak meg, vagy ami már
 * aláírva jön vissza. Ilyenkor nincs mit generálni és nincs kinek kiküldeni,
 * csak rögzíteni - ez a gomb tölti fel a kész dokumentumot, a backend pedig
 * ugyanoda viszi a bejegyzést, ahova a kiküldés vinné (lásd a .../sajat-fajl
 * végpontokat).
 *
 * Az `elokeszit` az űrlap mentése: a feltöltés csak a fájlt küldi, az űrlapon
 * beírt adatokat (összeg, keltezés, tételek) előtte el kell menteni - ha az
 * nem sikerül, fel se töltünk. */
export function SajatPapirFeltoltes({
  cimke,
  feltoltesPath,
  elokeszit,
  disabled = false,
  onKesz,
}: {
  cimke: string;
  feltoltesPath: string;
  elokeszit?: () => Promise<boolean>;
  disabled?: boolean;
  onKesz: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function feltolt(file: File) {
    setBusy(true);
    try {
      if (elokeszit && !(await elokeszit())) return;
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch(feltoltesPath, { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen feltöltés: ${detail?.detail ?? res.status}`);
        return;
      }
      onKesz();
    } catch (err) {
      alert(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
      // A mezőt ürítjük, hogy ugyanaz a fájl újra kiválasztható legyen (a
      // böngésző azonos értéknél nem indítana új change eseményt).
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <label
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary ${
        disabled || busy ? "opacity-50" : "cursor-pointer hover:bg-surface-3"
      }`}
      title="A generálás és kiküldés helyett: egy már meglévő dokumentum feltöltése"
    >
      <Upload size={13} />
      {busy ? "Feltöltés…" : cimke}
      <input
        ref={inputRef}
        type="file"
        disabled={disabled || busy}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) feltolt(file);
        }}
        className="hidden"
      />
    </label>
  );
}
