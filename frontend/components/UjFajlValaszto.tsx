"use client";

import { Paperclip, Upload, X } from "lucide-react";

/** Fájlválasztó FELVITELI ŰRLAPHOZ: csak összegyűjti a fájlokat, nem tölt fel.
 *
 * A csatolmány végpontnak kell az entity_id, az viszont még nincs meg, amíg a
 * rekordot nem mentettük (lásd lib/csatolmany.toltsdFelAFajlokat). Ezért itt
 * csak kiválasztjuk a fájlt, a feltöltés a mentés UTÁN fut le.
 *
 * Miért kell ez egyáltalán, ha a listában soronként is fel lehet tölteni?
 * Mert a számla akkor van kéznél, amikor a tételt felvezetik - egy külön
 * "majd megkeresem a sort és feltöltöm" lépés az, ami rendszeresen elmarad.
 */
export function UjFajlValaszto({
  fajlok,
  onValtozas,
  disabled = false,
  cimke = "Számla / blokk",
  sugo = "Nem kötelező – utólag is feltölthető a listában.",
}: {
  fajlok: File[];
  onValtozas: (uj: File[]) => void;
  disabled?: boolean;
  cimke?: string;
  sugo?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] text-text-muted">{cimke}</label>
      {fajlok.length > 0 && (
        <ul className="space-y-1">
          {fajlok.map((f, index) => (
            <li key={`${f.name}-${index}`} className="flex items-center gap-2 text-[12.5px] text-text-secondary">
              <Paperclip size={12} className="shrink-0 text-text-muted" />
              <span className="max-w-[300px] truncate" title={f.name}>
                {f.name}
              </span>
              <button
                type="button"
                onClick={() => onValtozas(fajlok.filter((_, i) => i !== index))}
                disabled={disabled}
                title="Fájl elvétele"
                className="rounded-[var(--radius)] p-0.5 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
              >
                <X size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <label
        className={`inline-flex w-fit items-center gap-1.5 rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary ${
          disabled ? "opacity-50" : "cursor-pointer hover:bg-surface-3"
        }`}
      >
        <Upload size={12} />
        {fajlok.length > 0 ? "Még egy fájl" : "Fájl kiválasztása (PDF, fotó)"}
        <input
          type="file"
          multiple
          // A telefon így a kamerát és a galériát is felajánlja - a blokkot a
          // legtöbbször ott helyben fotózzák le.
          accept="application/pdf,image/*"
          disabled={disabled}
          onChange={(e) => {
            const ujak = Array.from(e.target.files ?? []);
            if (ujak.length > 0) onValtozas([...fajlok, ...ujak]);
            e.target.value = "";
          }}
          className="hidden"
        />
      </label>
      <p className="text-[11px] text-text-muted">{sugo}</p>
    </div>
  );
}
