"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { RendszerAllapot } from "@/lib/api";

/** Lara — a TELJES RENDSZER figyelése (kliens).
 *
 * Lara óránként átnézi az egész HYPE OS-t, és két fajta TÉNY-tudást tanul
 * belőle: modulonkénti rendszerismeretet és projektkódonkénti életutat. Csak
 * olvas; feladatot továbbra is csak adminisztrációs területen végez (lásd
 * backend admin_agent/rendszer.py és enums.ADMIN_FELADATTIPUSOK). */
export function LaraRendszer({ kezdo, canRun }: { kezdo: RendszerAllapot | null; canRun: boolean }) {
  const router = useRouter();
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState(false);

  if (!kezdo) return <p className="text-[13px] text-text-secondary">Az állapot nem tölthető be.</p>;
  const u = kezdo.utolso;

  async function futtat() {
    setUzenet(null);
    setHiba(null);
    setFut(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/system-learning/run", { method: "POST" });
      const d = (await res.json().catch(() => ({}))) as Record<string, unknown> & { detail?: unknown };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "Az átnézés nem sikerült.");
        return;
      }
      setUzenet(
        `Kész: ${d.figyelt_tabla ?? 0} rendszerterületet néztem át — ${d.uj ?? 0} új és ${d.frissitett ?? 0} frissült tény; ` +
          `${d.projektkod ?? 0} projektkód életútja frissült.`,
      );
      router.refresh();
    } finally {
      setFut(false);
    }
  }

  return (
    <div>
      <p className="mb-3 text-[12px] text-text-muted">
        Lara óránként átnézi az egész rendszert — diszpó, forgatások, utómunka, portál, anyagbekérés, eszközök, papírok,
        pénzügy —, és tanul belőle: modulonként mi van és mi mozog, projektkódonként hol tart a munka. Ezt a tervezeteknél
        és az elemzésnél tényként használja (pl. TIG-nél látja, hogy az utómunka leadva). <b>Csak olvas és tanul</b>:
        feladatot továbbra is kizárólag adminisztrációs területen végez, más területhez nem nyúlhat. Személyes és titkos
        adatot nem néz. A tények a{" "}
        <Link href="/admin-agent/tudastar" className="text-text-accent hover:underline">
          Tudástárban
        </Link>{" "}
        látszanak.
      </p>
      {!kezdo.engedelyezve && (
        <div className="mb-3 rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[13px] text-text-secondary">
          A teljes rendszer figyelése ki van kapcsolva —{" "}
          <Link href="/admin-agent/beallitasok" className="text-text-accent hover:underline">
            Beállítások
          </Link>
          .
        </div>
      )}
      {uzenet && <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>}
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}

      {canRun && (
        <button
          type="button"
          disabled={fut || !kezdo.engedelyezve || kezdo.leallitva}
          onClick={futtat}
          className="mb-4 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
        >
          {fut ? "Átnézés…" : "Rendszer átnézése most"}
        </button>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Szam cimke="Figyelt terület" ertek={u?.figyelt_tabla ?? 0} al={u?.kizart_tabla ? `${u.kizart_tabla} kizárva (személyes / technikai)` : undefined} />
        <Szam cimke="Modul-ismeret" ertek={kezdo.modul_tudas} al="tény a Tudástárban" />
        <Szam cimke="Projektkód-életút" ertek={kezdo.projektkod_tudas} al="hol tart a munka" />
        <Szam cimke="Mozgás (30 nap)" ertek={u?.mozgas_30nap ?? 0} al="új + módosított tétel" />
      </div>

      {u?.legaktivabb && u.legaktivabb.length > 0 && (
        <div>
          <p className="mb-1.5 text-[12px] text-text-muted">A legaktívabb területek az elmúlt 30 napban</p>
          <ul className="flex flex-wrap gap-1.5">
            {u.legaktivabb.map((a) => (
              <li key={a.tabla} className="rounded-full border border-border px-2.5 py-0.5 text-[12.5px] text-text-secondary">
                {a.modul} <span className="tabular-nums text-text-muted">{a.mozgas}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Szam({ cimke, ertek, al }: { cimke: string; ertek: number; al?: string }) {
  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
      <p className="text-[11.5px] text-text-muted">{cimke}</p>
      <p className="text-[20px] font-medium tabular-nums text-text-primary">{ertek}</p>
      {al && <p className="text-[11.5px] text-text-muted">{al}</p>}
    </div>
  );
}
