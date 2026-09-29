"use client";

import { useState } from "react";
import { authFetch } from "@/lib/authFetch";

type Lepes = { cim: string; ok: boolean; ms: number; valasz?: string; hiba?: string; vegok?: string };
type Eredmeny = { ok: boolean; modell: string; lepesek: Lepes[]; hiba?: string };

/** Élő kapcsolat-próba a nyelvi modellel: ha Lara nem tud válaszolni, ez
 * megmutatja a pontos okot (kulcs, kvóta, rossz modellnév, elutasított
 * beállítás). Adatot nem olvas és nem ír. */
export function LaraModellEllenorzes({ canManage }: { canManage: boolean }) {
  const [busy, setBusy] = useState(false);
  const [e, setE] = useState<Eredmeny | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  async function ellenoriz() {
    setBusy(true);
    setHiba(null);
    setE(null);
    try {
      const res = await authFetch("/api/v1/admin-agent/modell/ellenorzes", { method: "POST" });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : `Az ellenőrzés nem sikerült (${res.status}).`);
        return;
      }
      setE(d as Eredmeny);
    } catch {
      setHiba("A szerver nem válaszolt.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-[var(--radius)] border border-border px-4 py-3.5">
      <p className="text-[13px] font-medium text-text-primary">Nyelvi modell kapcsolata</p>
      <p className="mt-0.5 text-[12px] text-text-muted">
        Ha Lara a kérdésekre nem tud rendesen válaszolni, ez kipróbálja a kapcsolatot (egy egyszerű hívás, majd egy Lara
        eszközeivel, a beszélgetés beállításaival), és megmutatja a pontos okot. Adatot nem olvas és nem ír.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={!canManage || busy}
          onClick={ellenoriz}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {busy ? "Ellenőrzöm…" : "Modell-kapcsolat ellenőrzése"}
        </button>
        {e && (
          <span className={`text-[12.5px] ${e.ok ? "text-text-success" : "text-text-danger"}`}>
            {e.ok ? "Rendben" : "Hiba"} · modell: {e.modell}
          </span>
        )}
      </div>
      {hiba && <p className="mt-2 text-[12.5px] text-text-danger">{hiba}</p>}
      {e?.hiba && <p className="mt-2 text-[12.5px] text-text-danger">{e.hiba}</p>}
      {e && e.lepesek.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1 text-[12.5px]">
          {e.lepesek.map((l) => (
            <li key={l.cim} className={l.ok ? "text-text-secondary" : "text-text-danger"}>
              <span className="font-medium">{l.ok ? "✓" : "✗"}</span> {l.cim} ({l.ms} ms)
              {l.hiba ? ` — ${l.hiba}` : l.ok ? "" : ` — nem jött válasz${l.vegok ? ` (${l.vegok})` : ""}`}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
