"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** ADMIN-ÁGENS — Tanulás vezérlők (kliens).
 *
 * A háttér-tanuló (distill) és az értékelés (eval) kézi indítása. A distill
 * csak jelölteket készít (nem aktivál), az eval a biztonsági invariánsokat
 * ellenőrzi. Csak `edit` joggal. */
export function AdminTanulasVezerlok({ canRun }: { canRun: boolean }) {
  const router = useRouter();
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState<string | null>(null);

  async function futtat(mit: "observations" | "observations-backfill" | "learning-runs" | "evaluations") {
    setUzenet(null);
    setHiba(null);
    setFolyamatban(mit);
    try {
      const ut =
        mit === "observations-backfill"
          ? "/api/v1/admin-agent/observations?kezdettol=true"
          : `/api/v1/admin-agent/${mit}`;
      const res = await authFetch(ut, { method: "POST" });
      if (!res.ok) {
        setHiba("A futtatás nem sikerült.");
        return;
      }
      const d = (await res.json()) as Record<string, unknown>;
      if (mit === "observations" || mit === "observations-backfill") {
        const k = (d.korszak ?? {}) as { felreteve?: number; tanulas_kezdete?: string };
        setUzenet(
          `Megfigyelés kész: ${d.uj_megfigyeles} új lépés rögzítve a projektkódokról/utókövetésből, ${d.uj_pelda} új példa-jelölt (Tudástár → Példák), ${d.frissitett_pelda} frissítve.` +
            (Number(d.kihagyott_regi) || k.felreteve
              ? ` A tanulás kezdete (${k.tanulas_kezdete ?? "szept. 1."}) előtti / Notion-korszakbeli lezárt rekordokból nem lett jelölt${k.felreteve ? `; ${k.felreteve} régi jelölt félretéve` : ""}.`
              : ""),
        );
      } else if (mit === "learning-runs") {
        setUzenet(
          `Tanulás kész: ${d.feldolgozott_korrekciok} javítás feldolgozva, ${d.uj_szabaly_jeloltek} szabály-jelölt, ${d.sop_keresek} SOP-kérés.`,
        );
      } else {
        setUzenet(
          `Értékelés kész: ${d.sikeres}/${d.osszes} sikeres, kritikus hiba: ${d.kritikus_hiba}, ${d.atment ? "ÁTMENT" : "NEM ment át"}.`,
        );
      }
      router.refresh();
    } finally {
      setFolyamatban(null);
    }
  }

  if (!canRun) {
    return <p className="text-[12px] text-text-muted">A futtatáshoz szerkesztési jogosultság szükséges.</p>;
  }

  return (
    <div>
      {uzenet && (
        <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>
      )}
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={folyamatban !== null}
          onClick={() => futtat("observations")}
          className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
        >
          {folyamatban === "observations" ? "Megfigyelés fut…" : "1. Megfigyelés (projektkód / utókövetés)"}
        </button>
        <button
          type="button"
          disabled={folyamatban !== null}
          onClick={() => futtat("observations-backfill")}
          title="A tanulás kezdete (Beállítások; alap: 2026. szeptember 1.) óta itt keletkezett munkát dolgozza fel"
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[13px] font-medium text-text-secondary hover:bg-surface-4 disabled:opacity-50"
        >
          {folyamatban === "observations-backfill" ? "Visszatekintés fut…" : "Visszatekintés a tanulás kezdetéig"}
        </button>
        <button
          type="button"
          disabled={folyamatban !== null}
          onClick={() => futtat("learning-runs")}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-4 disabled:opacity-50"
        >
          {folyamatban === "learning-runs" ? "Tanulás fut…" : "2. Háttér-tanuló (javításokból)"}
        </button>
        <button
          type="button"
          disabled={folyamatban !== null}
          onClick={() => futtat("evaluations")}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-4 disabled:opacity-50"
        >
          {folyamatban === "evaluations" ? "Értékelés fut…" : "3. Értékelés (eval)"}
        </button>
      </div>
    </div>
  );
}
