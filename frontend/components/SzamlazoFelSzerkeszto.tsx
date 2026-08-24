"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { KeresosSelect, type KeresosOpcio } from "@/components/KeresosSelect";
import { IndoklasDialog } from "@/components/IndoklasDialog";
import { MegbeszeltDijDialog } from "@/components/MegbeszeltDijDialog";
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
  canEdit,
}: {
  nezet: ProjektSzamlazoNezet;
  /** Minden aktív cég - a tagsági javaslaton felül bármelyik választható. */
  cegek: { id: number; nev: string }[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<number | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  // Melyik sornál kérjük épp a "hova és miért került a kiadásba" magyarázatot.
  const [kiadasIndokSor, setKiadasIndokSor] = useState<ProjektSzamlazoNezet["sorok"][number] | null>(null);
  // Melyik sor megbeszélt díját szerkesztjük épp. A díjat a stábtag
  // felvételekor kérdezzük meg (lásd StabLinker), de utólag is állítható:
  // sokszor csak később egyeznek meg, vagy változik az összeg.
  const [dijSor, setDijSor] = useState<ProjektSzamlazoNezet["sorok"][number] | null>(null);

  if (nezet.sorok.length === 0) {
    return (
      <p className="text-[13px] text-text-secondary">
        Nincs olyan (nem belsős) stábtag a projekten, akinél a számlázás kérdés lenne.
      </p>
    );
  }

  /** "Projekt kiadásként elszámolva" - a stábtag marad, csak papír nem kell
   * tőle: a díja egy másik tételben (pl. a technika bérleti árában) szerepel. */
  async function kiadaskentAllit(employeeId: number, ertek: boolean, megjegyzes?: string) {
    setKiadasIndokSor(null);
    setBusyId(employeeId);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/projekt-szamlazok/${nezet.project_id}/${employeeId}/kiadaskent`, {
        method: "PUT",
        body: JSON.stringify({ kiadaskent_elszamolva: ertek, kiadas_megjegyzes: megjegyzes ?? null }),
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

  /** A lebeszélt napidíj mentése - ebből nyílik meg a szerződés és a TIG
   * piszkozata (lásd backend services/megbeszelt_dij.py). */
  async function dijatAllit(employeeId: number, dij: number | null, megjegyzes: string) {
    setDijSor(null);
    setBusyId(employeeId);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/projekt-szamlazok/${nezet.project_id}/${employeeId}/dij`, {
        method: "PUT",
        body: JSON.stringify({ megbeszelt_dij: dij, dij_megjegyzes: megjegyzes || null }),
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
      <p className="mb-3 text-[12.5px] text-text-muted">
        A <strong className="text-text-secondary">Projekt kiadásként</strong> jelölés azoké, akiknek a díja egy másik
        tételben (pl. a technika bérleti árában) már benne van: tőlük nem kérünk sem szerződést, sem TIG-et, mert nem
        a munkájukért fizetünk külön. Stábtagok maradnak, és utólag is átjelölhetők.
      </p>
      <p className="mb-3 text-[12.5px] text-text-muted">
        A <strong className="text-text-secondary">Megbeszélt díj</strong> az, amennyiért az illető ezt a napot
        vállalta – ezt a stábtag felvételekor kérdezzük meg, de itt is megadható vagy javítható. Ha van, a szerződése
        és a TIG-je automatikusan ezzel az összeggel nyílik meg.
      </p>
      {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}
      <div className="overflow-x-auto">
        <table className="os-table min-w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Stábtag</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Ki számláz a munkájáért</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Megbeszélt díj</th>
              <th className="py-1.5 text-left font-medium text-text-secondary">Projekt kiadásként</th>
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
              // A listát a SZERVER adja (nezet.valaszthato_emberek): azt, hogy
              // ki lehet számlázó fél, a belsős IDŐSZAKOK döntik el a forgatás
              // napjára nézve, és az az adat csak ott van meg. Aki nincs a
              // stábban, ugyanúgy választható - a számlát gyakran olyan
              // vállalkozó állítja ki, aki maga nem volt a forgatáson.
              const tovabbiEmberek = nezet.valaszthato_emberek
                .filter((e) => e.szamlazo !== `e${sor.employee_id}` && !javasoltKulcsok.has(e.szamlazo));
              const opciok: KeresosOpcio[] = [
                ...sor.javaslatok.map((j) => ({
                  value: j.szamlazo,
                  label:
                    j.forras === "sajat"
                      ? `${j.nev} (saját nevében)`
                      : j.forras === "vallalkozas-tagsag"
                        ? `${j.nev} – cége`
                        : j.nev,
                  group: "Javaslatok",
                })),
                ...tovabbiEmberek.map((e) => ({
                  value: e.szamlazo,
                  label: e.nev,
                  group: "További munkatársak (nincsenek a stábban)",
                })),
                ...tovabbiCegek.map((c) => ({
                  value: c.szamlazo,
                  label: c.nev,
                  group: "További cégek",
                })),
              ];
              return (
                <tr key={sor.employee_id} className="border-b border-border last:border-0">
                  <td className="py-2.5 pr-6">
                    <a href={`/csapat/${sor.employee_id}`} className="text-text-accent hover:underline">
                      {sor.full_name}
                    </a>
                  </td>
                  <td className="py-2.5 pr-6">
                    {canEdit ? (
                      // Kereshető legördülő, nem natív <select>: a lista minden
                      // munkatársat és céget tartalmaz, abban a böngésző
                      // betű-ugrálásával nem lehet megtalálni senkit.
                      <KeresosSelect
                        value={sor.szamlazo}
                        options={opciok}
                        disabled={busyId === sor.employee_id}
                        onChange={(ertek) => allit(sor.employee_id, ertek)}
                        className="min-w-[260px]"
                      />
                    ) : (
                      <span className={sor.felulirva ? "text-text-primary" : "text-text-muted"}>
                        {sor.felulirva ? sor.szamlazo_nev : "Saját nevében"}
                      </span>
                    )}
                  </td>
                  {/* Mennyiért vállalta ezt a napot: a stábtag felvételekor
                      kérdezzük meg (lásd StabLinker), de itt utólag is
                      megadható vagy javítható. Ebből nyílik meg a szerződés és
                      a TIG piszkozata. */}
                  <td className="py-2.5 pr-6">
                    <button
                      type="button"
                      disabled={!canEdit || busyId === sor.employee_id}
                      onClick={() => setDijSor(sor)}
                      className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                    >
                      {sor.megbeszelt_dij != null
                        ? `${sor.megbeszelt_dij.toLocaleString("hu-HU")} Ft`
                        : "Nincs megadva"}
                    </button>
                    {sor.dij_megjegyzes && (
                      <p className="mt-1 max-w-[16rem] text-[11.5px] text-text-muted">{sor.dij_megjegyzes}</p>
                    )}
                  </td>
                  <td className="py-2.5">
                    {/* Aki kiadásként van elszámolva, stábtag marad (diszpót
                        kap, rajta van a projekten), csak papír nem kell tőle. */}
                    <label className="flex items-center gap-2 text-[12.5px] text-text-secondary">
                      <input
                        type="checkbox"
                        checked={sor.kiadaskent_elszamolva}
                        disabled={!canEdit || busyId === sor.employee_id}
                        // Bekapcsoláskor előbb a magyarázat kell (hova és miért
                        // került a kiadásba); kikapcsoláskor nincs mit indokolni.
                        onChange={(e) =>
                          e.target.checked ? setKiadasIndokSor(sor) : kiadaskentAllit(sor.employee_id, false)
                        }
                        className="h-3.5 w-3.5 accent-[var(--text-accent)] disabled:opacity-50"
                      />
                      {sor.kiadaskent_elszamolva ? "Kiadásban elszámolva" : "Nem"}
                    </label>
                    {/* A magyarázat ott van a jelölés alatt: enélkül a sor csak
                        annyit mondana, hogy tőle nem kell papír - azt nem, hogy
                        hol keressük a pénzt. */}
                    {sor.kiadaskent_elszamolva && sor.kiadas_megjegyzes && (
                      <p className="mt-1 max-w-[20rem] text-[11.5px] text-text-muted">{sor.kiadas_megjegyzes}</p>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {kiadasIndokSor && (
        <IndoklasDialog
          cim={`${kiadasIndokSor.full_name} a projekt kiadásba kerül`}
          leiras="Tőle nem kérünk sem szerződést, sem TIG-et. Írd le, hova és miért került a költsége - ebből fog kiderülni, hol keressük a pénzt."
          mezoCimke="Hova és miért került"
          placeholder="Pl. a technika bérleti díjában van benne, a Média Kft. számláján"
          gombCimke="Jelölés"
          onMegse={() => setKiadasIndokSor(null)}
          onKesz={(indok) => kiadaskentAllit(kiadasIndokSor.employee_id, true, indok)}
        />
      )}
      {dijSor && (
        <MegbeszeltDijDialog
          nev={dijSor.full_name}
          kezdoDij={dijSor.megbeszelt_dij}
          kezdoMegjegyzes={dijSor.dij_megjegyzes}
          onMegse={() => setDijSor(null)}
          onKesz={(dij, megjegyzes) => dijatAllit(dijSor.employee_id, dij, megjegyzes)}
        />
      )}
    </div>
  );
}
