"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AsszisztensAllapot, AsszisztensFutas } from "@/lib/api";

/** Lara — az AI ASSZISZTENS munkájának figyelése (kliens).
 *
 * Lara félóránként végignézi, mit kérdeztek az AI asszisztenstől és mit
 * csinált meg: minden lezárt kérés-kör (kérdés + válasz + végrehajtott /
 * elutasított / hibás műveletek) tudás-jelölt lesz a Tudástárban. Az
 * elutasított művelet külön jel: az embernek az nem tetszett (lásd backend
 * admin_agent/asszisztens.py). */
export function LaraAsszisztens({ kezdo, canRun }: { kezdo: AsszisztensAllapot | null; canRun: boolean }) {
  const router = useRouter();
  const [futasok, setFutasok] = useState<AsszisztensFutas[]>(kezdo?.futasok ?? []);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState(false);

  if (!kezdo) return <p className="text-[13px] text-text-secondary">Az állapot nem tölthető be.</p>;

  async function futtat() {
    setUzenet(null);
    setHiba(null);
    setFut(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/assistant-learning/run", { method: "POST" });
      const d = (await res.json().catch(() => ({}))) as AsszisztensFutas & { detail?: unknown };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A feldolgozás nem sikerült.");
        return;
      }
      setFutasok((p) => [{ ...d, id: Date.now(), trigger: "asszisztens:kezi", veg_at: new Date().toISOString() }, ...p]);
      setUzenet(
        `Kész: ${d.feldolgozott_kor ?? 0} lezárt kérést néztem át — ${d.uj ?? 0} új és ${d.frissitett ?? 0} frissült tudás-jelölt` +
          (d.folyamatban ? `; ${d.folyamatban} kérés még folyamatban van vagy jóváhagyásra vár, azt később nézem meg` : "") +
          ".",
      );
      router.refresh();
    } finally {
      setFut(false);
    }
  }

  const temak = Object.entries(kezdo.temak);

  return (
    <div>
      <p className="mb-3 text-[12px] text-text-muted">
        Lara figyeli, mit kérdeztek az AI asszisztenstől, és mit csinált meg: minden lezárt kérésből (a kérdés, a
        válasz, a végrehajtott, a felhasználó által elutasított és a hibás műveletek) tudás-jelölt lesz a{" "}
        <Link href="/admin-agent/tudastar" className="text-text-accent hover:underline">
          Tudástárban
        </Link>
        . Jóváhagyás után a témája szerint (számla, TIG, szerződés, e-mail) és a partner neve alapján használja. Az
        elutasított művelet külön tanulság: az embernek az nem tetszett. Csak olvas; félóránként magától fut.
      </p>
      {!kezdo.engedelyezve && (
        <div className="mb-3 rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[13px] text-text-secondary">
          Az AI asszisztens figyelése ki van kapcsolva —{" "}
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
          {fut ? "Feldolgozás…" : "Asszisztens-kérések feldolgozása most"}
        </button>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Szam cimke="Megfigyelt kérés" ertek={kezdo.kerdesek} />
        <Szam cimke="Végrehajtott művelet" ertek={kezdo.vegrehajtott_muvelet} al={kezdo.hibas_muvelet ? `${kezdo.hibas_muvelet} hibára futott` : undefined} />
        <Szam cimke="Elutasított művelet" ertek={kezdo.elutasitott_muvelet} al="az embernek nem tetszett" />
        <Szam cimke="Tudás-jelölt" ertek={kezdo.jelolt} al={`${kezdo.jovahagyott} már Lara tudásában`} />
      </div>

      {temak.length > 0 && (
        <div className="mb-4">
          <p className="mb-1.5 text-[12px] text-text-muted">Miről kérdeznek a legtöbbet</p>
          <ul className="flex flex-wrap gap-1.5">
            {temak.map(([cimke, n]) => (
              <li key={cimke} className="rounded-full border border-border px-2.5 py-0.5 text-[12.5px] text-text-secondary">
                {cimke} <span className="tabular-nums text-text-muted">{n}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {futasok.length > 0 && (
        <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                <th className="px-3 py-2 font-medium">Mikor</th>
                <th className="px-3 py-2 font-medium">Átnézett kérés</th>
                <th className="px-3 py-2 font-medium">Új jelölt</th>
                <th className="px-3 py-2 font-medium">Frissült</th>
                <th className="px-3 py-2 font-medium">Folyamatban</th>
              </tr>
            </thead>
            <tbody>
              {futasok.slice(0, 10).map((f) => (
                <tr key={f.id} className="border-b border-border last:border-0">
                  <td className="px-3 py-2 text-text-secondary">
                    {f.veg_at ? new Date(f.veg_at).toLocaleString("hu-HU") : "—"}
                    <span className="ml-1 text-[11px] text-text-muted">{f.trigger.endsWith("kezi") ? "kézi" : "ütemezett"}</span>
                  </td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.feldolgozott_kor ?? 0}</td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.uj ?? 0}</td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.frissitett ?? 0}</td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.folyamatban ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
