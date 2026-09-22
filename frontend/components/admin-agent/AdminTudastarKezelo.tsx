"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AdminMemory, AdminRule } from "@/lib/api";
import { TIPUS_CIMKE } from "@/components/admin-agent/allapotok";

const RULE_ALLAPOT: Record<string, string> = {
  draft: "Vázlat",
  pending: "Gépi jelölt",
  active: "Aktív (éles)",
  retired: "Visszavonva",
};

/** ADMIN-ÁGENS — Tudástár kezelő (kliens).
 *
 * Itt dönt az ember arról, mi kerül az ügynök éles tudásába:
 * - Szabályok: a gépi JELÖLT „Élesítés” gombbal lesz aktív — csak sikeres
 *   értékelés (eval) után és tudás-aktiválási joggal; visszavonható.
 * - Példák: a megfigyelésből (projektkód/utókövetés) és a javításokból született
 *   példa-JELÖLT „Jóváhagyás” után használható a döntésekben; „Elvetés” után soha.
 * Semmi nem kerül észrevétlenül éles használatba. */
export function AdminTudastarKezelo({
  kezdoSzabalyok,
  kezdoPeldak,
  canEdit,
}: {
  kezdoSzabalyok: AdminRule[];
  kezdoPeldak: AdminMemory[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [szabalyok, setSzabalyok] = useState(kezdoSzabalyok);
  const [peldak, setPeldak] = useState(kezdoPeldak);
  const [hiba, setHiba] = useState<string | null>(null);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState<string | null>(null);

  async function hibaSzoveg(res: Response, alap: string) {
    try {
      const d = (await res.json()) as { detail?: unknown };
      if (typeof d.detail === "string") return d.detail;
    } catch {
      // nem JSON
    }
    return alap;
  }

  async function szabalyAllapot(r: AdminRule, allapot: string) {
    setHiba(null);
    setUzenet(null);
    setFolyamatban(`r${r.id}`);
    try {
      const res = await authFetch(`/api/v1/admin-agent/rules/${r.id}`, {
        method: "PATCH",
        body: JSON.stringify({ allapot }),
      });
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A szabály módosítása nem sikerült."));
        return;
      }
      const uj = (await res.json()) as AdminRule;
      setSzabalyok((p) => p.map((x) => (x.id === uj.id ? uj : x)));
      setUzenet(allapot === "active" ? "A szabály élesítve — mostantól segíti a döntéseket." : "A szabály visszavonva.");
      router.refresh();
    } finally {
      setFolyamatban(null);
    }
  }

  async function peldaDontes(m: AdminMemory, jovahagy: boolean) {
    setHiba(null);
    setUzenet(null);
    setFolyamatban(`m${m.id}`);
    try {
      const res = await authFetch(`/api/v1/admin-agent/memory/${m.id}`, {
        method: "PATCH",
        body: JSON.stringify(jovahagy ? { ervenyes: true } : { visszavont: true }),
      });
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A példa módosítása nem sikerült."));
        return;
      }
      const uj = (await res.json()) as AdminMemory;
      setPeldak((p) => p.map((x) => (x.id === uj.id ? uj : x)));
      setUzenet(jovahagy ? "Példa jóváhagyva — az ügynök mostantól használhatja." : "Példa elvetve.");
      router.refresh();
    } finally {
      setFolyamatban(null);
    }
  }

  const aktivSzabaly = szabalyok.filter((r) => r.allapot === "active");
  const jeloltSzabaly = szabalyok.filter((r) => r.allapot === "pending" || r.allapot === "draft");
  const jeloltPelda = peldak.filter((m) => !m.ervenyes && !m.visszavont);
  const jovahagyottPelda = peldak.filter((m) => m.ervenyes && !m.visszavont);

  const gomb =
    "rounded-[var(--radius)] px-2.5 py-1 text-[12px] font-medium disabled:opacity-50";

  return (
    <div className="flex flex-col gap-4">
      {hiba && <div className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      {uzenet && <div className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>}

      <Szekcio
        cim={`Jóváhagyásra váró példák (${jeloltPelda.length})`}
        leiras="A megfigyelésből (projektkódok, utókövetés) és a javításokból született példák. Jóváhagyás után az ügynök ezekből tanul a hasonló eseteknél."
      >
        {jeloltPelda.length === 0 ? (
          <Ures szoveg="Nincs jóváhagyásra váró példa. Futtasd a Tanulás oldalon a „Megfigyelés” lépést." />
        ) : (
          jeloltPelda.map((m) => (
            <Sor key={m.id} cimke={TIPUS_CIMKE[m.hatokor] ?? m.hatokor} szoveg={m.tartalom} forras={m.forras}>
              {canEdit && (
                <>
                  <button
                    type="button"
                    disabled={folyamatban === `m${m.id}`}
                    onClick={() => peldaDontes(m, true)}
                    className={`${gomb} bg-bg-success text-text-success`}
                  >
                    Jóváhagyás
                  </button>
                  <button
                    type="button"
                    disabled={folyamatban === `m${m.id}`}
                    onClick={() => peldaDontes(m, false)}
                    className={`${gomb} border border-border text-text-secondary hover:bg-surface-4`}
                  >
                    Elvetés
                  </button>
                </>
              )}
            </Sor>
          ))
        )}
      </Szekcio>

      <Szekcio
        cim={`Szabály-jelöltek (${jeloltSzabaly.length})`}
        leiras="Gépi javaslatok ismétlődő javításokból. Élesítés csak sikeres értékelés (Tanulás → 3. Értékelés) után lehetséges."
      >
        {jeloltSzabaly.length === 0 ? (
          <Ures szoveg="Nincs szabály-jelölt. Legalább két hasonló javításból születik egy." />
        ) : (
          jeloltSzabaly.map((r) => (
            <Sor key={r.id} cimke={`${r.hatokor} · ${RULE_ALLAPOT[r.allapot] ?? r.allapot}`} szoveg={`${r.cim} — ${r.tartalom}`}>
              {canEdit && (
                <>
                  <button
                    type="button"
                    disabled={folyamatban === `r${r.id}`}
                    onClick={() => szabalyAllapot(r, "active")}
                    className={`${gomb} bg-bg-success text-text-success`}
                  >
                    Élesítés
                  </button>
                  <button
                    type="button"
                    disabled={folyamatban === `r${r.id}`}
                    onClick={() => szabalyAllapot(r, "retired")}
                    className={`${gomb} border border-border text-text-secondary hover:bg-surface-4`}
                  >
                    Elvetés
                  </button>
                </>
              )}
            </Sor>
          ))
        )}
      </Szekcio>

      <Szekcio cim={`Éles tudás — aktív szabályok (${aktivSzabaly.length}) és jóváhagyott példák (${jovahagyottPelda.length})`}>
        {aktivSzabaly.length === 0 && jovahagyottPelda.length === 0 ? (
          <Ures szoveg="Még nincs éles tudás. A fenti jelöltek jóváhagyásával épül fel." />
        ) : (
          <>
            {aktivSzabaly.map((r) => (
              <Sor key={`r${r.id}`} cimke={`Szabály · ${r.hatokor}`} szoveg={`${r.cim} — ${r.tartalom}`}>
                {canEdit && (
                  <button
                    type="button"
                    disabled={folyamatban === `r${r.id}`}
                    onClick={() => szabalyAllapot(r, "retired")}
                    className={`${gomb} border border-border text-text-secondary hover:bg-surface-4`}
                  >
                    Visszavonás
                  </button>
                )}
              </Sor>
            ))}
            {jovahagyottPelda.map((m) => (
              <Sor key={`m${m.id}`} cimke={`Példa · ${TIPUS_CIMKE[m.hatokor] ?? m.hatokor}`} szoveg={m.tartalom} forras={m.forras}>
                {canEdit && (
                  <button
                    type="button"
                    disabled={folyamatban === `m${m.id}`}
                    onClick={() => peldaDontes(m, false)}
                    className={`${gomb} border border-border text-text-secondary hover:bg-surface-4`}
                  >
                    Visszavonás
                  </button>
                )}
              </Sor>
            ))}
          </>
        )}
      </Szekcio>
    </div>
  );
}

function Szekcio({ cim, leiras, children }: { cim: string; leiras?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <p className="t-card mb-1">{cim}</p>
      {leiras && <p className="mb-3 text-[12px] text-text-muted">{leiras}</p>}
      <ul className="flex flex-col gap-2">{children}</ul>
    </div>
  );
}

function Sor({
  cimke,
  szoveg,
  forras,
  children,
}: {
  cimke: string;
  szoveg: string;
  forras?: string | null;
  children?: React.ReactNode;
}) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
      <div className="min-w-0 flex-1">
        <span className="mb-0.5 inline-block rounded-[var(--radius)] bg-surface-2 px-2 py-0.5 text-[11px] text-text-secondary">
          {cimke}
        </span>
        <p className="text-[13px] text-text-primary">{szoveg}</p>
        {forras && <p className="text-[11px] text-text-muted">forrás: {forras}</p>}
      </div>
      {children && <div className="flex shrink-0 gap-1.5">{children}</div>}
    </li>
  );
}

function Ures({ szoveg }: { szoveg: string }) {
  return <li className="text-[13px] text-text-secondary">{szoveg}</li>;
}
