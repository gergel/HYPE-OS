"use client";

import { useEffect, useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";
import { authFetch } from "@/lib/authFetch";

type Elonezet = {
  cimzett: string | null;
  targy: string;
  level_html: string;
  alap_szoveg: string;
  valaszkent: boolean;
  esedekes: boolean;
};

async function elonezetLekeres(contractId: number, szoveg: string | null): Promise<Elonezet> {
  const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/szerzodes/${contractId}/emlekezteto/elonezet`, {
    method: "POST",
    body: JSON.stringify({ szoveg }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => null);
    throw new Error(typeof d?.detail === "string" ? d.detail : `HTTP ${res.status}`);
  }
  return (await res.json()) as Elonezet;
}

/** Az aláírás-emlékeztető ELŐNÉZETE és SZERKESZTÉSE (a felhasználó kérése: a
 * levél szövege átírható legyen). Az alap szöveggel nyílik; amit átírnak, az
 * előnézet pár pillanat múlva mutatja - pontosan úgy, ahogy kimenne, a közös
 * aláírással. Küldeni csak itt, a gombbal lehet, és csak ha épp esedékes
 * (lásd backend subcontractor_contracts.emlekezteto_kuldese). A hívó
 * feltételesen rendereli, így minden megnyitás az alap szövegről indul. */
export function EmlekeztetoElonezet({
  contractId,
  nev,
  kuldheto,
  onClose,
  onElkuldve,
}: {
  contractId: number;
  nev: string;
  /** Van-e joga küldeni (a gomb csak akkor jelenik meg, ha esedékes is). */
  kuldheto: boolean;
  onClose: () => void;
  onElkuldve: () => void;
}) {
  const [adat, setAdat] = useState<Elonezet | null>(null);
  const [szoveg, setSzoveg] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [kuldes, setKuldes] = useState(false);

  // Első betöltés: az alap szöveg és a levél.
  useEffect(() => {
    let ervenyes = true;
    elonezetLekeres(contractId, null)
      .then((v) => {
        if (!ervenyes) return;
        setAdat(v);
        setSzoveg(v.alap_szoveg);
      })
      .catch((err) => ervenyes && setHiba(String(err instanceof Error ? err.message : err)));
    return () => {
      ervenyes = false;
    };
  }, [contractId]);

  // Átírás után (kis késleltetéssel) frissül az előnézet.
  useEffect(() => {
    if (szoveg === null) return;
    let ervenyes = true;
    const ora = window.setTimeout(() => {
      elonezetLekeres(contractId, szoveg)
        .then((v) => ervenyes && setAdat(v))
        .catch(() => undefined);
    }, 400);
    return () => {
      ervenyes = false;
      window.clearTimeout(ora);
    };
  }, [contractId, szoveg]);

  async function kuld() {
    setKuldes(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/szerzodes/${contractId}/emlekezteto`, {
        method: "POST",
        body: JSON.stringify({ szoveg }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setHiba(`Az emlékeztető nem ment ki: ${typeof d?.detail === "string" ? d.detail : res.status}`);
        return;
      }
      onElkuldve();
      onClose();
    } catch (err) {
      setHiba(`Az emlékeztető nem ment ki (hálózati hiba): ${err}`);
    } finally {
      setKuldes(false);
    }
  }

  const atirva = adat !== null && szoveg !== null && szoveg.trim() !== adat.alap_szoveg.trim();

  return (
    <ModalReteg onClose={kuldes ? undefined : onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Az emlékeztető előnézete"
        className="w-full max-w-3xl rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">Aláírás-emlékeztető – {nev}</h3>
          <p className="mt-0.5 text-[12.5px] text-text-secondary">
            A szöveg átírható. A levél csak az „Emlékeztető küldése” gombra megy ki – magától soha.
          </p>
        </div>
        <div className="max-h-[72vh] overflow-y-auto p-5 text-[13px]">
          {!adat ? (
            <p className={hiba ? "text-text-danger" : "text-text-muted"}>
              {hiba ? `Az előnézet nem töltődött be: ${hiba}` : "Betöltés…"}
            </p>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1">
                <p>
                  <span className="text-text-muted">Címzett: </span>
                  <span className="text-text-primary">{adat.cimzett ?? "– (nincs e-mail cím)"}</span>
                </p>
                <p>
                  <span className="text-text-muted">Tárgy: </span>
                  <span className="font-medium text-text-primary">{adat.targy}</span>
                </p>
                <p className="text-[12px] text-text-muted">
                  {adat.valaszkent
                    ? "Válaszként megy az eredeti szerződés-levélre, ugyanabba a levélszálba."
                    : "Az eredeti levélszál nem ismert (régebbi kiküldés) – új levélként megy, ugyanazzal a tárggyal."}
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <span className="flex items-center justify-between">
                  <label htmlFor="emlekezteto-szoveg" className="text-[11px] text-text-muted">
                    A levél szövege (üres sor = új bekezdés; az aláírás automatikusan alá kerül)
                  </label>
                  {atirva && (
                    <button
                      type="button"
                      onClick={() => setSzoveg(adat.alap_szoveg)}
                      className="text-[12px] text-text-accent hover:underline"
                    >
                      Alap szöveg visszaállítása
                    </button>
                  )}
                </span>
                <textarea
                  id="emlekezteto-szoveg"
                  value={szoveg ?? ""}
                  onChange={(e) => setSzoveg(e.target.value)}
                  disabled={kuldes || !kuldheto}
                  rows={8}
                  className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary focus:outline-none"
                />
              </div>
              <div>
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">Így megy ki</p>
                {/* A levél elszigetelt keretben, ahogy a címzett látja. */}
                <iframe
                  title="Az emlékeztető levél"
                  sandbox=""
                  srcDoc={adat.level_html}
                  className="h-[340px] w-full rounded-[var(--radius)] border border-border bg-white"
                />
              </div>
              {hiba && <p className="text-text-danger">{hiba}</p>}
            </div>
          )}
        </div>
        <div className="flex items-center justify-end gap-3 border-t border-border px-5 py-3">
          {adat && kuldheto && !adat.esedekes && (
            <span className="mr-auto text-[12px] text-text-muted">Most még nem küldhető – a kiküldés után 7 nappal lesz.</span>
          )}
          <button
            type="button"
            onClick={onClose}
            disabled={kuldes}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Bezárás
          </button>
          {adat && kuldheto && adat.esedekes && (
            <button
              type="button"
              onClick={kuld}
              disabled={kuldes || !(szoveg ?? "").trim()}
              className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
            >
              {kuldes ? "Küldés…" : "Emlékeztető küldése"}
            </button>
          )}
        </div>
      </div>
    </ModalReteg>
  );
}
