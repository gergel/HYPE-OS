"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { AnchoredPanel } from "@/components/AnchoredPanel";

export type KeresosOpcio = {
  value: string;
  label: string;
  /** Opcionális csoportcím - a natív <optgroup> megfelelője. */
  group?: string;
  /** Halványan a név mellé írt kiegészítés (pl. e-mail), ami a keresésbe is
   * beleszámít - azonos nevű embereket másképp nem lehetne megkülönböztetni. */
  sublabel?: string;
};

/** Ékezet- és kisbetű-független kulcs a kereséshez.
 *
 * Enélkül a magyar neveket pontosan ékezethelyesen kellene begépelni: aki
 * "arvai"-t ír, nem találná meg "Árvai"-t. A NFD bontás után a diakritikus
 * jeleket egyszerűen eldobjuk. */
function keresoKulcs(szoveg: string): string {
  return szoveg
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

/** KERESHETŐ legördülő - a natív <select> helyett.
 *
 * A natív select "keresése" a böngésző beépített ugrálása: csak az éppen
 * begépelt betűkkel egyező ELSŐ elemre ugrik, a beírt szöveg pár száz
 * ezredmásodperc után elfelejtődik, és a listát nem szűkíti. Hosszú
 * listáknál (minden munkatárs, minden cég) ez használhatatlan.
 *
 * Itt a panel tetején egy valódi szövegmező áll: amit beírsz, az MEGMARAD, és
 * a lista arra szűkül - a névben és a kiegészítésben (pl. e-mail) is keres,
 * ékezettől és kis/nagybetűtől függetlenül.
 *
 * Az értékkészlet ZÁRT (nem lehet új értéket felvenni) - ebben tér el a
 * SelectDropdown-tól, ami szöveges értékekhez való; itt azonosítót választunk
 * névsorból. */
export function KeresosSelect({
  value,
  options,
  onChange,
  placeholder = "Válassz…",
  disabled = false,
  className = "",
}: {
  value: string | null;
  options: KeresosOpcio[];
  onChange: (next: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const szurt = useMemo(() => {
    const kulcs = keresoKulcs(query.trim());
    if (!kulcs) return options;
    return options.filter((o) => keresoKulcs(`${o.label} ${o.sublabel ?? ""} ${o.group ?? ""}`).includes(kulcs));
  }, [options, query]);

  // Csoportonként, az eredeti sorrendet megtartva.
  const csoportok = useMemo(() => {
    const rendezett: { cim: string | undefined; elemek: KeresosOpcio[] }[] = [];
    for (const opcio of szurt) {
      const utolso = rendezett[rendezett.length - 1];
      if (utolso && utolso.cim === opcio.group) utolso.elemek.push(opcio);
      else rendezett.push({ cim: opcio.group, elemek: [opcio] });
    }
    return rendezett;
  }, [szurt]);

  const kivalasztott = options.find((o) => o.value === value) ?? null;

  function valaszt(opcio: KeresosOpcio) {
    onChange(opcio.value);
    close();
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => (open ? close() : setOpen(true))}
        className="flex w-full items-center justify-between gap-2 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-left text-[13px] text-text-primary disabled:opacity-50"
      >
        <span className={kivalasztott ? "truncate" : "truncate text-text-muted"}>
          {kivalasztott?.label ?? placeholder}
        </span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-text-muted" />
      </button>

      {open && (
        <AnchoredPanel anchorRef={containerRef} onClose={close}>
          <div className="border-b border-border p-2">
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") close();
                // Enterre az egyetlen találat kiválasztható - így a billentyűzet
                // el sem kell hagyni: gépelsz, Enter, kész.
                if (e.key === "Enter" && szurt.length === 1) {
                  e.preventDefault();
                  valaszt(szurt[0]);
                }
              }}
              placeholder="Keresés…"
              className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary outline-none"
            />
          </div>
          <div className="max-h-72 overflow-y-auto p-1">
            {csoportok.map((csoport, i) => (
              <div key={csoport.cim ?? `nincs-${i}`}>
                {csoport.cim && (
                  <p className="px-2 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                    {csoport.cim}
                  </p>
                )}
                {csoport.elemek.map((opcio) => (
                  <button
                    key={opcio.value}
                    type="button"
                    onClick={() => valaszt(opcio)}
                    className={`block w-full truncate rounded-[var(--radius)] px-2 py-1.5 text-left text-[13px] hover:bg-surface-3 ${
                      opcio.value === value ? "text-text-accent" : "text-text-primary"
                    }`}
                  >
                    {opcio.label}
                    {opcio.sublabel && <span className="ml-2 text-[11.5px] text-text-muted">{opcio.sublabel}</span>}
                  </button>
                ))}
              </div>
            ))}
            {szurt.length === 0 && <p className="px-2 py-3 text-[12.5px] text-text-muted">Nincs találat.</p>}
          </div>
        </AnchoredPanel>
      )}
    </div>
  );
}
