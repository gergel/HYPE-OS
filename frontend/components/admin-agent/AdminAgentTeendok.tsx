"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";
import { ALLAPOT_CIMKE, TIPUS_CIMKE } from "@/components/admin-agent/allapotok";

type Sor = {
  id: number;
  tipus: string;
  cim: string;
  allapot: string;
  kockazat: string | null;
};

const TIPUS_OPCIOK = [
  { ertek: "szerzodes", cimke: "Szerződés-előkészítés" },
  { ertek: "tig", cimke: "TIG-előkészítés" },
  { ertek: "szamla", cimke: "Számla-felvezetés" },
  { ertek: "utalas", cimke: "Utalás-előkészítés" },
  { ertek: "egyeb", cimke: "Egyéb" },
];

/** HYRON TEENDŐK blokk egy projektkódhoz (projektkód-adatlap, utókövetés).
 *
 * Megmutatja az adott projektkódhoz tartozó HYRON feladatokat, és enged
 * újat felvenni (szerződés/TIG/számla/utalás), a projektkódhoz kötve. Így
 * HYRON munkafelülete ezekre az oldalakra is elér, és a rajtuk rögzített
 * javításokból tanul. Ha a felhasználónak nincs /admin-agent joga, a blokk
 * csendben elrejti magát. */
export function AdminAgentTeendok({ projectCodeId }: { projectCodeId: number }) {
  const [sorok, setSorok] = useState<Sor[]>([]);
  const [rejtett, setRejtett] = useState(false);
  const [betolt, setBetolt] = useState(true);
  const [nyitva, setNyitva] = useState(false);
  const [tipus, setTipus] = useState(TIPUS_OPCIOK[0].ertek);
  const [cim, setCim] = useState("");
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);

  async function betolts() {
    try {
      const res = await authFetch(`/api/v1/admin-agent/tasks?project_code_id=${projectCodeId}&limit=50`);
      if (res.status === 403) {
        setRejtett(true);
        return;
      }
      if (!res.ok) return;
      const d = (await res.json()) as { elemek: Sor[] };
      setSorok(d.elemek);
    } finally {
      setBetolt(false);
    }
  }

  useEffect(() => {
    betolts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectCodeId]);

  async function letrehoz() {
    setHiba(null);
    if (!cim.trim()) {
      setHiba("Adj címet a feladatnak.");
      return;
    }
    setFolyamatban(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/tasks", {
        method: "POST",
        body: JSON.stringify({ tipus, cim: cim.trim(), project_code_id: projectCodeId }),
      });
      if (res.status === 403) {
        setHiba("Nincs jogosultságod HYRON-feladat létrehozásához.");
        return;
      }
      if (!res.ok) {
        setHiba("A feladat létrehozása nem sikerült.");
        return;
      }
      setCim("");
      setNyitva(false);
      await betolts();
    } finally {
      setFolyamatban(false);
    }
  }

  if (rejtett) return null;

  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="t-card">HYRON teendők</p>
        <button
          type="button"
          onClick={() => setNyitva((v) => !v)}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1 text-[12px] font-medium text-text-primary hover:bg-surface-4"
        >
          {nyitva ? "Mégse" : "+ Feladat"}
        </button>
      </div>

      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[12.5px] text-text-danger">{hiba}</div>}

      {nyitva && (
        <div className="mb-4 grid grid-cols-1 gap-2 rounded-[var(--radius)] border border-border bg-surface-3 p-3 sm:grid-cols-[180px_1fr_auto]">
          <select
            value={tipus}
            onChange={(e) => setTipus(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
          >
            {TIPUS_OPCIOK.map((o) => (
              <option key={o.ertek} value={o.ertek}>
                {o.cimke}
              </option>
            ))}
          </select>
          <input
            value={cim}
            onChange={(e) => setCim(e.target.value)}
            placeholder="Mit kell elvégezni?"
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted"
          />
          <button
            type="button"
            disabled={folyamatban}
            onClick={letrehoz}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            {folyamatban ? "Mentés…" : "Létrehozás"}
          </button>
        </div>
      )}

      {betolt ? (
        <p className="text-[13px] text-text-secondary">Betöltés…</p>
      ) : sorok.length === 0 ? (
        <p className="text-[13px] text-text-secondary">
          Ehhez a projektkódhoz még nincs HYRON-feladat. A „+ Feladat” gombbal vehetsz fel szerződés-, TIG-,
          számla- vagy utalás-előkészítést; HYRON ezekből is tanul.
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {sorok.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-3 text-[13px]">
              <Link href={`/admin-agent/munkasor/${t.id}`} className="text-text-primary hover:text-text-accent hover:underline">
                {t.cim}
              </Link>
              <span className="shrink-0 text-[12px] text-text-muted">
                {TIPUS_CIMKE[t.tipus] ?? t.tipus} · {ALLAPOT_CIMKE[t.allapot] ?? t.allapot}
                {t.kockazat ? ` · ${t.kockazat}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
