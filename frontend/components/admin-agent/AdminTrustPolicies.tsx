"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AdminTrustPolicy } from "@/lib/api";
import { TIPUS_CIMKE } from "@/components/admin-agent/allapotok";

const SZINTEK = ["L0", "L1", "L2", "L3", "L4"];
const SZINT_LEIRAS: Record<string, string> = {
  L0: "Árnyék (csak elemzés)",
  L1: "Előkészítés, emberi véglegesítés",
  L2: "Szűk, alacsony kockázatú automatika",
  L3: "Munkasor-önállóság, kivételkezelés",
  L4: "Csak külön engedélyezett, szűk körben",
};

/** ADMIN-ÁGENS — bizalmi szintek (kliens).
 *
 * Feladattípusonként állítható a bizalmi szint. A magasabb szint SEM oldja fel
 * az R3-tiltást (a policy engine dönt); a modell a saját szintjét nem
 * módosíthatja. A módosítás a legerősebb (trust_change) joghoz kötött. */
export function AdminTrustPolicies({
  kezdo,
  canManage,
}: {
  kezdo: AdminTrustPolicy[];
  canManage: boolean;
}) {
  const router = useRouter();
  const [sorok, setSorok] = useState<AdminTrustPolicy[]>(kezdo);
  const [hiba, setHiba] = useState<string | null>(null);
  const [mentve, setMentve] = useState<number | null>(null);

  async function valt(p: AdminTrustPolicy, szint: string) {
    if (!canManage) return;
    setHiba(null);
    const res = await authFetch(`/api/v1/admin-agent/trust-policies/${p.id}`, {
      method: "PATCH",
      body: JSON.stringify({ szint }),
    });
    if (!res.ok) {
      setHiba("A bizalmi szint módosítása nem sikerült.");
      return;
    }
    const uj = (await res.json()) as AdminTrustPolicy;
    setSorok((elozo) => elozo.map((x) => (x.id === uj.id ? uj : x)));
    setMentve(p.id);
    setTimeout(() => setMentve(null), 1500);
    router.refresh();
  }

  return (
    <div>
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      <p className="mb-3 text-[12px] text-text-muted">
        A magasabb szint sem old fel tiltott (R3) műveletet, és a pénzügyi/jogi jóváhagyás továbbra is emberhez kötött.
      </p>
      <ul className="flex flex-col gap-2">
        {sorok.map((p) => (
          <li
            key={p.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5"
          >
            <div>
              <p className="text-[13px] font-medium text-text-primary">{TIPUS_CIMKE[p.tipus] ?? p.tipus}</p>
              <p className="text-[11.5px] text-text-muted">{SZINT_LEIRAS[p.szint] ?? ""}</p>
            </div>
            <div className="flex items-center gap-2">
              {mentve === p.id && <span className="text-[12px] text-text-success">Mentve</span>}
              <select
                value={p.szint}
                disabled={!canManage}
                onChange={(e) => valt(p, e.target.value)}
                className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary disabled:opacity-50"
              >
                {SZINTEK.map((sz) => (
                  <option key={sz} value={sz}>
                    {sz}
                  </option>
                ))}
              </select>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
