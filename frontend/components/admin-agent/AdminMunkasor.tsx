"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AdminTaskSor } from "@/lib/api";
import { ALLAPOT_CIMKE, KEZI_ALLAPOTOK, TIPUS_CIMKE } from "@/components/admin-agent/allapotok";

type EmberOpcio = { id: number; nev: string };

const TIPUS_OPCIOK = Object.entries(TIPUS_CIMKE);

/** A LEZÁRT állapotok (a backend LEZART_TASK_STATES tükre) — csak a szűrőhöz. */
const LEZART = new Set(["completed", "rejected", "cancelled"]);

function hataridoLejart(t: AdminTaskSor): boolean {
  if (!t.hatarido || LEZART.has(t.allapot)) return false;
  return new Date(t.hatarido).getTime() < Date.now();
}

/** HYRON — MUNKASOR (kliens).
 *
 * A feladatok belső munkaszervezése: létrehozás, felelős-kiosztás és
 * MELLÉKHATÁS-MENTES állapotváltás (a backend csak a _KEZI_ALLAPOTOK átmeneteit
 * engedi — routes/admin_agent.py). A javaslat/végrehajtás állapotokat HYRON
 * és a jóváhagyási folyamat állítja, kézzel nem. */
export function AdminMunkasor({
  kezdoElemek,
  emberek,
  canCreate,
  canEdit,
}: {
  kezdoElemek: AdminTaskSor[];
  emberek: EmberOpcio[];
  canCreate: boolean;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [elemek, setElemek] = useState<AdminTaskSor[]>(kezdoElemek);
  const [tipusSzuro, setTipusSzuro] = useState("");
  const [allapotSzuro, setAllapotSzuro] = useState("");
  const [kereses, setKereses] = useState("");
  const [urlapNyitva, setUrlapNyitva] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [mentesFolyamatban, setMentesFolyamatban] = useState(false);

  const emberNev = useMemo(() => {
    const m = new Map<number, string>();
    for (const e of emberek) m.set(e.id, e.nev);
    return m;
  }, [emberek]);

  const szurtElemek = useMemo(() => {
    const k = kereses.trim().toLowerCase();
    return elemek.filter((t) => {
      if (tipusSzuro && t.tipus !== tipusSzuro) return false;
      if (allapotSzuro && t.allapot !== allapotSzuro) return false;
      if (k) {
        const talalat =
          t.cim.toLowerCase().includes(k) || (t.partner_nev ?? "").toLowerCase().includes(k);
        if (!talalat) return false;
      }
      return true;
    });
  }, [elemek, tipusSzuro, allapotSzuro, kereses]);

  function frissitElem(uj: AdminTaskSor) {
    setElemek((elozo) => elozo.map((t) => (t.id === uj.id ? uj : t)));
  }

  async function letrehoz(mezok: {
    tipus: string;
    cim: string;
    prioritas: number;
    hatarido: string | null;
    felelos_id: number | null;
    partner_nev: string | null;
  }) {
    setHiba(null);
    setMentesFolyamatban(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/tasks", {
        method: "POST",
        body: JSON.stringify(mezok),
      });
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A feladat létrehozása nem sikerült."));
        return;
      }
      const uj = (await res.json()) as AdminTaskSor;
      setElemek((elozo) => [uj, ...elozo]);
      setUrlapNyitva(false);
      router.refresh();
    } finally {
      setMentesFolyamatban(false);
    }
  }

  async function patch(t: AdminTaskSor, valtozas: Partial<Pick<AdminTaskSor, "allapot" | "felelos_id" | "prioritas">>) {
    setHiba(null);
    const res = await authFetch(`/api/v1/admin-agent/tasks/${t.id}`, {
      method: "PATCH",
      body: JSON.stringify({ row_version: t.row_version, ...valtozas }),
    });
    if (res.status === 409) {
      setHiba("A feladatot időközben módosították — töltsd újra az oldalt.");
      return;
    }
    if (!res.ok) {
      setHiba(await hibaSzoveg(res, "A módosítás nem sikerült."));
      return;
    }
    frissitElem((await res.json()) as AdminTaskSor);
    router.refresh();
  }

  return (
    <div>
      {hiba && (
        <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={tipusSzuro}
          onChange={(e) => setTipusSzuro(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary"
        >
          <option value="">Minden típus</option>
          {TIPUS_OPCIOK.map(([ertek, cimke]) => (
            <option key={ertek} value={ertek}>
              {cimke}
            </option>
          ))}
        </select>
        <select
          value={allapotSzuro}
          onChange={(e) => setAllapotSzuro(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary"
        >
          <option value="">Minden állapot</option>
          {Object.entries(ALLAPOT_CIMKE).map(([ertek, cimke]) => (
            <option key={ertek} value={ertek}>
              {cimke}
            </option>
          ))}
        </select>
        <input
          value={kereses}
          onChange={(e) => setKereses(e.target.value)}
          placeholder="Keresés (cím, partner)…"
          className="min-w-[180px] flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted"
        />
        {canCreate && (
          <button
            type="button"
            onClick={() => setUrlapNyitva((v) => !v)}
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-4"
          >
            {urlapNyitva ? "Mégse" : "+ Új feladat"}
          </button>
        )}
      </div>

      {urlapNyitva && canCreate && (
        <UjFeladatUrlap emberek={emberek} onMentes={letrehoz} mentesFolyamatban={mentesFolyamatban} />
      )}

      {szurtElemek.length === 0 ? (
        <div className="rounded-[var(--radius)] border border-dashed border-border px-4 py-8 text-center">
          <p className="text-[13px] text-text-secondary">
            {elemek.length === 0 ? "Még nincs egyetlen feladat sem a munkasorban." : "Nincs a szűrésnek megfelelő feladat."}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                <th className="px-3 py-2 font-medium">Feladat</th>
                <th className="px-3 py-2 font-medium">Típus</th>
                <th className="px-3 py-2 font-medium">Állapot</th>
                <th className="px-3 py-2 font-medium">Felelős</th>
                <th className="px-3 py-2 font-medium">Kockázat</th>
                <th className="px-3 py-2 font-medium">Határidő</th>
              </tr>
            </thead>
            <tbody>
              {szurtElemek.map((t) => (
                <tr key={t.id} className="border-b border-border last:border-0">
                  <td className="px-3 py-2.5">
                    <Link
                      href={`/admin-agent/munkasor/${t.id}`}
                      className="font-medium text-text-primary hover:text-text-accent hover:underline"
                    >
                      {t.cim}
                    </Link>
                    {t.partner_nev && <p className="text-[12px] text-text-muted">{t.partner_nev}</p>}
                    {t.blokkolo_ok && <p className="mt-0.5 text-[12px] text-text-warning">{t.blokkolo_ok}</p>}
                  </td>
                  <td className="px-3 py-2.5 text-text-secondary">{TIPUS_CIMKE[t.tipus] ?? t.tipus}</td>
                  <td className="px-3 py-2.5">
                    {canEdit && KEZI_ALLAPOTOK.includes(t.allapot as (typeof KEZI_ALLAPOTOK)[number]) ? (
                      <select
                        value={t.allapot}
                        onChange={(e) => patch(t, { allapot: e.target.value })}
                        className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-1 text-[12.5px] text-text-primary"
                      >
                        {KEZI_ALLAPOTOK.map((a) => (
                          <option key={a} value={a}>
                            {ALLAPOT_CIMKE[a]}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-text-secondary">{ALLAPOT_CIMKE[t.allapot] ?? t.allapot}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {canEdit ? (
                      <select
                        value={t.felelos_id ?? ""}
                        onChange={(e) => patch(t, { felelos_id: e.target.value ? Number(e.target.value) : null })}
                        className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-1 text-[12.5px] text-text-primary"
                      >
                        <option value="">— nincs —</option>
                        {emberek.map((e) => (
                          <option key={e.id} value={e.id}>
                            {e.nev}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-text-secondary">
                        {t.felelos_id ? emberNev.get(t.felelos_id) ?? `#${t.felelos_id}` : "—"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-text-secondary">{t.kockazat ?? "—"}</td>
                  <td className={`px-3 py-2.5 ${hataridoLejart(t) ? "text-text-danger" : "text-text-secondary"}`}>
                    {t.hatarido ? new Date(t.hatarido).toLocaleDateString("hu-HU") : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function UjFeladatUrlap({
  emberek,
  onMentes,
  mentesFolyamatban,
}: {
  emberek: EmberOpcio[];
  onMentes: (mezok: {
    tipus: string;
    cim: string;
    prioritas: number;
    hatarido: string | null;
    felelos_id: number | null;
    partner_nev: string | null;
  }) => void;
  mentesFolyamatban: boolean;
}) {
  const [tipus, setTipus] = useState(TIPUS_OPCIOK[0][0]);
  const [cim, setCim] = useState("");
  const [partner, setPartner] = useState("");
  const [prioritas, setPrioritas] = useState(0);
  const [hatarido, setHatarido] = useState("");
  const [felelos, setFelelos] = useState("");

  const kuldheto = cim.trim().length > 0 && !mentesFolyamatban;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!kuldheto) return;
        onMentes({
          tipus,
          cim: cim.trim(),
          prioritas,
          hatarido: hatarido || null,
          felelos_id: felelos ? Number(felelos) : null,
          partner_nev: partner.trim() || null,
        });
      }}
      className="mb-4 grid grid-cols-1 gap-3 rounded-[var(--radius)] border border-border bg-surface-3 p-4 sm:grid-cols-2"
    >
      <label className="flex flex-col gap-1 text-[12px] text-text-muted">
        Típus
        <select
          value={tipus}
          onChange={(e) => setTipus(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
        >
          {TIPUS_OPCIOK.map(([ertek, cimke]) => (
            <option key={ertek} value={ertek}>
              {cimke}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[12px] text-text-muted">
        Felelős
        <select
          value={felelos}
          onChange={(e) => setFelelos(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
        >
          <option value="">— nincs —</option>
          {emberek.map((e) => (
            <option key={e.id} value={e.id}>
              {e.nev}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[12px] text-text-muted sm:col-span-2">
        Cím
        <input
          value={cim}
          onChange={(e) => setCim(e.target.value)}
          placeholder="Mit kell elvégezni?"
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted"
        />
      </label>
      <label className="flex flex-col gap-1 text-[12px] text-text-muted">
        Partner (opcionális)
        <input
          value={partner}
          onChange={(e) => setPartner(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
        />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-[12px] text-text-muted">
          Prioritás
          <input
            type="number"
            value={prioritas}
            onChange={(e) => setPrioritas(Number(e.target.value) || 0)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
          />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-text-muted">
          Határidő
          <input
            type="date"
            value={hatarido}
            onChange={(e) => setHatarido(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
          />
        </label>
      </div>
      <div className="sm:col-span-2">
        <button
          type="submit"
          disabled={!kuldheto}
          className="rounded-[var(--radius)] bg-bg-accent px-3.5 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
        >
          {mentesFolyamatban ? "Mentés…" : "Feladat létrehozása"}
        </button>
      </div>
    </form>
  );
}

async function hibaSzoveg(res: Response, alap: string): Promise<string> {
  try {
    const adat = (await res.json()) as { detail?: unknown };
    if (typeof adat.detail === "string") return adat.detail;
  } catch {
    // nem JSON
  }
  return alap;
}
