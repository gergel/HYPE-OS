"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";
import { IdoszakReszletekModal } from "@/components/krumpello/IdoszakReszletekModal";
import { authFetch } from "@/lib/authFetch";
import { formatFt } from "@/lib/ido";
import { KRUMPELLO_BEJELENTESEK } from "@/lib/krumpello";
import type { KrumpelloDolgozo, KrumpelloIdoszak } from "@/lib/api";

const UT = "/api/v1/krumpello/idoszakok";

type Urlap = {
  dolgozo_id: string;
  kezdet: string;
  veg: string;
  bejelentes: string;
  napi_ber: string;
  nev: string;
  megjegyzes: string;
};

const URES: Urlap = {
  dolgozo_id: "",
  kezdet: "",
  veg: "",
  bejelentes: "efo",
  napi_ber: "",
  nev: "",
  megjegyzes: "",
};

function idoszakSzoveg(i: KrumpelloIdoszak): string {
  return `${i.kezdet} – ${i.veg ?? "azóta is tart"}`;
}

/** Foglalkoztatási időszakok: mettől meddig, milyen bejelentéssel, mennyi a
 * bejelentett napi bér - és az elszámolásuk.
 *
 * Ez a nézet válaszol arra a két kérdésre, ami a kifizetéskor számít:
 * **mennyit kell utalni** (a bejelentett napi bérek összege) és **mennyit kell
 * készpénzben odaadni** (a fölötte lévő rész). Naponta kattintgatva ugyanez
 * kézzel összeadogatás lenne, épp a legfáradtabb pillanatban.
 *
 * Több időszak egyszerre is elszámolható: ha valakinél egy EFO-s és egy
 * szerződéses szakasz is nyitva maradt, egyszerre rendezik őket - és egy
 * összeget adnak oda, nem kettőt. */
export function IdoszakKezelo({
  dolgozok,
  idoszakok,
  canEdit,
}: {
  dolgozok: KrumpelloDolgozo[];
  idoszakok: KrumpelloIdoszak[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const [nyitva, setNyitva] = useState(false);
  const [szerkesztett, setSzerkesztett] = useState<KrumpelloIdoszak | null>(null);
  const [urlap, setUrlap] = useState<Urlap>(URES);
  const [busy, setBusy] = useState(false);
  const [kijelolt, setKijelolt] = useState<Set<number>>(new Set());
  const [reszletek, setReszletek] = useState<number | null>(null);

  function frissit<K extends keyof Urlap>(kulcs: K, ertek: Urlap[K]) {
    setUrlap((e) => ({ ...e, [kulcs]: ertek }));
  }

  function ujat() {
    setSzerkesztett(null);
    setUrlap({ ...URES, dolgozo_id: dolgozok[0] ? String(dolgozok[0].id) : "" });
    setNyitva(true);
  }

  function szerkeszt(i: KrumpelloIdoszak) {
    setSzerkesztett(i);
    setUrlap({
      dolgozo_id: String(i.dolgozo_id),
      kezdet: i.kezdet,
      veg: i.veg ?? "",
      bejelentes: i.bejelentes,
      napi_ber: i.napi_ber != null ? String(i.napi_ber) : "",
      nev: i.nev ?? "",
      megjegyzes: i.megjegyzes ?? "",
    });
    setNyitva(true);
  }

  async function ment() {
    if (!urlap.dolgozo_id || !urlap.kezdet) {
      toast("A dolgozó és a kezdő dátum kötelező.");
      return;
    }
    setBusy(true);
    try {
      const torzs = {
        ...(szerkesztett ? {} : { dolgozo_id: Number(urlap.dolgozo_id) }),
        kezdet: urlap.kezdet,
        veg: urlap.veg || null,
        bejelentes: urlap.bejelentes,
        napi_ber: urlap.napi_ber ? Number(urlap.napi_ber) : null,
        nev: urlap.nev || null,
        megjegyzes: urlap.megjegyzes || null,
      };
      const res = await authFetch(szerkesztett ? `${UT}/${szerkesztett.id}` : UT, {
        method: szerkesztett ? "PATCH" : "POST",
        body: JSON.stringify(torzs),
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen mentés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      setNyitva(false);
      router.refresh();
    } catch (err) {
      toast(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function torol(i: KrumpelloIdoszak) {
    if (
      !(await confirm(
        `Törlöd a(z) "${i.dolgozo_nev} – ${idoszakSzoveg(i)}" időszakot? A ledolgozott napok megmaradnak, csak a bejelentés esik le róluk.`,
      ))
    )
      return;
    setBusy(true);
    try {
      const res = await authFetch(`${UT}/${i.id}`, { method: "DELETE" });
      if (!res.ok) {
        toast(`Sikertelen törlés: ${res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  function kijelolesValt(id: number) {
    setKijelolt((elozo) => {
      const uj = new Set(elozo);
      if (uj.has(id)) uj.delete(id);
      else uj.add(id);
      return uj;
    });
  }

  const kijeloltek = idoszakok.filter((i) => kijelolt.has(i.id));
  const kijeloltHatralek = kijeloltek.reduce((s, i) => s + i.hatralek, 0);

  /** A kijelölt időszakok elszámolása EGYBEN - ez a művelet lényege. */
  async function elszamol() {
    const utalando = kijeloltek.reduce((s, i) => s + i.utalando, 0);
    const keszpenz = kijeloltek.reduce((s, i) => s + i.keszpenz, 0);
    if (
      !(await confirm(
        `${kijeloltek.length} időszak elszámolása kifizetettként. Utalás: ${formatFt(utalando)}, készpénz: ${formatFt(keszpenz)}. Folytatod?`,
      ))
    )
      return;
    setBusy(true);
    try {
      const res = await authFetch(`${UT}/elszamolas`, {
        method: "POST",
        body: JSON.stringify({ idoszak_idk: [...kijelolt], kifizetve: true }),
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen elszámolás: ${reszlet?.detail ?? res.status}`);
        return;
      }
      const e = await res.json();
      toast(
        e.erintett_napok
          ? `${e.erintett_napok} nap elszámolva. Utalni: ${formatFt(e.utalando)}, készpénzben: ${formatFt(e.keszpenz)}.`
          : "Ezekben az időszakokban már minden nap ki volt fizetve.",
      );
      setKijelolt(new Set());
      router.refresh();
    } catch (err) {
      toast(`Sikertelen elszámolás (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3 text-[13px]">
      <div className="flex flex-wrap items-center gap-3">
        {canEdit && (
          <button
            type="button"
            onClick={ujat}
            disabled={busy || dolgozok.length === 0}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            + Új időszak
          </button>
        )}
        {canEdit && kijelolt.size > 0 && (
          <button
            type="button"
            onClick={elszamol}
            disabled={busy}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-primary hover:bg-surface-3 disabled:opacity-50"
          >
            {kijelolt.size} időszak elszámolása ({formatFt(kijeloltHatralek)})
          </button>
        )}
      </div>

      {idoszakok.length === 0 ? (
        <p className="text-text-muted">
          Még nincs foglalkoztatási időszak. Enélkül minden nap „nem volt bejelentve”, tehát a teljes bér
          készpénzben megy.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-text-muted">
                {canEdit && <th className="w-8 py-2" />}
                <th className="py-2 pr-3 font-medium">Dolgozó</th>
                <th className="py-2 pr-3 font-medium">Időszak</th>
                <th className="py-2 pr-3 font-medium">Bejelentés</th>
                <th className="py-2 pr-3 text-right font-medium">Napi bér</th>
                <th className="py-2 pr-3 text-right font-medium">Nap</th>
                <th className="py-2 pr-3 text-right font-medium">Járandóság</th>
                <th className="py-2 pr-3 text-right font-medium">Utalás</th>
                <th className="py-2 pr-3 text-right font-medium">Készpénz</th>
                <th className="py-2 pr-3 text-right font-medium">Még jár</th>
                <th className="py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {idoszakok.map((i) => (
                <tr key={i.id} className="border-b border-border last:border-0">
                  {canEdit && (
                    <td className="py-2">
                      <input
                        type="checkbox"
                        checked={kijelolt.has(i.id)}
                        onChange={() => kijelolesValt(i.id)}
                        disabled={busy || i.napok_szama === 0}
                        title={i.napok_szama === 0 ? "Ebben az időszakban nincs ledolgozott nap" : "Kijelölés elszámolásra"}
                      />
                    </td>
                  )}
                  <td className="py-2 pr-3 text-text-primary">{i.dolgozo_nev}</td>
                  <td className="py-2 pr-3">
                    <button
                      type="button"
                      onClick={() => setReszletek(i.id)}
                      className="text-left text-text-accent hover:underline"
                    >
                      {idoszakSzoveg(i)}
                    </button>
                    {i.nev && <span className="block text-[11.5px] text-text-muted">{i.nev}</span>}
                  </td>
                  <td className="py-2 pr-3 text-text-secondary">{i.bejelentes_cimke}</td>
                  <td className="py-2 pr-3 text-right text-text-secondary">
                    {i.napi_ber ? formatFt(i.napi_ber) : "–"}
                  </td>
                  <td className="py-2 pr-3 text-right text-text-secondary">{i.napok_szama}</td>
                  <td className="py-2 pr-3 text-right text-text-primary">{formatFt(i.jarandosag)}</td>
                  <td className="py-2 pr-3 text-right text-text-secondary">{formatFt(i.utalando)}</td>
                  <td className="py-2 pr-3 text-right text-text-secondary">{formatFt(i.keszpenz)}</td>
                  <td
                    className={`py-2 pr-3 text-right ${i.hatralek > 0 ? "text-text-primary" : "text-text-muted"}`}
                  >
                    {i.teljesen_kifizetve ? "Fizetve" : formatFt(i.hatralek)}
                  </td>
                  <td className="whitespace-nowrap py-2 text-right">
                    {canEdit && (
                      <>
                        <button
                          type="button"
                          onClick={() => szerkeszt(i)}
                          disabled={busy}
                          className="text-text-secondary hover:underline disabled:opacity-50"
                        >
                          Szerkesztés
                        </button>
                        <button
                          type="button"
                          onClick={() => torol(i)}
                          disabled={busy}
                          className="ml-3 text-text-danger hover:underline disabled:opacity-50"
                        >
                          Törlés
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {reszletek !== null && (
        <IdoszakReszletekModal idoszakId={reszletek} onClose={() => setReszletek(null)} />
      )}

      {nyitva && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busy ? undefined : () => setNyitva(false)}>
          <div
            className="w-full max-w-lg rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">
              {szerkesztett ? "Időszak szerkesztése" : "Új foglalkoztatási időszak"}
            </h3>
            <p className="mb-4 text-[12px] text-text-muted">
              A bejelentett napi bér utalással megy, a fölötte lévő rész készpénzben. Az időszakba eső napok
              ezt öröklik – naponta felül lehet írni.
            </p>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Mezo label="Dolgozó *">
                <select
                  value={urlap.dolgozo_id}
                  onChange={(e) => frissit("dolgozo_id", e.target.value)}
                  disabled={busy || szerkesztett !== null}
                  className={mezoOsztaly}
                >
                  {dolgozok.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.nev}
                    </option>
                  ))}
                </select>
              </Mezo>
              <Mezo label="Megnevezés (nem kötelező)">
                <input value={urlap.nev} onChange={(e) => frissit("nev", e.target.value)} disabled={busy} placeholder="Pl. Nyári szezon" className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Kezdet *">
                <input type="date" value={urlap.kezdet} onChange={(e) => frissit("kezdet", e.target.value)} disabled={busy} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Vég (üresen: azóta is tart)">
                <input type="date" value={urlap.veg} onChange={(e) => frissit("veg", e.target.value)} disabled={busy} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Bejelentés">
                <select
                  value={urlap.bejelentes}
                  onChange={(e) => frissit("bejelentes", e.target.value)}
                  disabled={busy}
                  className={mezoOsztaly}
                >
                  {KRUMPELLO_BEJELENTESEK.map((b) => (
                    <option key={b.ertek} value={b.ertek}>
                      {b.cimke}
                    </option>
                  ))}
                </select>
              </Mezo>
              <Mezo label="Bejelentett napi bér (utalással)">
                <input
                  type="number"
                  value={urlap.napi_ber}
                  onChange={(e) => frissit("napi_ber", e.target.value)}
                  disabled={busy || urlap.bejelentes === "nincs"}
                  placeholder={urlap.bejelentes === "nincs" ? "Bejelentés nélkül nincs utalás" : ""}
                  className={mezoOsztaly}
                />
              </Mezo>
            </div>
            <div className="mt-3">
              <Mezo label="Megjegyzés">
                <input value={urlap.megjegyzes} onChange={(e) => frissit("megjegyzes", e.target.value)} disabled={busy} className={mezoOsztaly} />
              </Mezo>
            </div>

            <div className="mt-5 flex justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={() => setNyitva(false)}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={ment}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Mentés…" : "Mentés"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const mezoOsztaly =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

function Mezo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] text-text-muted">{label}</label>
      {children}
    </div>
  );
}
