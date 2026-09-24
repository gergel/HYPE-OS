"use client";

import { useState } from "react";
import { authFetch } from "@/lib/authFetch";

/** Egy szabály SZAKMAI tesztje (kliens) — a szabály aktuális verziójához
 * kötött pozitív, ellenpélda és hiányos-adat esetek. Ha van eset, az
 * élesítéshez mindnek át kell mennie (lásd backend admin_agent/szakmai_eval.py). */

type Eset = {
  id: number;
  nev: string;
  fajta: "pozitiv" | "ellenpelda" | "hianyos";
  bemenet: Record<string, unknown>;
  elvart: Record<string, unknown> | null;
  kapott: { alkalmazhato: boolean; eredmeny: Record<string, unknown> | null; ok: string };
  ok: boolean;
};

type Eredmeny = {
  gepi: boolean;
  esetszam: number;
  atment: boolean | null;
  hianyzo_fajta?: string[];
  esetek: Eset[];
  uzenet?: string;
  szabaly_verzio?: number;
};

const FAJTA: Record<string, string> = { pozitiv: "pozitív", ellenpelda: "ellenpélda", hianyos: "hiányos adat" };

export function LaraSzakmaiTeszt({ ruleId, canEdit }: { ruleId: number; canEdit: boolean }) {
  const [nyitva, setNyitva] = useState(false);
  const [e, setE] = useState<Eredmeny | null>(null);
  const [fut, setFut] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function betolt() {
    const r = await authFetch(`/api/v1/admin-agent/rules/${ruleId}/szakmai`);
    if (r.ok) setE((await r.json()) as Eredmeny);
    else setHiba("A szakmai teszt nem tölthető be.");
  }

  async function general() {
    setFut(true);
    setHiba(null);
    try {
      const r = await authFetch(`/api/v1/admin-agent/rules/${ruleId}/szakmai/generalas`, { method: "POST" });
      const d = (await r.json().catch(() => ({}))) as Eredmeny & { detail?: string };
      if (!r.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "Nem sikerült.");
        return;
      }
      setE(d);
    } finally {
      setFut(false);
    }
  }

  return (
    <div className="mt-1 text-[12px]">
      <button
        type="button"
        onClick={() => {
          setNyitva((v) => !v);
          if (!e) void betolt();
        }}
        className="text-text-accent hover:underline"
      >
        {nyitva ? "Szakmai teszt — elrejt" : "Szakmai teszt"}
      </button>
      {nyitva && (
        <div className="mt-1 rounded-[var(--radius)] border border-border bg-surface-2 p-2">
          {hiba && <p className="text-text-danger">{hiba}</p>}
          {!e ? (
            <p className="text-text-muted">Betöltés…</p>
          ) : !e.gepi ? (
            <p className="text-text-muted">{e.uzenet}</p>
          ) : (
            <>
              <p className="text-text-secondary">
                {e.esetszam === 0
                  ? "Ehhez a verzióhoz még nincs szakmai eset — az élesítést nem blokkolja, de érdemes felvenni."
                  : e.atment
                    ? `Mind a ${e.esetszam} eset átment (v${e.szabaly_verzio}).`
                    : "Nem ment át — ezzel a szabály nem élesíthető."}
                {e.hianyzo_fajta && e.hianyzo_fajta.length > 0 && e.esetszam > 0 && (
                  <> Hiányzik: {e.hianyzo_fajta.map((f) => FAJTA[f] ?? f).join(", ")}.</>
                )}
              </p>
              {e.esetek.length > 0 && (
                <ul className="mt-1 flex flex-col gap-0.5">
                  {e.esetek.map((c) => (
                    <li key={c.id} className={c.ok ? "text-text-secondary" : "text-text-danger"}>
                      {c.ok ? "✓" : "✗"} {FAJTA[c.fajta] ?? c.fajta}: {String(c.bemenet.partner ?? "— nincs partner —")} →{" "}
                      {c.kapott.alkalmazhato ? JSON.stringify(c.kapott.eredmeny) : `nem alkalmazható (${c.kapott.ok})`}
                    </li>
                  ))}
                </ul>
              )}
              {canEdit && (
                <button
                  type="button"
                  disabled={fut}
                  onClick={() => void general()}
                  className="mt-1.5 rounded-[var(--radius)] border border-border px-2 py-0.5 text-text-primary hover:bg-surface-4 disabled:opacity-50"
                >
                  {fut ? "…" : "Kiinduló esetek (pozitív, ellenpélda, hiányos)"}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
