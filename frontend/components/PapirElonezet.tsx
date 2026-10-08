"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";

type Elonezet = {
  cimzett: string | null;
  targy: string;
  level_html: string;
  pdf_base64: string | null;
  pdf_hiba: string | null;
  /** A levél szerkesztőjének: az alap tárgy/szöveg és a most érvényes szöveg. */
  alap_targy?: string | null;
  alap_szoveg?: string | null;
  szoveg?: string | null;
};

/** A kísérőlevél átírása (a felhasználó kérése): a hívó űrlapjában él (az
 * `email_targy` / `email_szoveg` mező), üres = az alap tárgy / szöveg. */
export type LevelSzerkeszto = {
  targy: string;
  szoveg: string;
  onChange: (v: { targy?: string; szoveg?: string }) => void;
};

/** A levél mezői nem hatnak a dokumentumra - a PDF-et ne készítsük újra miattuk. */
function dokumentumKulcs(payload: unknown): string {
  if (!payload || typeof payload !== "object") return JSON.stringify(payload);
  const { email_targy: _t, email_szoveg: _s, ...tobbi } = payload as Record<string, unknown>;
  void _t;
  void _s;
  return JSON.stringify(tobbi);
}

async function lekeres(url: string, payload: unknown): Promise<Elonezet> {
  const res = await authFetch(url, { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `HTTP ${res.status}`);
  }
  return (await res.json()) as Elonezet;
}

/** KIKÜLDÉS ELŐTTI ELŐNÉZET (a felhasználó kérése): pontosan az a levél és az
 * a kitöltött dokumentum, ami a küldéssel kimenne - a még nem mentett, beírt
 * adatokból (lásd backend subcontractor_contracts.elonezet és
 * performance_certificates.elonezet). Semmit nem ment és semmit nem küld.
 *
 * Előbb a levél adatai jönnek (gyors), utána a PDF: az egy ideiglenes
 * Google-dokumentumból készül, ezért pár másodperc. A hívó feltételesen
 * rendereli, így minden megnyitás friss előnézet.
 *
 * `szerkeszto`-vel a levél tárgya és szövege itt helyben átírható (a
 * felhasználó kérése: ha az alap levél nem tetszik); gépelés közben csak a
 * levél előnézete frissül, a dokumentumé nem. */
export function PapirElonezet({
  path,
  payload,
  szerkeszto,
}: {
  path: string;
  payload: unknown;
  szerkeszto?: LevelSzerkeszto;
}) {
  const [level, setLevel] = useState<Elonezet | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfToltodik, setPdfToltodik] = useState(true);
  const [pdfHiba, setPdfHiba] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  // A payload objektum minden rendernél új - a tartalmát figyeljük.
  const kulcs = JSON.stringify(payload);
  const dokKulcs = dokumentumKulcs(payload);

  // A levél: gépelés közben kis késleltetéssel (ne minden betűre kérdezzen).
  useEffect(() => {
    let ervenyes = true;
    const adat = JSON.parse(kulcs) as unknown;
    const idozito = setTimeout(() => {
      lekeres(`${path}?pdf=false`, adat)
        .then((v) => {
          if (!ervenyes) return;
          setLevel(v);
          setHiba(null);
        })
        .catch((err) => ervenyes && setHiba(String(err instanceof Error ? err.message : err)));
    }, 350);
    return () => {
      ervenyes = false;
      clearTimeout(idozito);
    };
  }, [path, kulcs]);

  // A dokumentum (PDF): csak ha a papírra kerülő adat változik.
  useEffect(() => {
    let ervenyes = true;
    let blobUrl: string | null = null;
    const adat = JSON.parse(dokKulcs) as unknown;
    lekeres(path, adat)
      .then((v) => {
        if (!ervenyes) return;
        if (v.pdf_base64) {
          const bajtok = Uint8Array.from(atob(v.pdf_base64), (ch) => ch.charCodeAt(0));
          blobUrl = URL.createObjectURL(new Blob([bajtok], { type: "application/pdf" }));
          setPdfUrl(blobUrl);
        } else {
          setPdfHiba(v.pdf_hiba ?? "A dokumentum előnézete nem készült el.");
        }
      })
      .catch((err) => ervenyes && setPdfHiba(String(err instanceof Error ? err.message : err)))
      .finally(() => ervenyes && setPdfToltodik(false));
    return () => {
      ervenyes = false;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [path, dokKulcs]);

  const alapTargy = level?.alap_targy ?? "";
  const alapSzoveg = level?.alap_szoveg ?? "";
  const atirva = !!szerkeszto && (!!szerkeszto.targy.trim() || !!szerkeszto.szoveg.trim());

  return (
    <div className="mt-4 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-text-muted">Előnézet – így megy ki</p>
      {hiba ? (
        <p className="text-[12.5px] text-text-danger">Az előnézet nem készült el: {hiba}</p>
      ) : !level ? (
        <p className="text-[12.5px] text-text-muted">Az előnézet készül…</p>
      ) : (
        <div className="space-y-2 text-[13px]">
          {szerkeszto ? (
            <div className="space-y-2">
              <label className="flex flex-col gap-1 text-[11px] text-text-muted">
                E-mail tárgya
                <input
                  value={szerkeszto.targy || alapTargy}
                  onChange={(e) => szerkeszto.onChange({ targy: e.target.value === alapTargy ? "" : e.target.value })}
                  className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-text-muted">
                A levél szövege – átírható, ha az alap nem tetszik (az aláírás mindig alá kerül)
                <textarea
                  value={szerkeszto.szoveg || alapSzoveg}
                  onChange={(e) =>
                    szerkeszto.onChange({ szoveg: e.target.value.trim() === alapSzoveg.trim() ? "" : e.target.value })
                  }
                  rows={7}
                  className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
                />
              </label>
              {atirva && (
                <button
                  type="button"
                  onClick={() => szerkeszto.onChange({ targy: "", szoveg: "" })}
                  className="text-[12px] text-text-accent hover:underline"
                >
                  Vissza az alap levélre
                </button>
              )}
              <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">Így néz ki a levél</p>
            </div>
          ) : (
            <p>
              <span className="text-text-muted">E-mail tárgya: </span>
              <span className="font-medium text-text-primary">{level.targy}</span>
            </p>
          )}
          {/* A levél szövege elszigetelt keretben - a sablonba beírt adat ne
              futhasson a felületen. */}
          <iframe
            title="A levél szövege"
            sandbox=""
            srcDoc={level.level_html}
            className={`${szerkeszto ? "h-[260px]" : "h-[150px]"} w-full rounded-[var(--radius)] border border-border bg-white`}
          />
        </div>
      )}
      <div className="mt-3">
        {pdfToltodik ? (
          <p className="text-[12.5px] text-text-muted">A dokumentum előnézete készül (pár másodperc)…</p>
        ) : pdfUrl ? (
          <>
            <iframe
              title="A dokumentum előnézete"
              src={pdfUrl}
              className="h-[480px] w-full rounded-[var(--radius)] border border-border bg-white"
            />
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block text-[12px] text-text-accent hover:underline"
            >
              Megnyitás új lapon
            </a>
          </>
        ) : (
          <p className="text-[12.5px] text-text-warning">{pdfHiba}</p>
        )}
      </div>
    </div>
  );
}
