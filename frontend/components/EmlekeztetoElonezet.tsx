"use client";

import { useEffect, useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";
import { authFetch } from "@/lib/authFetch";

type Elonezet = { cimzett: string | null; targy: string; level_html: string; valaszkent: boolean };

/** Hogyan néz ki az aláírás-emlékeztető (a felhasználó kérése): pontosan az
 * a levél, ami az "Emlékeztető küldése" gombra kimenne - címzett, tárgy,
 * szöveg, aláírás. Semmit nem küld (lásd backend
 * subcontractor_contracts.emlekezteto_elonezet). A hívó feltételesen
 * rendereli, így minden megnyitás friss lekérés. */
export function EmlekeztetoElonezet({ contractId, onClose }: { contractId: number; onClose: () => void }) {
  const [adat, setAdat] = useState<Elonezet | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => {
    let ervenyes = true;
    authFetch(`/api/v1/alvallalkozoi-szerzodesek/szerzodes/${contractId}/emlekezteto/elonezet`)
      .then(async (res) => {
        if (!ervenyes) return;
        if (!res.ok) {
          const d = await res.json().catch(() => null);
          setHiba(typeof d?.detail === "string" ? d.detail : `HTTP ${res.status}`);
          return;
        }
        setAdat((await res.json()) as Elonezet);
      })
      .catch((err) => ervenyes && setHiba(String(err)));
    return () => {
      ervenyes = false;
    };
  }, [contractId]);

  return (
    <ModalReteg onClose={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Az emlékeztető előnézete"
        className="w-full max-w-2xl rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">Az aláírás-emlékeztető előnézete</h3>
          <p className="mt-0.5 text-[12.5px] text-text-secondary">
            Ez a levél csak az „Emlékeztető küldése” gombra megy ki – magától soha.
          </p>
        </div>
        <div className="max-h-[70vh] overflow-y-auto p-5 text-[13px]">
          {hiba ? (
            <p className="text-text-danger">Az előnézet nem töltődött be: {hiba}</p>
          ) : !adat ? (
            <p className="text-text-muted">Betöltés…</p>
          ) : (
            <div className="space-y-2">
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
              {/* A levél elszigetelt keretben, ahogy a címzett látja. */}
              <iframe
                title="Az emlékeztető levél"
                sandbox=""
                srcDoc={adat.level_html}
                className="h-[360px] w-full rounded-[var(--radius)] border border-border bg-white"
              />
            </div>
          )}
        </div>
        <div className="flex justify-end border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Bezárás
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
