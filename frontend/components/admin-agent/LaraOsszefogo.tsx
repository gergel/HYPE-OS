"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";
import { ALLAPOT_CIMKE, TIPUS_CIMKE } from "@/components/admin-agent/allapotok";

type Hatokor = {
  idoszak: { tol: string; ig: string; cimke: string } | null;
  projektkodok: { id: number; kod: string }[];
  ugyfelek: { id: number; nev: string }[];
  temak: string[];
};

type Tetel = { kulcs: string; tema: string; cimke: string; allapot?: string; project_id?: number };

type Allapot = {
  hatokor: Hatokor;
  cel: string | null;
  terv: Tetel[];
  terv_osszesito: Record<string, number>;
  reszfeladatok: { id: number; tipus: string; cim: string; allapot: string }[];
  reszfeladat_db: number;
  kesz_db: number;
  lezart_db: number;
  nyitott_tetel_db: number;
  bontatlan_tetel_db: number;
  szazalek: number;
  kesz?: boolean;
};

const TEMAK: { kulcs: string; cimke: string }[] = [
  { kulcs: "szerzodes", cimke: "Szerződés" },
  { kulcs: "tig", cimke: "TIG" },
  { kulcs: "szamla", cimke: "Számla" },
  { kulcs: "email", cimke: "E-mail (pl. számlabekérés)" },
  { kulcs: "diszpo", cimke: "Diszpó brief + technika" },
];

async function lekeres(taskId: number): Promise<Allapot | string> {
  const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/osszefogo`);
  const d = await res.json().catch(() => ({}));
  if (!res.ok) return typeof d.detail === "string" ? d.detail : `Nem sikerült betölteni (${res.status}).`;
  return d as Allapot;
}

/** Lara — ÖSSZEFOGÓ adminisztrációs feladat: a nagy feladat értelmezett
 * hatóköre (időszak, projektkódok, ügyfél, témák), az élő terv (a konkrét
 * teendők a teljes rendszerből) és a részfeladatok előrehaladása. A
 * részfeladatok csak a gombra jönnek létre, és a szokásos jóváhagyási úton
 * mennek tovább - az összefogó feladat maga semmit nem hajt végre. */
export function LaraOsszefogo({ taskId, canEdit }: { taskId: number; canEdit: boolean }) {
  const [adat, setAdat] = useState<Allapot | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [szerk, setSzerk] = useState(false);
  const [temak, setTemak] = useState<string[]>([]);
  const [tol, setTol] = useState("");
  const [ig, setIg] = useState("");

  const alkalmaz = useCallback((d: Allapot | string) => {
    if (typeof d === "string") {
      setHiba(d);
      return;
    }
    setAdat(d);
    setTemak(d.hatokor.temak);
    setTol(d.hatokor.idoszak?.tol ?? "");
    setIg(d.hatokor.idoszak?.ig ?? "");
  }, []);

  useEffect(() => {
    let elve = false;
    lekeres(taskId).then((d) => {
      if (!elve) alkalmaz(d);
    });
    return () => {
      elve = true;
    };
  }, [taskId, alkalmaz]);

  async function hivas(ut: string, method: string, body: unknown, siker: (d: Record<string, unknown>) => string) {
    setBusy(true);
    setHiba(null);
    setUzenet(null);
    try {
      const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/osszefogo${ut}`, {
        method,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : `Sikertelen művelet (${res.status}).`);
        return;
      }
      setUzenet(siker(d));
      alkalmaz(await lekeres(taskId));
    } finally {
      setBusy(false);
    }
  }

  if (hiba && !adat) return <p className="text-[13px] text-text-danger">{hiba}</p>;
  if (!adat) return <p className="text-[13px] text-text-muted">Betöltés…</p>;
  const hk = adat.hatokor;

  return (
    <div className="flex flex-col gap-4 text-[13px]">
      {hiba && <p className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-text-danger">{hiba}</p>}
      {uzenet && <p className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-text-success">{uzenet}</p>}

      <section>
        <h3 className="mb-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">Így értelmeztem</h3>
        {adat.cel && <p className="mb-2 text-text-primary">{adat.cel}</p>}
        <div className="flex flex-wrap gap-1.5">
          <span className="rounded-full bg-surface-3 px-2 py-0.5 text-text-secondary">
            Időszak: {hk.idoszak ? hk.idoszak.cimke : "nincs megszorítás"}
          </span>
          {hk.temak.map((t) => (
            <span key={t} className="rounded-full bg-bg-accent px-2 py-0.5 text-text-accent">
              {TEMAK.find((x) => x.kulcs === t)?.cimke ?? t}
            </span>
          ))}
          {hk.projektkodok.map((k) => (
            <span key={k.id} className="rounded-full bg-surface-3 px-2 py-0.5 text-text-secondary">
              {k.kod}
            </span>
          ))}
          {hk.ugyfelek.map((u) => (
            <span key={u.id} className="rounded-full bg-surface-3 px-2 py-0.5 text-text-secondary">
              Ügyfél: {u.nev}
            </span>
          ))}
        </div>
        {canEdit && (
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSzerk((v) => !v)}
              className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3"
            >
              {szerk ? "Mégse" : "Hatókör javítása"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void hivas("/ertelmezes", "POST", undefined, () => "Újraértelmeztem a feladatot.")}
              className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
            >
              Újraértelmezés
            </button>
          </div>
        )}
        {szerk && (
          <div className="mt-2 flex flex-col gap-2 rounded-[var(--radius)] border border-border p-3">
            <div className="flex flex-wrap gap-3">
              {TEMAK.map((t) => (
                <label key={t.kulcs} className="flex items-center gap-1.5 text-text-secondary">
                  <input
                    type="checkbox"
                    checked={temak.includes(t.kulcs)}
                    onChange={(e) =>
                      setTemak((v) => (e.target.checked ? [...v, t.kulcs] : v.filter((x) => x !== t.kulcs)))
                    }
                  />
                  {t.cimke}
                </label>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-text-secondary">
              Időszak:
              <input type="date" value={tol} onChange={(e) => setTol(e.target.value)} className="rounded border border-border bg-surface-3 px-2 py-1" />
              –
              <input type="date" value={ig} onChange={(e) => setIg(e.target.value)} className="rounded border border-border bg-surface-3 px-2 py-1" />
              <span className="text-[12px] text-text-muted">(üresen: nincs időszak-megszorítás)</span>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void hivas("/hatokor", "PATCH", { temak, idoszak: tol && ig ? { tol, ig } : null }, () => {
                  setSzerk(false);
                  return "A hatókör frissült - a terv ennek megfelelően újraszámolódott.";
                })
              }
              className="self-start rounded-[var(--radius)] bg-bg-accent px-3 py-1 text-[12.5px] font-medium text-text-accent disabled:opacity-50"
            >
              Mentés
            </button>
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">
          Teendők most ({adat.nyitott_tetel_db})
        </h3>
        {adat.terv.length === 0 ? (
          <p className="text-text-secondary">A hatókörben most nincs nyitott teendő.</p>
        ) : (
          <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto">
            {adat.terv.map((t) => (
              <li key={t.kulcs} className="flex items-start gap-2">
                <span className="mt-0.5 shrink-0 rounded bg-surface-3 px-1.5 text-[11px] text-text-muted">
                  {TEMAK.find((x) => x.kulcs === t.tema)?.cimke ?? t.tema}
                </span>
                <span className="text-text-primary">{t.cimke}</span>
              </li>
            ))}
          </ul>
        )}
        {canEdit && adat.bontatlan_tetel_db > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void hivas("/bontas", "POST", undefined, (d) =>
                `Részfeladatok: ${d.letrehozva ?? 0} új${d.bekotve ? `, ${d.bekotve} meglévő bekötve` : ""}. Mindegyik a szokásos jóváhagyási úton megy tovább.`,
              )
            }
            className="mt-2 rounded-[var(--radius)] bg-bg-success px-3 py-1.5 text-[13px] font-medium text-text-success disabled:opacity-50"
          >
            Részfeladatok létrehozása ({adat.bontatlan_tetel_db} tétel)
          </button>
        )}
      </section>

      <section>
        <h3 className="mb-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">
          Részfeladatok ({adat.kesz_db}/{adat.reszfeladat_db} kész)
        </h3>
        {adat.reszfeladat_db > 0 && (
          <div className="mb-2 h-2 w-full overflow-hidden rounded-full bg-surface-3" aria-label={`${adat.szazalek}% kész`}>
            <div className="h-full bg-text-success" style={{ width: `${adat.szazalek}%` }} />
          </div>
        )}
        {adat.reszfeladatok.length === 0 ? (
          <p className="text-text-secondary">Még nincs részfeladat.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {adat.reszfeladatok.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-2">
                <Link href={`/admin-agent/munkasor/${r.id}`} className="text-text-accent hover:underline">
                  {r.cim}
                </Link>
                <span className="text-[12px] text-text-muted">
                  {TIPUS_CIMKE[r.tipus] ?? r.tipus} · {ALLAPOT_CIMKE[r.allapot] ?? r.allapot}
                </span>
              </li>
            ))}
          </ul>
        )}
        {canEdit && adat.reszfeladat_db > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              void hivas("/frissites", "POST", undefined, (d) =>
                d.kesz ? "Minden részfeladat lezárult és nincs nyitott teendő - az összefogó feladat kész." : "Előrehaladás frissítve.",
              )
            }
            className="mt-2 rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Előrehaladás frissítése
          </button>
        )}
      </section>
    </div>
  );
}
