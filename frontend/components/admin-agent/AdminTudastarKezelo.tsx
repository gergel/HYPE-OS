"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AdminMemory, AdminRule } from "@/lib/api";
import { TIPUS_CIMKE } from "@/components/admin-agent/allapotok";
import { AdminSzabalyUrlap } from "@/components/admin-agent/AdminSzabalyUrlap";

/** A szabály feltételeinek rövid, emberi címkéje (partner / cél). */
function feltetelCimke(r: AdminRule): string {
  const f = (r.feltetelek ?? {}) as Record<string, unknown>;
  const reszek: string[] = [];
  if (f.partner) reszek.push(`partner: ${String(f.partner_nev ?? f.partner)}`);
  if (f.forras === "visszajatszas") reszek.push("visszajátszásból");
  if (f.forras === "kezi") reszek.push("kézi");
  return reszek.length ? ` · ${reszek.join(" · ")}` : "";
}

const RULE_ALLAPOT: Record<string, string> = {
  draft: "Vázlat",
  pending: "Gépi jelölt",
  active: "Aktív (éles)",
  retired: "Visszavonva",
};

/** Lara — Tudástár kezelő (kliens).
 *
 * Itt dönt az ember arról, mi kerül Lara éles tudásába:
 * - Szabályok: a gépi JELÖLT „Élesítés” gombbal lesz aktív — csak sikeres
 *   értékelés (eval) után és tudás-aktiválási joggal; visszavonható.
 * - Példák: a megfigyelésből (projektkód/utókövetés) és a javításokból született
 *   példa-JELÖLT „Jóváhagyás” után használható a döntésekben; „Elvetés” után soha.
 * Semmi nem kerül észrevétlenül éles használatba. */
export function AdminTudastarKezelo({
  kezdoSzabalyok,
  kezdoPeldak,
  felretettRegi = 0,
  tanulasKezdete = null,
  canEdit,
}: {
  kezdoSzabalyok: AdminRule[];
  kezdoPeldak: AdminMemory[];
  /** A régi korszakból (a tanulás kezdete előtti / Notion) félretett jelöltek száma. */
  felretettRegi?: number;
  tanulasKezdete?: string | null;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [szabalyok, setSzabalyok] = useState(kezdoSzabalyok);
  const [peldak, setPeldak] = useState(kezdoPeldak);
  const [hiba, setHiba] = useState<string | null>(null);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState<string | null>(null);
  const [szuro, setSzuro] = useState<string>("");
  const [kijelolt, setKijelolt] = useState<Set<number>>(new Set());
  const [felretett, setFelretett] = useState<AdminMemory[] | null>(null);
  const [felretettDb, setFelretettDb] = useState(felretettRegi);
  const kezdetSzoveg = tanulasKezdete ? tanulasKezdete.replaceAll("-", ". ") + "." : "2026. 09. 01.";

  async function felretettBetolt() {
    setHiba(null);
    setFolyamatban("felretett");
    try {
      const res = await authFetch("/api/v1/admin-agent/memory?felretett=true&limit=1000");
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A félretett jelöltek betöltése nem sikerült."));
        return;
      }
      const d = (await res.json()) as { elemek: AdminMemory[] };
      setFelretett(d.elemek.filter((m) => m.minosites === "felreteve" && !m.ervenyes && !m.visszavont));
    } finally {
      setFolyamatban(null);
    }
  }

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
      setPeldak((p) => (p.some((x) => x.id === uj.id) ? p.map((x) => (x.id === uj.id ? uj : x)) : [uj, ...p]));
      if (felretett?.some((x) => x.id === uj.id)) {
        setFelretett((f) => (f ? f.filter((x) => x.id !== uj.id) : f));
        setFelretettDb((n) => Math.max(0, n - 1));
      }
      setUzenet(jovahagy ? "Példa jóváhagyva — Lara mostantól használhatja." : "Példa elvetve.");
      router.refresh();
    } finally {
      setFolyamatban(null);
    }
  }

  async function tomeges(muvelet: "jovahagy" | "elvet") {
    const ids = jeloltPelda.filter((m) => kijelolt.has(m.id)).map((m) => m.id).slice(0, 500);
    if (ids.length === 0) return;
    setHiba(null);
    setUzenet(null);
    setFolyamatban("tomeges");
    try {
      const res = await authFetch(`/api/v1/admin-agent/memory/bulk`, {
        method: "POST",
        body: JSON.stringify({ ids, muvelet }),
      });
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A kijelölt példák módosítása nem sikerült."));
        return;
      }
      const d = (await res.json()) as { modositva: number; kihagyva: number };
      const idSet = new Set(ids);
      setPeldak((p) =>
        p.map((x) =>
          idSet.has(x.id) && !(muvelet === "jovahagy" && x.visszavont)
            ? muvelet === "jovahagy"
              ? { ...x, ervenyes: true }
              : { ...x, ervenyes: false, visszavont: true }
            : x,
        ),
      );
      setKijelolt(new Set());
      setUzenet(
        `${d.modositva} példa ${muvelet === "jovahagy" ? "jóváhagyva" : "elvetve"}` +
          (d.kihagyva ? ` (${d.kihagyva} kihagyva, mert korábban elvetették)` : "") +
          ".",
      );
      router.refresh();
    } finally {
      setFolyamatban(null);
    }
  }

  function kijel(id: number) {
    setKijelolt((p) => {
      const uj = new Set(p);
      if (uj.has(id)) uj.delete(id);
      else uj.add(id);
      return uj;
    });
  }

  const aktivSzabaly = szabalyok.filter((r) => r.allapot === "active");
  const jeloltSzabaly = szabalyok.filter((r) => r.allapot === "pending" || r.allapot === "draft");
  const osszesJelolt = peldak.filter((m) => !m.ervenyes && !m.visszavont && m.minosites !== "felreteve");
  const hatokorok = Array.from(new Set(osszesJelolt.map((m) => m.hatokor))).sort();
  const jeloltPelda = szuro ? osszesJelolt.filter((m) => m.hatokor === szuro) : osszesJelolt;
  const kijeloltDb = jeloltPelda.filter((m) => kijelolt.has(m.id)).length;
  const mindKijelolve = jeloltPelda.length > 0 && kijeloltDb === jeloltPelda.length;
  const jovahagyottPelda = peldak.filter((m) => m.ervenyes && !m.visszavont);

  const gomb =
    "rounded-[var(--radius)] px-2.5 py-1 text-[12px] font-medium disabled:opacity-50";

  return (
    <div className="flex flex-col gap-4">
      {hiba && <div className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      {uzenet && <div className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>}

      <Szekcio
        cim={`Jóváhagyásra váró példák (${osszesJelolt.length})`}
        leiras={`A megfigyelésből (projektkódok, utókövetés) és a javításokból született példák. Jóváhagyás után Lara ezekből tanul a hasonló eseteknél. Csak a tanulás kezdete (${kezdetSzoveg}) óta a HYPE OS-ben keletkezett munkából készül jelölt — a Notion-korszak rekordjaiból nem. Többet is kipipálhatsz — de csak azt hagyd jóvá, amit át is néztél.`}
      >
        {osszesJelolt.length > 0 && (
          <li className="flex flex-wrap items-center gap-2 pb-1">
            <select
              value={szuro}
              onChange={(e) => {
                setSzuro(e.target.value);
                setKijelolt(new Set());
              }}
              className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary"
            >
              <option value="">Minden típus ({osszesJelolt.length})</option>
              {hatokorok.map((h) => (
                <option key={h} value={h}>
                  {TIPUS_CIMKE[h] ?? h} ({osszesJelolt.filter((m) => m.hatokor === h).length})
                </option>
              ))}
            </select>
            {canEdit && (
              <>
                <label className="flex items-center gap-1.5 text-[12px] text-text-secondary">
                  <input
                    type="checkbox"
                    checked={mindKijelolve}
                    onChange={() =>
                      setKijelolt(mindKijelolve ? new Set() : new Set(jeloltPelda.slice(0, 500).map((m) => m.id)))
                    }
                  />
                  A listázottak kijelölése
                </label>
                <button
                  type="button"
                  disabled={kijeloltDb === 0 || folyamatban === "tomeges"}
                  onClick={() => tomeges("jovahagy")}
                  className={`${gomb} bg-bg-success text-text-success`}
                >
                  Kijelöltek jóváhagyása ({kijeloltDb})
                </button>
                <button
                  type="button"
                  disabled={kijeloltDb === 0 || folyamatban === "tomeges"}
                  onClick={() => tomeges("elvet")}
                  className={`${gomb} border border-border text-text-secondary hover:bg-surface-4`}
                >
                  Kijelöltek elvetése ({kijeloltDb})
                </button>
              </>
            )}
          </li>
        )}
        {jeloltPelda.length === 0 ? (
          <Ures szoveg="Nincs jóváhagyásra váró példa. Futtasd a Tanulás oldalon a „Megfigyelés” lépést." />
        ) : (
          jeloltPelda.map((m) => (
            <Sor
              key={m.id}
              cimke={TIPUS_CIMKE[m.hatokor] ?? m.hatokor}
              szoveg={m.tartalom}
              forras={m.forras}
              kijelolve={canEdit ? kijelolt.has(m.id) : undefined}
              onKijel={() => kijel(m.id)}
            >
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

      {felretettDb > 0 && (
        <Szekcio
          cim={`Félretett régi jelöltek (${felretettDb})`}
          leiras={`A tanulás kezdete (${kezdetSzoveg}) előtti, illetve a Notionből hozott rekordokból korábban készült jelöltek. Nem törlődtek, de Lara nem kér rájuk döntést. Ha egy régi eset mégis jó minta, itt egyenként jóváhagyhatod — a jóváhagyott régi példát Lara csak az újabbak után, kisebb súllyal használja.`}
        >
          {felretett === null ? (
            <li>
              <button
                type="button"
                disabled={folyamatban === "felretett"}
                onClick={felretettBetolt}
                className={`${gomb} border border-border text-text-secondary hover:bg-surface-4`}
              >
                {folyamatban === "felretett" ? "Betöltés…" : "Megjelenítés"}
              </button>
            </li>
          ) : felretett.length === 0 ? (
            <Ures szoveg="Nincs félretett régi jelölt." />
          ) : (
            felretett.map((m) => (
              <Sor
                key={m.id}
                cimke={`${TIPUS_CIMKE[m.hatokor] ?? m.hatokor} · régi`}
                szoveg={m.tartalom}
                forras={m.forras}
              >
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
      )}

      <Szekcio
        cim={`Szabály-jelöltek (${jeloltSzabaly.length})`}
        leiras="Gépi javaslatok (ismétlődő javításokból és a visszajátszásból) és a kézzel felvett vázlatok. Élesítés csak sikeres értékelés (Tanulás → 3. Értékelés) után lehetséges."
      >
        {canEdit && (
          <AdminSzabalyUrlap
            onLetrehozva={(r) => {
              setSzabalyok((p) => [r, ...p]);
              setUzenet("Szabály vázlatként mentve — a Szabály-jelöltek között élesítheted (sikeres értékelés után).");
            }}
          />
        )}
        {jeloltSzabaly.length === 0 ? (
          <Ures szoveg="Nincs szabály-jelölt. Ismétlődő javításokból, a visszajátszásból (Tanulás oldal) vagy kézzel születik." />
        ) : (
          jeloltSzabaly.map((r) => (
            <Sor
              key={r.id}
              cimke={`${TIPUS_CIMKE[r.hatokor] ?? r.hatokor} · ${RULE_ALLAPOT[r.allapot] ?? r.allapot}${feltetelCimke(r)}`}
              szoveg={`${r.cim} — ${r.tartalom}`}
            >
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
              <Sor
                key={`r${r.id}`}
                cimke={`Szabály · ${TIPUS_CIMKE[r.hatokor] ?? r.hatokor}${feltetelCimke(r)}`}
                szoveg={`${r.cim} — ${r.tartalom}`}
              >
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
              <Sor
                key={`m${m.id}`}
                cimke={`Példa · ${TIPUS_CIMKE[m.hatokor] ?? m.hatokor}${m.regi_korszak ? " · régi (kisebb súllyal)" : ""}`}
                szoveg={m.tartalom}
                forras={m.forras}
              >
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
  kijelolve,
  onKijel,
  children,
}: {
  cimke: string;
  szoveg: string;
  forras?: string | null;
  kijelolve?: boolean;
  onKijel?: () => void;
  children?: React.ReactNode;
}) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
      {kijelolve !== undefined && (
        <input type="checkbox" checked={kijelolve} onChange={onKijel} className="mt-1" aria-label="Kijelölés" />
      )}
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
