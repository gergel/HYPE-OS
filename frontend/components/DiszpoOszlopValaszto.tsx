"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Columns3, RotateCcw } from "lucide-react";

/** Ékezet- és kisbetű-független kulcs a kereséshez - ugyanaz az elv, mint a
 * KeresosSelect-ben: aki "arvai"-t ír, találja meg "Árvai"-t is. */
function keresoKulcs(szoveg: string): string {
  return szoveg
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

export type OszlopTetel = {
  id: number;
  idx: number;
  betu: string;
  cimke: string | null;
  employee_nev: string | null;
  /** Admin által MINDENKI elől elrejtett oszlop. */
  globalisRejtett: boolean;
  /** A hívó saját nézetében elrejtett. */
  sajatRejtett: boolean;
  /** Befagyasztott (dátum/nap/diszpószám) oszlop - nem rejthető. */
  fagyasztott: boolean;
};

/** Az „Oszlopok" gomb panele (a felhasználó kérése): kereshető,
 * jelölőnégyzetes oszloplista, ahol egy pillantással látszik és állítható,
 * hogy MELYIK oszlop látszik a SAJÁT nézetben. Betűjel ÉS név alapján is
 * kereshető. A globális (admin-) elrejtés itt csak jelzésként látszik - azt
 * a rács admin-vezérlői kezelik. */
export function DiszpoOszlopValaszto({
  oszlopok,
  onSajatValt,
  onOsszesMutat,
  onAlapnezet,
  vanSajatBeallitas,
}: {
  oszlopok: OszlopTetel[];
  /** Egy oszlop saját láthatóságának átbillentése. */
  onSajatValt: (oszlopId: number, rejtett: boolean) => void;
  /** Minden SAJÁT elrejtés feloldása. */
  onOsszesMutat: () => void;
  /** A saját nézet teljes visszaállítása (elrejtések + szélességek). */
  onAlapnezet: () => void;
  /** Van-e bármi saját beállítás (a gombok engedélyezéséhez). */
  vanSajatBeallitas: boolean;
}) {
  const [nyitva, setNyitva] = useState(false);
  const [kereses, setKereses] = useState("");
  const dobozRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!nyitva) return;
    function kivulKatt(e: MouseEvent) {
      if (dobozRef.current && !dobozRef.current.contains(e.target as Node)) setNyitva(false);
    }
    window.addEventListener("mousedown", kivulKatt);
    return () => window.removeEventListener("mousedown", kivulKatt);
  }, [nyitva]);

  const szurt = useMemo(() => {
    const k = keresoKulcs(kereses.trim());
    if (!k) return oszlopok;
    return oszlopok.filter((o) =>
      keresoKulcs(`${o.betu} ${o.cimke ?? ""} ${o.employee_nev ?? ""}`).includes(k),
    );
  }, [oszlopok, kereses]);

  const sajatRejtettDb = oszlopok.filter((o) => o.sajatRejtett).length;

  return (
    <div ref={dobozRef} className="relative">
      <button
        type="button"
        onClick={() => setNyitva((n) => !n)}
        title="Oszlopok megjelenítése és elrejtése a saját nézetben"
        className={`flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] hover:bg-surface-3 ${
          sajatRejtettDb > 0 ? "text-text-accent" : "text-text-secondary"
        }`}
      >
        <Columns3 size={13} />
        Oszlopok
        {sajatRejtettDb > 0 && <span className="text-[10.5px]">({sajatRejtettDb} rejtve)</span>}
      </button>

      {nyitva && (
        <div className="absolute left-0 top-full z-50 mt-1 w-[300px] rounded-[var(--radius)] border border-border bg-surface-1 shadow-xl">
          <div className="border-b border-border p-2">
            <input
              autoFocus
              value={kereses}
              onChange={(e) => setKereses(e.target.value)}
              placeholder="Keresés betűjel vagy név szerint…"
              className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none"
            />
          </div>
          <div className="max-h-[300px] overflow-y-auto py-1">
            {szurt.length === 0 && (
              <p className="px-3 py-2 text-[12px] text-text-muted">Nincs találat.</p>
            )}
            {szurt.map((o) => (
              <label
                key={o.id}
                className={`flex cursor-pointer items-center gap-2 px-3 py-1 text-[12.5px] hover:bg-surface-3 ${
                  o.fagyasztott ? "cursor-default opacity-60" : ""
                }`}
                title={
                  o.fagyasztott
                    ? "Rögzített oszlop (dátum/nap/diszpószám) – nem rejthető, ez igazít el a sorok között"
                    : undefined
                }
              >
                <input
                  type="checkbox"
                  checked={!o.sajatRejtett}
                  disabled={o.fagyasztott}
                  onChange={() => onSajatValt(o.id, !o.sajatRejtett)}
                  className="h-3.5 w-3.5 accent-[var(--accent-solid)]"
                />
                <span className="w-8 shrink-0 font-mono text-[11px] text-text-muted">{o.betu}</span>
                <span className="min-w-0 flex-1 truncate text-text-primary">
                  {o.cimke || <span className="text-text-muted">(nincs felirat)</span>}
                  {o.employee_nev && o.employee_nev !== o.cimke && (
                    <span className="ml-1 text-[11px] text-text-muted">· {o.employee_nev}</span>
                  )}
                </span>
                {o.globalisRejtett && (
                  <span
                    className="shrink-0 rounded bg-bg-warning px-1 py-0.5 text-[10px] text-text-warning"
                    title="Az admin mindenki elől elrejtette"
                  >
                    mindenkinél rejtett
                  </span>
                )}
              </label>
            ))}
          </div>
          <div className="flex gap-1.5 border-t border-border p-2">
            <button
              type="button"
              disabled={sajatRejtettDb === 0}
              onClick={onOsszesMutat}
              className="flex-1 rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Összes megjelenítése
            </button>
            <button
              type="button"
              disabled={!vanSajatBeallitas}
              onClick={onAlapnezet}
              title="A saját elrejtések ÉS oszlopszélességek visszaállítása"
              className="flex items-center gap-1 rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              <RotateCcw size={12} />
              Alapnézet
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
