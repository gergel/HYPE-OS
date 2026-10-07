"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";

type Elonezet = {
  cimzett: string | null;
  targy: string;
  level_html: string;
  pdf_base64: string | null;
  pdf_hiba: string | null;
};

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
 * rendereli, így minden megnyitás friss előnézet. */
export function PapirElonezet({ path, payload }: { path: string; payload: unknown }) {
  const [level, setLevel] = useState<Elonezet | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfToltodik, setPdfToltodik] = useState(true);
  const [pdfHiba, setPdfHiba] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  // A payload objektum minden rendernél új - a tartalmát figyeljük.
  const kulcs = JSON.stringify(payload);

  useEffect(() => {
    let ervenyes = true;
    let blobUrl: string | null = null;
    const adat = JSON.parse(kulcs) as unknown;
    lekeres(`${path}?pdf=false`, adat)
      .then((v) => ervenyes && setLevel(v))
      .catch((err) => ervenyes && setHiba(String(err instanceof Error ? err.message : err)));
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
  }, [path, kulcs]);

  return (
    <div className="mt-4 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-text-muted">Előnézet – így megy ki</p>
      {hiba ? (
        <p className="text-[12.5px] text-text-danger">Az előnézet nem készült el: {hiba}</p>
      ) : !level ? (
        <p className="text-[12.5px] text-text-muted">Az előnézet készül…</p>
      ) : (
        <div className="space-y-2 text-[13px]">
          <p>
            <span className="text-text-muted">E-mail tárgya: </span>
            <span className="font-medium text-text-primary">{level.targy}</span>
          </p>
          {/* A levél szövege elszigetelt keretben - a sablonba beírt adat ne
              futhasson a felületen. */}
          <iframe
            title="A levél szövege"
            sandbox=""
            srcDoc={level.level_html}
            className="h-[150px] w-full rounded-[var(--radius)] border border-border bg-white"
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
