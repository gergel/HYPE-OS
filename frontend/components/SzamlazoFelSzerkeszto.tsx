"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { ProjektSzamlazoNezet } from "@/lib/api";

/** Ki számláz kinek a munkájáért ezen a projekten?
 *
 * Alapból mindenki magának. Két eset miatt kell átállítani:
 *
 * - valaki MÁS nevében számláz (a projekt két stábtagjának egy számlája van) -
 *   ilyenkor egy szerződés és egy TIG megy ki, a számlázó nevére;
 * - az embert egy CÉG küldte, a cég számláz - ha a cégnek van keretszerződése,
 *   eseti szerződés sem kell.
 *
 * A lefedett ember STÁBTAG marad: kap diszpót, rajta van a projekten, benne van
 * a jövedelmezőségben. Csak a papír megy a másik fél nevére.
 *
 * Ha egy munkáról már készült TIG, a backend nem engedi átállítani - előbb a
 * TIG-et kell rendezni (lásd routes/project_szamlazok.py). */
export function SzamlazoFelSzerkeszto({
  nezet,
  cegek,
  emberek = [],
  canEdit,
}: {
  nezet: ProjektSzamlazoNezet;
  /** Minden aktív cég - a tagsági javaslaton felül bármelyik választható. */
  cegek: { id: number; nev: string }[];
  /** Minden (nem belsős) munkatárs - a javaslatokon felül olyan is
   * választható, aki NINCS rajta ezen a projekten. Ez valós eset: van, hogy a
   * számlát olyan vállalkozó állítja ki, aki maga nem volt a forgatáson (pl. a
   * csapat "gazdája" számláz a nála dolgozókért). A stábtagságnak semmi köze
   * ahhoz, ki a számlázó fél - a backend sem kötötte ki soha (lásd
   * routes/project_szamlazok.py set_szamlazo), csak a felület nem kínálta fel. */
  emberek?: { id: number; full_name: string }[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<number | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  if (nezet.sorok.length === 0) {
    return (
      <p className="text-[13px] text-text-secondary">
        Nincs olyan (nem belsős) stábtag a projekten, akinél a számlázás kérdés lenne.
      </p>
    );
  }

  async function allit(employeeId: number, szamlazo: string) {
    setBusyId(employeeId);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/projekt-szamlazok/${nezet.project_id}/${employeeId}`, {
        method: "PUT",
        body: JSON.stringify({ szamlazo: szamlazo || null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <p className="mb-3 text-[12.5px] text-text-muted">
        Alapból mindenki a saját nevében számláz. Itt lehet beállítani, ha valakiért másik ember vagy egy cég állítja
        ki a számlát – ilyenkor a szerződés és a TIG is az ő nevére megy, egyben. A számlázó fél olyan is lehet, aki
        nincs rajta ezen a projekten. A lefedett ember stábtag marad: diszpót kap és rajta van a projekten.
      </p>
      {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Stábtag</th>
              <th className="py-1.5 text-left font-medium text-text-secondary">Ki számláz a munkájáért</th>
            </tr>
          </thead>
          <tbody>
            {nezet.sorok.map((sor) => {
              // A cégeket a tagsági javaslatokon FELÜL is felkínáljuk: a tagság
              // csak javaslat, bárki beosztható bármelyik cég alá (lásd backend
              // models/vallalkozas.py).
              const javasoltKulcsok = new Set(sor.javaslatok.map((j) => j.szamlazo));
              const tovabbiCegek = cegek
                .map((c) => ({ szamlazo: `v${c.id}`, nev: c.nev }))
                .filter((c) => !javasoltKulcsok.has(c.szamlazo));
              // Ugyanez emberekre: aki nincs a stábban, az sem javaslat, de
              // választható. Magát a lefedett embert kihagyjuk (ő a "saját
              // nevében" opció), és azokat is, akik már javaslatként szerepelnek.
              const tovabbiEmberek = emberek
                .filter((e) => e.id !== sor.employee_id)
                .map((e) => ({ szamlazo: `e${e.id}`, nev: e.full_name }))
                .filter((e) => !javasoltKulcsok.has(e.szamlazo));
              return (
                <tr key={sor.employee_id} className="border-b border-border last:border-0">
                  <td className="py-2.5 pr-6">
                    <a href={`/csapat/${sor.employee_id}`} className="text-text-accent hover:underline">
                      {sor.full_name}
                    </a>
                  </td>
                  <td className="py-2.5">
                    {canEdit ? (
                      <select
                        value={sor.szamlazo}
                        disabled={busyId === sor.employee_id}
                        onChange={(e) => allit(sor.employee_id, e.target.value)}
                        className="min-w-[260px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary focus:outline-none disabled:opacity-50"
                      >
                        {sor.javaslatok.map((j) => (
                          <option key={j.szamlazo} value={j.szamlazo}>
                            {j.forras === "sajat" ? `${j.nev} (saját nevében)` : j.nev}
                            {j.forras === "vallalkozas-tagsag" ? " – cége" : ""}
                          </option>
                        ))}
                        {tovabbiEmberek.length > 0 && (
                          <optgroup label="További munkatársak (nincsenek a stábban)">
                            {tovabbiEmberek.map((e) => (
                              <option key={e.szamlazo} value={e.szamlazo}>
                                {e.nev}
                              </option>
                            ))}
                          </optgroup>
                        )}
                        {tovabbiCegek.length > 0 && (
                          <optgroup label="További cégek">
                            {tovabbiCegek.map((c) => (
                              <option key={c.szamlazo} value={c.szamlazo}>
                                {c.nev}
                              </option>
                            ))}
                          </optgroup>
                        )}
                      </select>
                    ) : (
                      <span className={sor.felulirva ? "text-text-primary" : "text-text-muted"}>
                        {sor.felulirva ? sor.szamlazo_nev : "Saját nevében"}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
