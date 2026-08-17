"use client";

import { Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { TigAllapotSelect } from "@/components/TigAllapotSelect";
import { KifizetesJeloloDialog } from "@/components/KifizetesJeloloDialog";
import { IndoklasDialog } from "@/components/IndoklasDialog";
import type { PerformanceCertificate } from "@/lib/api";

/** Mely FORGATÁSOKAT fedi ez a papír - a tételeiből, ismétlés nélkül.
 *
 * Egy TIG több projekt munkáját is igazolhatja (több nap egy számlán), és
 * ilyenkor a számla meg a kifizetés is EGYBEN megy az egészre. Ezt ki kell
 * írni: a másik projekt oldalán különben úgy tűnne, mintha az ottani munkához
 * külön számlát kellene kérni - és valaki fel is töltene egy másodikat. */
function fedettProjektek(c: PerformanceCertificate): string[] {
  // PROJEKTENKÉNT egy címke, nem kódonként: több forgatási nap tartozhat
  // ugyanahhoz a projektkódhoz, és pont az a lényeg, hogy látszódjon, HÁNY
  // napot fed a papír. A dátum különbözteti meg őket egymástól.
  const projektenkent = new Map<number, string>();
  for (const t of c.tetelek ?? []) {
    if (projektenkent.has(t.project_id)) continue;
    const nev = t.project_nev ?? t.projektkod ?? `#${t.project_id}`;
    projektenkent.set(t.project_id, t.forgatas_datuma ? `${nev} (${t.forgatas_datuma})` : nev);
  }
  return Array.from(projektenkent.values());
}

/** A TIG SZÁMLÁZÓ FELÉNEK kulcsa ("e12" ember, "v3" cég) - ez megy az
 * útvonalba (lásd backend services/szamlazo.py). Egy TIG nem feltétlenül egy
 * emberről szól: cég nevére is szólhat, és több ember munkáját is igazolhatja. */
function szamlazoKulcs(c: PerformanceCertificate): string {
  return c.vallalkozas_id != null ? `v${c.vallalkozas_id}` : `e${c.employee_id}`;
}

/** A "Kiküldve"/"Kész" állapotú TIG-ekhez (akár Külsős, akár Belsős) tartozó
 * számlák feltöltése, majd kifizetettként jelölése - ez utóbbi hozza létre a
 * Pénzügy -> Kiadások-ban megjelenő Expense sort (lásd backend
 * performance_certificates.py / internal_performance_certificates.py
 * /szamla és /szamla-kifizetve végpontjai). Ugyanaz a komponens szolgálja ki
 * mindkét TIG-fajtát, csak a basePath és a readyStatus különbözik köztük.
 *
 * Egy TIG-hez több számla is tartozhat (pl. részszámlák), és bármelyik
 * külön-külön törölhető - a törlés a kifizetettséget NEM vonja vissza, mert az
 * már pénzügyi tény (lásd backend delete_szamla).
 *
 * Maga a TIG is törölhető innen (amíg nincs kifizetve): ha rossz adattal ment
 * ki, vagy tévesen lett kihagyva, a törlés után az illető visszakerül a
 * teendők közé, és készíthető neki új TIG. Ezért jelennek meg itt a KIHAGYOTT
 * bejegyzések is - különben egy téves kihagyás sehol nem lenne javítható. */
export function TigInvoiceManager({
  projectId,
  basePath,
  certificates,
  employeeNameById,
  readyStatus,
  canEdit = true,
}: {
  projectId: number;
  basePath: string;
  certificates: PerformanceCertificate[];
  employeeNameById: Map<number, string>;
  readyStatus: string;
  /** Az állapot legördülője csak szerkesztési joggal aktív - enélkül sima
   * címkeként jelenik meg (lásd TigAllapotSelect). */
  canEdit?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busyId, setBusyId] = useState<string | null>(null);
  // Melyik TIG-et jelöljük épp kifizetettnek - a "kerüljön-e Kiadás sorba"
  // döntés miatt nem elég egy igen/nem megerősítés.
  const [kifizetendo, setKifizetendo] = useState<{
    szamlazo: string;
    nev: string;
    osszeg: string | null;
    hatarido: string | null;
  } | null>(null);
  // A feltöltés ELŐTT beírt fizetési határidő, számlázó felenként. A számlán
  // ott áll a határidő, tehát abban a pillanatban a kezünkben van, amikor a
  // fájlt kiválasztjuk - így nem kell külön lépésben visszajönni érte. Enélkül
  // nem is indul a feltöltés (a backend is elutasítja).
  const [hataridoInput, setHataridoInput] = useState<Record<string, string>>({});
  // Melyik TIG számla-lépését hagyjuk ki - az indoklás kötelező, ezért ez is
  // ablakot nyit (ugyanaz a minta, mint a szerződés/TIG kihagyásánál).
  const [kihagyando, setKihagyando] = useState<{ szamlazo: string; nev: string } | null>(null);

  const ready = certificates.filter((c) => c.allapot === readyStatus || c.allapot === "Kihagyva");

  /** Egyszerre több kiválasztott fájl is feltölthető - egymás után megy fel,
   * mert minden hívás egy külön számla-sort hoz létre a backenden. */
  async function uploadInvoices(szamlazo: string, hatarido: string, input: HTMLInputElement, files: File[]) {
    setBusyId(szamlazo);
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("fizetesi_hatarido", hatarido);
        const res = await authFetch(`${basePath}/${projectId}/${szamlazo}/szamla`, { method: "POST", body: fd });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          alert(`Sikertelen feltöltés (${file.name}): ${detail?.detail ?? res.status}`);
          break;
        }
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
      input.value = "";
    }
  }

  async function deleteInvoice(szamlazo: string, invoiceId: number, filename: string) {
    if (!(await confirm(`Biztosan törlöd ezt a számlát: "${filename}"?`))) return;
    setBusyId(szamlazo);
    try {
      const res = await authFetch(`${basePath}/${projectId}/${szamlazo}/szamla/${invoiceId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function deleteCertificate(szamlazo: string, nev: string) {
    const ok = await confirm(
      `Törlöd ${nev} teljesítési igazolását erről a projektről? Ezután újra a teendők közt jelenik meg, és készíthetsz neki újat.`,
    );
    if (!ok) return;
    setBusyId(szamlazo);
    try {
      const res = await authFetch(`${basePath}/${projectId}/${szamlazo}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  /** A fizetési határidő utólagos állítása: a fájl gyakran előbb kerül fel,
   * mint ahogy valaki megnézné, mi áll rajta - ilyenkor ne kelljen a számlát
   * újra feltölteni azért, hogy a dátum bekerüljön (lásd backend /hatarido). */
  async function saveHatarido(szamlazo: string, ertek: string) {
    setHataridoInput((elozo) => ({ ...elozo, [szamlazo]: ertek }));
    try {
      const res = await authFetch(`${basePath}/${projectId}/${szamlazo}/hatarido`, {
        method: "POST",
        body: JSON.stringify({ fizetesi_hatarido: ertek || null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        // A helyi értéket eldobjuk, hogy a mező visszaálljon arra, ami a
        // szerveren van - különben az elutasított dátum ottmaradna a képernyőn.
        setHataridoInput(({ [szamlazo]: _eldobott, ...tobbi }) => tobbi);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
      setHataridoInput(({ [szamlazo]: _eldobott, ...tobbi }) => tobbi);
    }
  }

  /** A SZÁMLA-lépés kihagyása (vagy a kihagyás visszavonása): ehhez a
   * papírhoz nem várunk se számlát, se kifizetést - mert máshol számolták el,
   * elengedték, beszámították. Az indok kötelező, ahogy a szerződés és a TIG
   * kihagyásánál is. */
  async function szamlatKihagy(szamlazo: string, kihagyva: boolean, indok?: string) {
    setKihagyando(null);
    setBusyId(szamlazo);
    try {
      const res = await authFetch(`${basePath}/${projectId}/${szamlazo}/szamla-kihagyas`, {
        method: "POST",
        body: JSON.stringify({ kihagyva, indok: indok ?? null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function markPaid(szamlazo: string, kiadasbaKerul: boolean, kifizetesDatuma: string) {
    setKifizetendo(null);
    setBusyId(szamlazo);
    try {
      const res = await authFetch(`${basePath}/${projectId}/${szamlazo}/szamla-kifizetve`, {
        method: "POST",
        body: JSON.stringify({ kiadasba_kerul: kiadasbaKerul, kifizetes_datuma: kifizetesDatuma }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  if (ready.length === 0) return null;

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="mb-2 text-[13px] font-medium text-text-primary">Elkészült TIG-ek és számlák</p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Számlázó fél</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">TIG állapota</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">TIG dokumentum</th>
              <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Bruttó</th>
              <th className="min-w-[240px] py-1.5 pr-6 text-left font-medium text-text-secondary">Számlák</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Fizetési határidő</th>
              <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Státusz</th>
              <th className="py-1.5 text-right font-medium text-text-secondary" />
            </tr>
          </thead>
          <tbody>
            {ready.map((c) => {
              const szamlazo = szamlazoKulcs(c);
              const busy = busyId === szamlazo;
              const invoices = c.invoices ?? [];
              // Cég nevére szóló TIG-nél nincs ember - a cégnév a papíron is
              // szereplő ceg_neve mezőből jön.
              const nev =
                (c.employee_id != null ? employeeNameById.get(c.employee_id) : null) ?? c.ceg_neve ?? szamlazo;
              // Egy TIG több ember munkáját is igazolhatja (lásd tetelek) - ha
              // igen, azt a név mellett ki is írjuk.
              const tovabbiak = (c.tetelek ?? [])
                .filter((t) => t.employee_id !== c.employee_id)
                .map((t) => employeeNameById.get(t.employee_id) ?? `#${t.employee_id}`);
              // Számla csak határidővel tölthető fel: a számlán ott áll, és
              // utólag már senki nem nyitja ki újra a fájlt érte.
              const hatarido = hataridoInput[szamlazo] ?? c.fizetesi_hatarido ?? "";
              // Több forgatás egy papíron: a számla és a kifizetés is EGYBEN
              // megy az egészre, ezért ki kell írni, mit fed.
              const projektek = fedettProjektek(c);
              return (
                <tr key={c.id} className="border-b border-border align-top last:border-0">
                  <td className="py-3 pr-6">
                    {nev}
                    {tovabbiak.length > 0 && (
                      <span className="block text-[11px] text-text-muted">
                        + {Array.from(new Set(tovabbiak)).join(", ")} munkája
                      </span>
                    )}
                    {projektek.length > 1 && (
                      <span className="mt-0.5 block text-[11px] text-text-muted">
                        {projektek.length} forgatás egy számlán: {projektek.join(", ")}
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-6">
                    {/* Kézzel is javítható: egy tévesen kiküldöttre állított TIG
                        visszavehető "Készítés alatt"-ra, és újra elkészíthető. */}
                    <TigAllapotSelect
                      postPath={`${basePath}/${projectId}/${szamlazo}/allapot`}
                      value={c.allapot}
                      canEdit={canEdit}
                    />
                  </td>
                  {/* Az elkészült TIG dokumentuma: a generálás+küldés után ez
                      mutatja meg, mi ment ki - enélkül a kiküldött TIG-hez
                      nem vezetne út a felületről. */}
                  <td className="py-3 pr-6">
                    {c.file_url ? (
                      <a
                        href={c.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        Elkészült TIG
                      </a>
                    ) : (
                      <span className="text-text-muted">–</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap py-3 pr-6 text-right">
                    {c.brutto_osszeg != null ? `${c.brutto_osszeg.toLocaleString("hu-HU")} Ft` : "–"}
                  </td>
                  <td className="py-3 pr-6">
                    {/* Kihagyott számla-lépés: ide nem jön se számla, se
                        kifizetés - csak az indok, és egy út visszafelé. */}
                    {c.szamla_kihagyva ? (
                      <div className="flex flex-col items-start gap-1">
                        <StatusBadge label="Számla kihagyva" tone="neutral" />
                        {c.szamla_kihagyas_oka && (
                          <span className="max-w-[16rem] text-[11.5px] text-text-muted">
                            {c.szamla_kihagyas_oka}
                          </span>
                        )}
                        {canEdit && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => szamlatKihagy(szamlazo, false)}
                            className="text-[12px] text-text-accent hover:underline disabled:opacity-50"
                          >
                            Mégis kérünk számlát
                          </button>
                        )}
                      </div>
                    ) : (
                    <div className="flex flex-col gap-1.5">
                      {invoices.map((inv) => (
                        <div key={inv.id} className="flex items-center gap-2">
                          <a
                            href={inv.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="max-w-[180px] truncate text-text-accent hover:underline"
                            title={inv.filename}
                          >
                            {inv.filename}
                          </a>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => deleteInvoice(szamlazo, inv.id, inv.filename)}
                            className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                            title="Számla törlése"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      ))}
                      {/* Határidő nélkül nincs feltöltés: a fájlválasztó helyén
                          ilyenkor az áll, mi hiányzik - így nem egy hibaüzenet
                          után derül ki, hogy a fájl nem ment fel. */}
                      {hatarido ? (
                        <label className="w-fit cursor-pointer text-[12px] text-text-accent hover:underline">
                          {busy ? "Feltöltés…" : "+ Számla feltöltése"}
                          <input
                            type="file"
                            multiple
                            disabled={busy}
                            onChange={(e) => {
                              const files = Array.from(e.target.files ?? []);
                              if (files.length > 0) uploadInvoices(szamlazo, hatarido, e.target, files);
                            }}
                            className="hidden"
                          />
                        </label>
                      ) : (
                        <span className="w-fit text-[12px] text-text-muted">
                          Számla feltöltése: előbb add meg a fizetési határidőt →
                        </span>
                      )}
                      {/* A számla-lépés kihagyása: van, amikor a papír megvan,
                          de pénz nem megy ki rá (máshol elszámolva,
                          elengedve). Enélkül az ilyen munka örökre "nincs
                          kifizetve" maradna az utókövetésben. Kifizetés után
                          már nincs mit kihagyni. */}
                      {canEdit && !c.szamla_kifizetve && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => setKihagyando({ szamlazo, nev })}
                          className="w-fit text-[12px] text-text-muted hover:text-text-primary disabled:opacity-50"
                        >
                          Számla kihagyása
                        </button>
                      )}
                    </div>
                    )}
                  </td>
                  {/* A számlán szereplő határidő: a feltöltés előtt beírva
                      rögtön a feltöltéssel megy, utólag pedig magában mentődik
                      (lásd saveHatarido). Kifizetés után már csak látszik. */}
                  <td className="py-3 pr-6">
                    {c.szamla_kihagyva ? (
                      // Kihagyott számlánál nincs mit határidőzni.
                      <span className="text-text-muted">–</span>
                    ) : c.szamla_kifizetve ? (
                      <span className="whitespace-nowrap text-text-secondary">{c.fizetesi_hatarido ?? "–"}</span>
                    ) : (
                      <>
                        <input
                          type="date"
                          disabled={busy || !canEdit}
                          value={hatarido}
                          onChange={(e) => saveHatarido(szamlazo, e.target.value)}
                          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12px] text-text-primary disabled:opacity-50"
                        />
                        {!hatarido && (
                          <span className="mt-0.5 block text-[11px] text-text-muted">
                            A számla feltöltéséhez kötelező
                          </span>
                        )}
                      </>
                    )}
                    {c.szamla_kifizetve && c.utalas_datuma && (
                      <span className="mt-0.5 block whitespace-nowrap text-[11px] text-text-muted">
                        Utalva: {c.utalas_datuma}
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-6 text-right">
                    {c.szamla_kihagyva ? (
                      // Nem hiány: szándékosan nincs számla és kifizetés -
                      // az utókövetésben sem marad függőben (lásd backend
                      // utokovetes_admin._kifizetes_state).
                      <StatusBadge label="Kihagyva" tone="neutral" />
                    ) : c.szamla_kifizetve ? (
                      <StatusBadge label="Kifizetve" tone="success" />
                    ) : invoices.length > 0 ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          setKifizetendo({
                            szamlazo,
                            nev,
                            osszeg:
                              c.brutto_osszeg != null ? `${c.brutto_osszeg.toLocaleString("hu-HU")} Ft bruttó` : null,
                            hatarido: hataridoInput[szamlazo] ?? c.fizetesi_hatarido ?? null,
                          })
                        }
                        className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                      >
                        Kifizetve jelölés
                      </button>
                    ) : (
                      <StatusBadge label="Nincs számla" tone="neutral" />
                    )}
                  </td>
                  <td className="py-3 text-right">
                    {/* Amihez KIADÁS SOR tartozik a Pénzügyben, azt a backend
                        nem engedi törölni: előbb ott kell törölni a kiadást
                        (az visszaállítja ezt a TIG-et "nincs kifizetve"-be,
                        lásd services/kiadas_kapcsolatok.py). A Kiadás sor
                        nélküli "kifizetve" jelölés viszont nem akadály. */}
                    {canEdit && c.expense_id == null && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => deleteCertificate(szamlazo, nev)}
                        title="TIG törlése - utána újra elkészíthető"
                        className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                      >
                        <XCircle size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Feltételes renderelés, hogy minden megnyitás friss példány legyen. */}
      {kifizetendo && (
        <KifizetesJeloloDialog
          nev={kifizetendo.nev}
          osszeg={kifizetendo.osszeg}
          hatarido={kifizetendo.hatarido}
          onMegse={() => setKifizetendo(null)}
          onJelol={(kiadasbaKerul, kifizetesDatuma) =>
            markPaid(kifizetendo.szamlazo, kiadasbaKerul, kifizetesDatuma)
          }
        />
      )}
      {kihagyando && (
        <IndoklasDialog
          cim={`Számla kihagyása – ${kihagyando.nev}`}
          leiras="Ehhez a papírhoz nem várunk se számlát, se kifizetést, és az utókövetésben sem marad függőben. Írd le, miért marad el - fél év múlva ebből fog kiderülni, hogy szándékos volt."
          mezoCimke="Miért marad el"
          placeholder="Pl. a technika bérleti díjában rendeztük"
          gombCimke="Kihagyás"
          onMegse={() => setKihagyando(null)}
          onKesz={(indok) => szamlatKihagy(kihagyando.szamlazo, true, indok)}
        />
      )}
    </div>
  );
}
