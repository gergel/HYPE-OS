"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AdminApprovalSor } from "@/lib/api";
import { TIPUS_CIMKE } from "@/components/admin-agent/allapotok";

/** HYRON — JÓVÁHAGYÁSOK (kliens).
 *
 * A jóváhagyás a KONKRÉT javaslat payload-hash-éhez kötődik: a szerver a
 * beküldött hash-t egyezteti, és a végrehajtást a guard-láncon (policy,
 * kapcsolók, idempotencia) engedi át. Biztonságos alapállásban (modul KI /
 * mellékhatás TILT) a jóváhagyás rögzül, de a végrehajtás blokkolt — ezt a
 * visszajelzés jelzi. Nincs „mindent jóváhagyó" tömeggomb. */
export function AdminJovahagyasok({
  kezdoElemek,
  canDecide,
}: {
  kezdoElemek: AdminApprovalSor[];
  canDecide: boolean;
}) {
  const router = useRouter();
  const [elemek, setElemek] = useState<AdminApprovalSor[]>(kezdoElemek);
  const [hiba, setHiba] = useState<string | null>(null);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState<number | null>(null);

  async function dontes(a: AdminApprovalSor, jovahagy: boolean) {
    setHiba(null);
    setUzenet(null);
    setFolyamatban(a.approval_id);
    try {
      const ut = jovahagy
        ? `/api/v1/admin-agent/approvals/${a.approval_id}/approve`
        : `/api/v1/admin-agent/approvals/${a.approval_id}/reject`;
      const res = await authFetch(ut, {
        method: "POST",
        body: JSON.stringify(jovahagy ? { payload_hash: a.payload_hash } : {}),
      });
      if (res.status === 409) {
        setHiba(await hibaSzoveg(res, "A javaslat időközben megváltozott — töltsd újra."));
        return;
      }
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A művelet nem sikerült."));
        return;
      }
      // Sikeres döntés: a sort levesszük a listáról, és jelezzük a végrehajtás sorsát.
      setElemek((elozo) => elozo.filter((x) => x.approval_id !== a.approval_id));
      if (jovahagy) {
        const adat = (await res.json()) as { execution?: { allapot?: string; eredmeny?: Record<string, unknown> } };
        const all = adat.execution?.allapot;
        if (all === "succeeded") setUzenet("Jóváhagyva és végrehajtva.");
        else {
          const ok = (adat.execution?.eredmeny as { blokk_ok?: string } | undefined)?.blokk_ok;
          setUzenet(`Jóváhagyva. A végrehajtás jelenleg blokkolt${ok ? ` (${ok})` : ""}.`);
        }
      } else {
        setUzenet("Elutasítva.");
      }
      router.refresh();
    } finally {
      setFolyamatban(null);
    }
  }

  if (elemek.length === 0) {
    return (
      <div>
        {uzenet && (
          <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>
        )}
        <div className="rounded-[var(--radius)] border border-dashed border-border px-4 py-8 text-center">
          <p className="text-[13px] text-text-secondary">Nincs jóváhagyásra váró művelet.</p>
          <p className="mx-auto mt-1 max-w-xl text-[12px] text-text-muted">
            Amikor HYRON éles feladatokon dolgozik, az emberi döntést igénylő műveletek itt jelennek meg. A
            jóváhagyás a konkrét művelethez kötött; a végrehajtás a szerver-oldali szabályrendszeren megy át.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      {uzenet && (
        <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>
      )}
      <ul className="flex flex-col gap-3">
        {elemek.map((a) => (
          <li key={a.approval_id} className="rounded-[var(--radius)] border border-border bg-surface-3 p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              {a.kockazat && (
                <span className="rounded-[var(--radius)] bg-bg-warning px-2 py-0.5 text-[12px] font-medium text-text-warning">
                  {a.kockazat}
                </span>
              )}
              <span className="text-[13px] font-medium text-text-primary">{a.cim}</span>
              <span className="text-[12px] text-text-muted">
                · {TIPUS_CIMKE[a.tipus] ?? a.tipus} · {a.eszkoz}
              </span>
            </div>
            <pre className="mb-3 max-h-48 overflow-auto rounded-[var(--radius)] bg-surface-2 p-2.5 text-[11.5px] text-text-secondary">
              {JSON.stringify(a.payload, null, 2)}
            </pre>
            {canDecide ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={folyamatban === a.approval_id}
                  onClick={() => dontes(a, true)}
                  className="rounded-[var(--radius)] bg-bg-success px-3 py-1.5 text-[13px] font-medium text-text-success disabled:opacity-50"
                >
                  Jóváhagyás és végrehajtás
                </button>
                <button
                  type="button"
                  disabled={folyamatban === a.approval_id}
                  onClick={() => dontes(a, false)}
                  className="rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-4 disabled:opacity-50"
                >
                  Elutasítás
                </button>
              </div>
            ) : (
              <p className="text-[12px] text-text-muted">A döntéshez jóváhagyási jogosultság szükséges.</p>
            )}
          </li>
        ))}
      </ul>
    </div>
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
