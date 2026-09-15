"use client";

/** UTALÁSOK FELVEZETÉSE - egy már elutalt számlacsomag adminisztrálása.
 *
 * A folyamat (a felhasználó előírása szerint):
 *   1. ZIP feltöltése + KÖTELEZŐ tényleges utalási dátum → háttér-felismerés.
 *   2. BESOROLÁS: melyik számla Krumpellóé, melyik HYPE-é - minden besorolást
 *      ember erősít meg (tömeges műveletekkel).
 *   3. HELYKERESÉS a HYPE-számláknak: a rendszer javasol, kézi kereső és
 *      előre kitöltött új-kiadás tervezet segít.
 *   4. JÓVÁHAGYÁS (1. emberi lépés): elfogadom, hová tartozik a számla.
 *   5. RÖGZÍTÉS (2. lépés): csak a jóváhagyott műveletek hajtódnak végre.
 *
 * Banki utalást NEM indít. A Krumpellóhoz sorolt tétel itt lezárt
 * ("máshol kézzel kezelendő"), HYPE-rekordot nem érint. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, RefreshCw, Upload } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { formatSzam } from "@/lib/penz";
import { huDatum } from "@/lib/huDate";
import { KeresosSelect } from "@/components/KeresosSelect";
import { StatusBadge } from "@/components/StatusBadge";
import type { UtalasAdag, UtalasAdagReszlet, UtalasTetel } from "@/lib/api";

type Valasztek = {
  projektkodok: { id: number; kod: string; nev: string | null }[];
  emberek: { id: number; nev: string }[];
};

const ALLAPOT_TONE: Record<string, "success" | "warning" | "danger" | "neutral" | "accent" | "blue" | "teal" | "orange"> = {
  rogzitheto: "orange",
  jovahagyva: "success",
  valasztas: "warning",
  nincs_talalat: "warning",
  mar_kifizetve: "blue",
  mar_rogzitve: "blue",
  osszeg_elter: "danger",
  duplikatum: "neutral",
  nem_feldolgozhato: "danger",
  rogzitve: "teal",
  krumpello: "teal",
  feldolgozas: "neutral",
};

//: Ezekkel az állapotokkal a tétel ebben az adagban LEZÁRT.
const LEZART = new Set(["rogzitve", "mar_kifizetve", "mar_rogzitve", "krumpello", "duplikatum"]);

const ELSZAMOLAS_CIMKE: Record<string, string> = { hype: "HYPE", krumpello: "Krumpelló", tisztazando: "Tisztázandó" };

function bruttoSzoveg(t: UtalasTetel): string {
  if (t.brutto != null) return `${formatSzam(t.brutto)} ${t.penznem}`;
  if (t.netto != null) return `${formatSzam(t.netto)} ${t.penznem} (nettó)`;
  return "–";
}

/** Az "Ez fog történni / Ez történt" emberi összefoglalója egy tételhez. */
function ezTortenik(t: UtalasTetel): string {
  const datum = t.ervenyes_datum ? huDatum(t.ervenyes_datum) : "?";
  if (t.allapot === "krumpello")
    return "Krumpellóhoz sorolva - ebben az adagban lezárt, máshol kézzel kezelendő. HYPE-kiadást nem hoz létre és nem módosít; a fájl és a besorolás visszakereshető marad.";
  if (t.elszamolas === "krumpello")
    return "Krumpellóhoz sorolva - a megerősítés után ebben az adagban lezárt lesz (máshol kézzel kezelendő), HYPE-rekordot nem érint.";
  if (t.allapot === "rogzitve") {
    const n = (t.rogzites_naplo || {}) as { mar_igy_volt?: boolean };
    return `Felvezetve: a tétel ${datum} nappal kifizetettként rögzült${n.mar_igy_volt ? " (már eleve így volt, nem módosítottunk)" : ""}. A célrekord a linkre kattintva nyitható.`;
  }
  if (t.allapot === "mar_rogzitve") return t.hiba_uzenet || "Ez a számla egy korábbi adagban már felvezetésre került - itt nincs teendő.";
  if (t.allapot === "mar_kifizetve")
    return `A kiválasztott cél már kifizetett${t.cel_fizetesi_allapot?.datum ? ` (${huDatum(t.cel_fizetesi_allapot.datum)})` : ""} - ide nem vezetünk fel újabb kifizetést, és a korábbi adatot nem írjuk felül. Ha csak a dokumentum hiányzik a célról, azt külön műveletként a Beérkező számlák felől csatold.`;
  if (t.allapot === "duplikatum") return t.hiba_uzenet || "Ugyanez a számla már szerepel - nem vezetjük fel kétszer.";
  if (t.allapot === "nem_feldolgozhato") return t.hiba_uzenet || "Ez a fájl nem dolgozható fel.";
  if (t.allapot === "osszeg_elter")
    return "A számla összege eltér a megtalált tétel összegétől - részfizetés/eltérés csak kifejezett elfogadással hagyható jóvá (lent pipálható).";
  const elotag = t.allapot === "jovahagyva" ? "JÓVÁHAGYVA - rögzítéskor: " : "";
  if (t.cel_tipus === "uj_kiadas") {
    const adatok = t.uj_kiadas || {};
    const hova = adatok.mukodesi ? "MŰKÖDÉSI kiadásként (tudatosan projekt nélkül)" : "a kiválasztott projektkódra";
    return `${elotag}ÚJ kiadás jön létre ${hova} (${t.kibocsato_nev || "?"}), a számla csatolásával, és ${datum} nappal kifizetettként rögzül.`;
  }
  if (t.cel_tipus && t.cel_cimke)
    return `${elotag}Ezt a számlát a(z) „${t.cel_cimke}” tételhez kapcsoljuk, és ${datum} nappal teljesen kifizetettnek jelöljük.`;
  return "Válaszd ki, melyik meglévő tételhez tartozik - vagy készíts belőle új kiadást (lent kereső és tervezet segít).";
}

export function UtalasokFelvezetese({
  kezdoAdagok,
  valasztek,
  canEdit,
  canCreate,
  canDelete,
}: {
  kezdoAdagok: UtalasAdag[];
  valasztek: Valasztek;
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const [adagok, setAdagok] = useState(kezdoAdagok);
  const [nyitott, setNyitott] = useState<UtalasAdagReszlet | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const adagFrissit = useCallback(async () => {
    try {
      const r = await authFetch("/api/v1/utalasok");
      if (r.ok) setAdagok(await r.json());
    } catch {
      /* lentebb router.refresh is fut */
    }
    router.refresh();
  }, [router]);

  const megnyit = useCallback(async (id: number) => {
    try {
      const r = await authFetch(`/api/v1/utalasok/${id}`);
      if (!r.ok) {
        setHiba(`Az adag nem tölthető be (${r.status}).`);
        return;
      }
      const adat: UtalasAdagReszlet = await r.json();
      setNyitott(adat);
      // Amíg a háttér-feldolgozás fut, 3 mp-enként frissülünk.
      if (pollRef.current) clearTimeout(pollRef.current);
      if (adat.allapot === "feldolgozas") {
        pollRef.current = setTimeout(() => void megnyit(id), 3000);
      }
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    }
  }, []);

  useEffect(() => () => {
    if (pollRef.current) clearTimeout(pollRef.current);
  }, []);

  return (
    <div className="space-y-4">
      {canCreate && <UjAdagUrlap onKesz={(id) => { void adagFrissit(); void megnyit(id); }} />}
      {hiba && <p className="text-[12.5px] text-text-danger">{hiba}</p>}

      {nyitott ? (
        <AdagReszletes
          adag={nyitott}
          valasztek={valasztek}
          canEdit={canEdit}
          canCreate={canCreate}
          canDelete={canDelete}
          onFrissit={() => void megnyit(nyitott.id)}
          onBezar={() => {
            setNyitott(null);
            if (pollRef.current) clearTimeout(pollRef.current);
            void adagFrissit();
          }}
        />
      ) : (
        <AdagLista adagok={adagok} canDelete={canDelete} onMegnyit={(id) => void megnyit(id)} onFrissit={() => void adagFrissit()} />
      )}
    </div>
  );
}

/** Új adag: ZIP + KÖTELEZŐ tényleges utalási dátum (nincs "mai nap"
 * alapérték, és nem következtetjük ki a számla dátumaiból sem). */
function UjAdagUrlap({ onKesz }: { onKesz: (adagId: number) => void }) {
  const [fajl, setFajl] = useState<File | null>(null);
  const [datum, setDatum] = useState("");
  const [nev, setNev] = useState("");
  const [megjegyzes, setMegjegyzes] = useState("");
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const fajlRef = useRef<HTMLInputElement | null>(null);

  async function kuldes() {
    if (!fajl) {
      setUzenet("Válaszd ki a ZIP-fájlt.");
      return;
    }
    if (!datum) {
      setUzenet("Add meg az utalás dátumát - ez a TÉNYLEGES banki utalás napja (kötelező, nincs alapérték).");
      return;
    }
    setBusy(true);
    setUzenet(null);
    try {
      const fd = new FormData();
      fd.append("fajl", fajl);
      fd.append("utalas_datum", datum);
      if (nev.trim()) fd.append("nev", nev.trim());
      if (megjegyzes.trim()) fd.append("megjegyzes", megjegyzes.trim());
      const r = await authFetch("/api/v1/utalasok", { method: "POST", body: fd });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setUzenet(`Sikertelen: ${d?.detail ?? r.status}`);
        return;
      }
      setUzenet(null);
      setFajl(null);
      setDatum("");
      setNev("");
      setMegjegyzes("");
      if (fajlRef.current) fajlRef.current.value = "";
      onKesz(d.id);
    } catch (err) {
      setUzenet(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
      <p className="mb-2 text-[12.5px] text-text-secondary">
        <b className="text-text-primary">Új adag:</b> egy ZIP = egy utalási adag. A feltöltéstől még semmi nem
        válik fizetetté: előbb besorolsz (HYPE / Krumpelló), aztán jóváhagyod a célokat, és csak a rögzítés
        hajt végre bármit.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-[12px] text-text-secondary">
          ZIP a számlákkal
          <input
            ref={fajlRef}
            type="file"
            accept=".zip,application/zip,application/x-zip-compressed"
            onChange={(e) => setFajl(e.target.files?.[0] ?? null)}
            className="text-[12.5px] text-text-primary file:mr-2 file:rounded-[var(--radius)] file:border file:border-border file:bg-surface-2 file:px-2.5 file:py-1 file:text-[12px] file:text-text-secondary"
          />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-text-secondary">
          Utalás dátuma (kötelező)
          <input
            type="date"
            value={datum}
            onChange={(e) => setDatum(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[12.5px] text-text-primary"
          />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-text-secondary">
          Adag neve (nem kötelező)
          <input
            value={nev}
            onChange={(e) => setNev(e.target.value)}
            placeholder="pl. Szeptember eleji utalások"
            className="w-[220px] rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[12.5px] text-text-primary"
          />
        </label>
        <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-[12px] text-text-secondary">
          Megjegyzés
          <input
            value={megjegyzes}
            onChange={(e) => setMegjegyzes(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[12.5px] text-text-primary"
          />
        </label>
        <button
          type="button"
          disabled={busy}
          onClick={() => void kuldes()}
          className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[12.5px] text-text-accent hover:opacity-90 disabled:opacity-50"
        >
          <Upload size={13} className={busy ? "animate-pulse" : ""} />
          {busy ? "Feltöltés…" : "Előkészítés indítása"}
        </button>
      </div>
      {uzenet && <p className="mt-1.5 text-[12px] text-text-danger">{uzenet}</p>}
    </div>
  );
}

function AdagLista({
  adagok,
  canDelete,
  onMegnyit,
  onFrissit,
}: {
  adagok: UtalasAdag[];
  canDelete: boolean;
  onMegnyit: (id: number) => void;
  onFrissit: () => void;
}) {
  const [busy, setBusy] = useState(false);
  if (adagok.length === 0)
    return <p className="py-6 text-center text-[13px] text-text-muted">Még nincs adag - tölts fel egy ZIP-et az elutalt számlákkal.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-[13px]">
        <thead>
          <tr className="border-b border-border text-left text-[11.5px] uppercase tracking-wide text-text-muted">
            <th className="py-2 pr-3">Adag</th>
            <th className="py-2 pr-3">Utalás dátuma</th>
            <th className="py-2 pr-3">Számlák</th>
            <th className="py-2 pr-3">Lezárva</th>
            <th className="py-2 pr-3">Állapot</th>
            <th className="py-2 text-right">Művelet</th>
          </tr>
        </thead>
        <tbody>
          {adagok.map((a) => (
            <tr key={a.id} className="border-b border-border/60">
              <td className="py-2 pr-3">
                <span className="font-medium text-text-primary">{a.nev || a.zip_fajl_nev || `Adag #${a.id}`}</span>
                <span className="ml-2 text-[11.5px] text-text-muted">{huDatum(a.created_at.slice(0, 10))}</span>
              </td>
              <td className="py-2 pr-3 text-text-secondary">{huDatum(a.utalas_datum)}</td>
              <td className="py-2 pr-3 text-text-secondary">{a.tetel_darab}</td>
              <td className="py-2 pr-3 text-text-secondary">
                {a.lezart_darab}/{a.tetel_darab}
              </td>
              <td className="py-2 pr-3">
                <StatusBadge
                  label={
                    a.allapot === "feldolgozas"
                      ? "Feldolgozás alatt"
                      : a.allapot === "hiba"
                        ? "Hiba"
                        : a.lezart
                          ? "Minden tétel lezárva"
                          : "Ellenőrizhető"
                  }
                  tone={a.allapot === "hiba" ? "danger" : a.allapot === "feldolgozas" ? "neutral" : a.lezart ? "success" : "warning"}
                />
              </td>
              <td className="py-2 text-right">
                <span className="inline-flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => onMegnyit(a.id)}
                    className="rounded-[var(--radius)] border border-border bg-bg-accent px-2.5 py-1 text-[12px] text-text-accent hover:opacity-90"
                  >
                    Megnyitás
                  </button>
                  {canDelete && a.rogzitett_darab === 0 && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={async () => {
                        if (!confirm("Törlöd ezt az adagot? A tételei és a tárolt fájljai végleg törlődnek.")) return;
                        setBusy(true);
                        try {
                          const r = await authFetch(`/api/v1/utalasok/${a.id}`, { method: "DELETE" });
                          if (!r.ok) {
                            const d = await r.json().catch(() => null);
                            alert(d?.detail ?? `Sikertelen törlés (${r.status})`);
                          }
                          onFrissit();
                        } finally {
                          setBusy(false);
                        }
                      }}
                      className="rounded-[var(--radius)] border border-text-danger/40 px-2.5 py-1 text-[12px] text-text-danger hover:bg-text-danger/10 disabled:opacity-50"
                    >
                      Törlés
                    </button>
                  )}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Az adag ellenőrző nézete: besorolás → jóváhagyás → rögzítés. */
function AdagReszletes({
  adag,
  valasztek,
  canEdit,
  canCreate,
  canDelete,
  onFrissit,
  onBezar,
}: {
  adag: UtalasAdagReszlet;
  valasztek: Valasztek;
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
  onFrissit: () => void;
  onBezar: () => void;
}) {
  const [kijelolt, setKijelolt] = useState<Set<number>>(new Set());
  const [nyitottTetel, setNyitottTetel] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);

  const tetelek = adag.tetelek;
  const feldolgozott = tetelek.filter((t) => t.allapot !== "feldolgozas").length;
  const krumplisok = tetelek.filter((t) => t.allapot === "krumpello" || (t.elszamolas === "krumpello" && !LEZART.has(t.allapot)));
  const kijeloltNyitott = tetelek.filter((t) => kijelolt.has(t.id) && !LEZART.has(t.allapot));
  const jovahagyhato = kijeloltNyitott.filter((t) => ["rogzitheto", "valasztas", "nincs_talalat", "osszeg_elter"].includes(t.allapot));
  const rogzithetoKijelolt = tetelek.filter((t) => kijelolt.has(t.id) && t.allapot === "jovahagyva");
  const rogzitettKijelolt = tetelek.filter((t) => kijelolt.has(t.id) && t.allapot === "rogzitve");
  const nemMegerositett = tetelek.filter((t) => !t.elszamolas_megerositve && !LEZART.has(t.allapot) && t.allapot !== "feldolgozas");

  const darab = (allapot: string) => tetelek.filter((t) => t.allapot === allapot).length;
  const lezartDarab = tetelek.filter((t) => LEZART.has(t.allapot)).length;
  // Az összegek PÉNZNEMENKÉNT külön - különböző pénznemeket nem adunk össze.
  const penznemOsszegek: Record<string, number> = {};
  for (const t of tetelek) {
    if (t.brutto != null) penznemOsszegek[t.penznem] = (penznemOsszegek[t.penznem] || 0) + t.brutto;
  }

  async function muvelet(utvonal: string, torzs: unknown, siker?: (d: { sikeres?: number; sikertelen?: number; modositott?: number; eredmenyek?: { tetel_id: number; siker: boolean; hiba?: string }[] }) => string) {
    setBusy(true);
    setUzenet(null);
    try {
      const r = await authFetch(utvonal, { method: "POST", body: JSON.stringify(torzs) });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setUzenet(`Sikertelen: ${d?.detail ?? r.status}`);
      } else if (siker) {
        setUzenet(siker(d));
      }
      onFrissit();
    } catch (err) {
      setUzenet(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  function eredmenySzoveg(cim: string) {
    return (d: { sikeres?: number; sikertelen?: number; eredmenyek?: { tetel_id: number; siker: boolean; hiba?: string }[] }) => {
      const hibak = (d.eredmenyek || []).filter((e) => !e.siker);
      return (
        `${cim}: ${d.sikeres ?? 0} sikeres` +
        (d.sikertelen ? `, ${d.sikertelen} nem ment át: ${hibak.map((h) => `#${h.tetel_id}: ${h.hiba}`).join(" · ")}` : ".")
      );
    };
  }

  async function rogzites() {
    if (rogzithetoKijelolt.length === 0) return;
    if (
      !confirm(
        `${rogzithetoKijelolt.length} JÓVÁHAGYOTT tétel kifizetését rögzítjük a megadott utalási dátumokkal. ` +
          "A művelet a meglévő tételeket kifizetettre állítja, és ahol kell, csatolja a számlát. Folytatod?",
      )
    )
      return;
    await muvelet(`/api/v1/utalasok/${adag.id}/rogzites`, { tetel_idk: rogzithetoKijelolt.map((t) => t.id) }, eredmenySzoveg("Rögzítés"));
    setKijelolt(new Set());
  }

  async function visszavonas() {
    if (rogzitettKijelolt.length === 0) return;
    if (
      !confirm(
        `${rogzitettKijelolt.length} felvezetés visszavonása: a rendszerbeli adminisztrációt állítjuk vissza (a banki utalást nem érinti), ` +
          "és csak azt, amit ez a felvezetés írt. Folytatod?",
      )
    )
      return;
    await muvelet(`/api/v1/utalasok/${adag.id}/visszavonas`, { tetel_idk: rogzitettKijelolt.map((t) => t.id) }, eredmenySzoveg("Visszavonás"));
    setKijelolt(new Set());
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onBezar}
          className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3"
        >
          ← Adagok
        </button>
        <h3 className="text-[14px] font-semibold text-text-primary">
          {adag.nev || adag.zip_fajl_nev || `Adag #${adag.id}`}
        </h3>
        <StatusBadge label={`Utalás dátuma: ${huDatum(adag.utalas_datum)}`} tone="accent" />
        {adag.allapot === "feldolgozas" && (
          <span className="flex items-center gap-1 text-[12.5px] text-text-secondary">
            <RefreshCw size={12} className="animate-spin" /> Feldolgozás: {feldolgozott}/{tetelek.length} fájl kész - a
            lista magától frissül
          </span>
        )}
        {adag.allapot !== "feldolgozas" && lezartDarab === tetelek.length && tetelek.length > 0 && (
          <StatusBadge label="Minden tétel lezárva" tone="success" />
        )}
        <button
          type="button"
          onClick={onFrissit}
          className="ml-auto rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3"
        >
          Frissítés
        </button>
      </div>
      {adag.megjegyzes && <p className="text-[12.5px] text-text-secondary">{adag.megjegyzes}</p>}
      {adag.hiba_uzenet && <p className="text-[12.5px] text-text-danger">{adag.hiba_uzenet}</p>}
      {(adag.kihagyott_fajlok?.length ?? 0) > 0 && (
        <details className="text-[12px] text-text-muted">
          <summary className="cursor-pointer">Kihagyott fájlok ({adag.kihagyott_fajlok!.length})</summary>
          <ul className="mt-1 list-inside list-disc">
            {adag.kihagyott_fajlok!.map((k, i) => (
              <li key={i}>
                {k.nev} – {k.ok}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Összegzés - a számlálók UGYANAZOKBÓL a szabályokból, mint a gombok */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[12.5px] text-text-secondary">
        <span><b className="text-text-primary">{lezartDarab}/{tetelek.length}</b> lezárva</span>
        <span><b className="text-text-warning">{darab("rogzitheto")}</b> jóváhagyásra vár</span>
        <span><b className="text-text-success">{darab("jovahagyva")}</b> rögzíthető</span>
        <span>
          <b className="text-text-primary">
            {darab("valasztas") + darab("nincs_talalat") + darab("osszeg_elter") + darab("nem_feldolgozhato")}
          </b>{" "}
          tisztázandó
        </span>
        {nemMegerositett.length > 0 && (
          <span><b className="text-text-warning">{nemMegerositett.length}</b> besorolás megerősítésre vár</span>
        )}
        <span className="ml-auto">
          {Object.entries(penznemOsszegek).map(([p, o]) => (
            <span key={p} className="ml-3 font-medium text-text-primary">
              {formatSzam(o)} {p}
            </span>
          ))}
        </span>
      </div>

      {uzenet && <p className="text-[12.5px] text-text-secondary">{uzenet}</p>}

      {/* Ellenőrző táblázat */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1080px] text-[12.5px]">
          <thead>
            <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-text-muted">
              <th className="py-2 pr-2">
                <input
                  type="checkbox"
                  checked={kijelolt.size > 0 && kijelolt.size === tetelek.length}
                  onChange={(e) => setKijelolt(e.target.checked ? new Set(tetelek.map((t) => t.id)) : new Set())}
                />
              </th>
              <th className="py-2 pr-3">Fájl / számlaszám</th>
              <th className="py-2 pr-3">Kibocsátó</th>
              <th className="py-2 pr-3 text-right">Bruttó</th>
              <th className="py-2 pr-3">Elszámolás</th>
              <th className="py-2 pr-3">Cél</th>
              <th className="py-2 pr-3">Cél fiz. állapota</th>
              <th className="py-2 pr-3">Utalás dátuma</th>
              <th className="py-2 pr-3">Állapot</th>
            </tr>
          </thead>
          <tbody>
            {tetelek.map((t) => (
              <TetelSor
                key={t.id}
                t={t}
                adag={adag}
                kijelolve={kijelolt.has(t.id)}
                onKijelol={(be) =>
                  setKijelolt((elozo) => {
                    const uj = new Set(elozo);
                    if (be) uj.add(t.id);
                    else uj.delete(t.id);
                    return uj;
                  })
                }
                nyitva={nyitottTetel === t.id}
                onNyit={() => setNyitottTetel(nyitottTetel === t.id ? null : t.id)}
                valasztek={valasztek}
                canEdit={canEdit}
                onFrissit={onFrissit}
                onJovahagy={(id) =>
                  void muvelet(`/api/v1/utalasok/${adag.id}/jovahagyas`, { tetel_idk: [id] }, eredmenySzoveg("Jóváhagyás"))
                }
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Műveletsáv - a folyamat sorrendjében: besorolás → jóváhagyás → rögzítés */}
      <div className="sticky bottom-0 flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2">
        <span className="text-[12.5px] text-text-secondary">{kijelolt.size} kijelölve</span>
        {canEdit && (
          <>
            <button
              type="button"
              disabled={busy || kijeloltNyitott.length === 0}
              onClick={() =>
                void muvelet(
                  `/api/v1/utalasok/${adag.id}/elszamolas`,
                  { tetel_idk: kijeloltNyitott.map((t) => t.id), elszamolas: "hype" },
                  (d) => `${d.modositott} tétel HYPE-ra sorolva (megerősítve).`,
                )
              }
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Kijelöltek → HYPE
            </button>
            <button
              type="button"
              disabled={busy || kijeloltNyitott.length === 0}
              onClick={() =>
                void muvelet(
                  `/api/v1/utalasok/${adag.id}/elszamolas`,
                  { tetel_idk: kijeloltNyitott.map((t) => t.id), elszamolas: "krumpello" },
                  (d) => `${d.modositott} tétel Krumpellóhoz sorolva - ebben az adagban lezárt, máshol kézzel kezelendő.`,
                )
              }
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Kijelöltek → Krumpelló
            </button>
            <button
              type="button"
              disabled={busy || nemMegerositett.length === 0}
              onClick={() =>
                void muvelet(
                  `/api/v1/utalasok/${adag.id}/elszamolas`,
                  { tetel_idk: [], elszamolas: "hype", fennmaradok: true },
                  (d) => `${d.modositott} fennmaradó tétel HYPE-besorolása megerősítve.`,
                )
              }
              title="Minden még meg nem erősített, nyitott tétel HYPE-besorolásának megerősítése egyben"
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Fennmaradók → HYPE megerősítése ({nemMegerositett.length})
            </button>
            <button
              type="button"
              disabled={busy || jovahagyhato.length === 0}
              onClick={() =>
                void muvelet(
                  `/api/v1/utalasok/${adag.id}/jovahagyas`,
                  { tetel_idk: jovahagyhato.map((t) => t.id) },
                  eredmenySzoveg("Jóváhagyás"),
                )
              }
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Kijelöltek jóváhagyása ({jovahagyhato.length})
            </button>
          </>
        )}
        {canDelete && rogzitettKijelolt.length > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void visszavonas()}
            className="rounded-[var(--radius)] border border-text-danger/40 px-2.5 py-1 text-[12px] text-text-danger hover:bg-text-danger/10 disabled:opacity-50"
          >
            Felvezetés visszavonása ({rogzitettKijelolt.length})
          </button>
        )}
        {canCreate && (
          <button
            type="button"
            disabled={busy || rogzithetoKijelolt.length === 0}
            onClick={() => void rogzites()}
            className="ml-auto rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[12.5px] font-medium text-text-accent hover:opacity-90 disabled:opacity-40"
            title={
              rogzithetoKijelolt.length === 0
                ? "Rögzíteni csak JÓVÁHAGYOTT tételt lehet - előbb hagyd jóvá a besorolást"
                : undefined
            }
          >
            Kijelölt jóváhagyottak rögzítése ({rogzithetoKijelolt.length})
          </button>
        )}
      </div>

      {/* Krumpelló-lista: ebben az adagban lezárt, máshol kézzel kezelendő */}
      {krumplisok.length > 0 && (
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2">
          <p className="mb-1 text-[12.5px] font-medium text-text-primary">
            Krumpelló – máshol kézzel kezelendő ({krumplisok.length})
          </p>
          <ul className="space-y-0.5 text-[12px] text-text-secondary">
            {krumplisok.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-2">
                <span>
                  {t.kibocsato_nev || t.fajl_nev || `#${t.id}`} – {t.szamlaszam || "számlaszám nélkül"} – {bruttoSzoveg(t)}
                </span>
                {t.url && (
                  <a href={t.url} target="_blank" rel="noreferrer" className="text-text-accent hover:underline">
                    fájl
                  </a>
                )}
                {t.allapot !== "krumpello" && <StatusBadge label="Megerősítésre vár" tone="warning" />}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function TetelSor({
  t,
  adag,
  kijelolve,
  onKijelol,
  nyitva,
  onNyit,
  valasztek,
  canEdit,
  onFrissit,
  onJovahagy,
}: {
  t: UtalasTetel;
  adag: UtalasAdagReszlet;
  kijelolve: boolean;
  onKijelol: (be: boolean) => void;
  nyitva: boolean;
  onNyit: () => void;
  valasztek: Valasztek;
  canEdit: boolean;
  onFrissit: () => void;
  onJovahagy: (tetelId: number) => void;
}) {
  const [busy, setBusy] = useState(false);
  const elteroDatum = !!t.utalas_datum && t.utalas_datum !== adag.utalas_datum;
  const lezart = LEZART.has(t.allapot);

  async function patch(adat: Record<string, unknown>) {
    setBusy(true);
    try {
      const r = await authFetch(`/api/v1/utalasok/tetel/${t.id}`, { method: "PATCH", body: JSON.stringify(adat) });
      if (!r.ok) {
        const d = await r.json().catch(() => null);
        alert(d?.detail ?? `Sikertelen (${r.status})`);
      }
      onFrissit();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <tr className={`border-b border-border/60 ${nyitva ? "bg-surface-3/60" : ""}`}>
        <td className="py-2 pr-2 align-top">
          <input type="checkbox" checked={kijelolve} onChange={(e) => onKijelol(e.target.checked)} />
        </td>
        <td className="max-w-[200px] cursor-pointer py-2 pr-3 align-top" onClick={onNyit}>
          <span className="block truncate font-medium text-text-primary">{t.szamlaszam || t.fajl_nev || `#${t.id}`}</span>
          <span className="block truncate text-[11.5px] text-text-muted">{t.fajl_utvonal}</span>
        </td>
        <td className="max-w-[160px] cursor-pointer py-2 pr-3 align-top" onClick={onNyit}>
          <span className="block truncate text-text-secondary">{t.kibocsato_nev || "–"}</span>
        </td>
        <td className="py-2 pr-3 text-right align-top text-text-primary">{bruttoSzoveg(t)}</td>
        <td className="py-2 pr-3 align-top">
          <span className="flex items-center gap-1">
            {canEdit && !lezart && t.allapot !== "rogzitve" ? (
              <select
                value={t.elszamolas}
                disabled={busy}
                onChange={(e) => void patch({ elszamolas: e.target.value })}
                className={`rounded-[var(--radius)] border px-1.5 py-1 text-[12px] ${t.elszamolas === "tisztazando" ? "border-text-warning/60 bg-bg-warning text-text-warning" : "border-border bg-surface-2 text-text-primary"}`}
              >
                <option value="hype">HYPE</option>
                <option value="krumpello">Krumpelló</option>
                <option value="tisztazando">Tisztázandó</option>
              </select>
            ) : (
              <span className="text-text-secondary">{ELSZAMOLAS_CIMKE[t.elszamolas] ?? t.elszamolas}</span>
            )}
            {!t.elszamolas_megerositve && !lezart && t.allapot !== "feldolgozas" && (
              <span title="A besorolást még nem erősítette meg senki" className="text-[11px] text-text-warning">
                ?
              </span>
            )}
          </span>
        </td>
        <td className="max-w-[230px] cursor-pointer py-2 pr-3 align-top" onClick={onNyit}>
          <span className="block truncate text-text-secondary">{t.cel_cimke || "–"}</span>
        </td>
        <td className="py-2 pr-3 align-top text-text-secondary">
          {t.cel_fizetesi_allapot
            ? t.cel_fizetesi_allapot.kifizetve
              ? `Kifizetve${t.cel_fizetesi_allapot.datum ? ` (${huDatum(t.cel_fizetesi_allapot.datum)})` : ""}`
              : "Nyitott"
            : "–"}
        </td>
        <td className="py-2 pr-3 align-top">
          <span className="flex items-center gap-1">
            {canEdit && !lezart ? (
              <input
                type="date"
                value={t.utalas_datum ?? adag.utalas_datum}
                disabled={busy}
                onChange={(e) => void patch({ utalas_datum: e.target.value === adag.utalas_datum ? "" : e.target.value })}
                className={`rounded-[var(--radius)] border px-1.5 py-1 text-[12px] ${elteroDatum ? "border-text-orange bg-bg-orange text-text-orange" : "border-border bg-surface-2 text-text-primary"}`}
              />
            ) : (
              <span className="text-text-secondary">{huDatum(t.ervenyes_datum)}</span>
            )}
            {elteroDatum && <StatusBadge label="Eltér az adagtól" tone="orange" />}
          </span>
        </td>
        <td className="py-2 align-top">
          <span className="flex flex-col items-start gap-1">
            <button type="button" onClick={onNyit} className="text-left">
              <StatusBadge label={t.allapot_cimke ?? t.allapot} tone={ALLAPOT_TONE[t.allapot] ?? "neutral"} />
            </button>
            {canEdit && t.allapot === "rogzitheto" && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onJovahagy(t.id)}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-2 py-0.5 text-[11.5px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                Jóváhagyás
              </button>
            )}
          </span>
        </td>
      </tr>
      {nyitva && (
        <tr className="border-b border-border/60 bg-surface-3/40">
          <td colSpan={9} className="px-3 py-3">
            <TetelReszletek t={t} valasztek={valasztek} canEdit={canEdit} busy={busy} patch={patch} onJovahagy={onJovahagy} />
          </td>
        </tr>
      )}
    </>
  );
}

/** Kereshető KÉZI célválasztó - a Beérkező számlák cél-választékát használja
 * (ugyanazok az emberi címkék: partner, projekt, összeg, állapot). */
function KeziCelValaszto({
  t,
  busy,
  patch,
}: {
  t: UtalasTetel;
  busy: boolean;
  patch: (adat: Record<string, unknown>) => Promise<void>;
}) {
  const [tipus, setTipus] = useState<"kiadas_csatolas" | "kulsos_tig" | "belsos_tig">("kiadas_csatolas");
  const [opciok, setOpciok] = useState<{ value: string; label: string }[] | null>(null);

  useEffect(() => {
    let elve = false;
    setOpciok(null);
    authFetch(`/api/v1/bejovo-szamlak/celok/${tipus}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!elve && d) setOpciok(d.lista.map((x: { id: number; cimke: string }) => ({ value: String(x.id), label: x.cimke })));
      })
      .catch(() => {
        if (!elve) setOpciok([]);
      });
    return () => {
      elve = true;
    };
  }, [tipus]);

  return (
    <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
      <span className="text-text-muted">Kézi keresés:</span>
      <select
        value={tipus}
        onChange={(e) => setTipus(e.target.value as typeof tipus)}
        className="rounded-[var(--radius)] border border-border bg-surface-2 px-1.5 py-1 text-[12px] text-text-primary"
      >
        <option value="kiadas_csatolas">Meglévő kiadás</option>
        <option value="kulsos_tig">Külsős TIG</option>
        <option value="belsos_tig">Belsős TIG</option>
      </select>
      <div className="min-w-[260px] flex-1">
        <KeresosSelect
          value=""
          onChange={(v: string) => {
            if (!v) return;
            const id = Number(v);
            if (tipus === "kiadas_csatolas") void patch({ cel_expense_id: id });
            else if (tipus === "kulsos_tig") void patch({ cel_certificate_id: id });
            else void patch({ cel_internal_certificate_id: id });
          }}
          options={opciok ?? []}
          placeholder={opciok === null ? "Betöltés…" : opciok.length === 0 ? "Nincs kereshető tétel ebben a típusban" : "Keress partnerre, projektre, összegre…"}
        />
      </div>
      <span className="text-[11.5px] text-text-muted">{busy ? "Mentés…" : ""}</span>
    </div>
  );
}

function TetelReszletek({
  t,
  valasztek,
  canEdit,
  busy,
  patch,
  onJovahagy,
}: {
  t: UtalasTetel;
  valasztek: Valasztek;
  canEdit: boolean;
  busy: boolean;
  patch: (adat: Record<string, unknown>) => Promise<void>;
  onJovahagy: (tetelId: number) => void;
}) {
  const alternativak = t.javaslat?.alternativak ?? [];
  const figyelmeztetesek = t.javaslat?.figyelmeztetesek ?? [];
  const szerkesztheto = canEdit && !LEZART.has(t.allapot);
  const [javitas, setJavitas] = useState<{ szamlaszam: string; kibocsato_nev: string; netto: string; brutto: string } | null>(null);

  return (
    <div className="grid gap-4 md:grid-cols-[1fr_1fr]">
      <div className="space-y-2">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-text-muted">Mit olvastunk ki</p>
        <dl className="grid grid-cols-[130px_1fr] gap-y-1 text-[12.5px]">
          <dt className="text-text-muted">Kibocsátó</dt>
          <dd className="text-text-primary">{t.kibocsato_nev || "–"} {t.kibocsato_adoszam ? `(${t.kibocsato_adoszam})` : ""}</dd>
          <dt className="text-text-muted">Vevő</dt>
          <dd className="text-text-primary">{t.vevo_nev || "–"} <span className="text-text-muted">(a vevő nem dönti el az elszámolási helyet)</span></dd>
          <dt className="text-text-muted">Számlaszám</dt>
          <dd className="text-text-primary">{t.szamlaszam || "–"}</dd>
          <dt className="text-text-muted">Nettó / bruttó</dt>
          <dd className="text-text-primary">
            {t.netto != null ? formatSzam(t.netto) : "–"} / {t.brutto != null ? formatSzam(t.brutto) : "–"} {t.penznem}
          </dd>
          <dt className="text-text-muted">Teljesítés</dt>
          <dd className="text-text-primary">{huDatum(t.teljesites_datuma) || "–"}</dd>
          <dt className="text-text-muted">Fiz. határidő</dt>
          <dd className="text-text-primary">{huDatum(t.fizetesi_hatarido) || "–"}</dd>
        </dl>
        {t.url && (
          <p>
            <a
              href={t.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-[12.5px] text-text-accent underline-offset-2 hover:underline"
            >
              <ExternalLink size={12} /> Számla megnyitása / előnézet
            </a>
          </p>
        )}
        {szerkesztheto && (
          <div className="rounded-[var(--radius)] border border-border bg-surface-2 p-2">
            {javitas === null ? (
              <button
                type="button"
                onClick={() =>
                  setJavitas({
                    szamlaszam: t.szamlaszam ?? "",
                    kibocsato_nev: t.kibocsato_nev ?? "",
                    netto: t.netto != null ? String(t.netto) : "",
                    brutto: t.brutto != null ? String(t.brutto) : "",
                  })
                }
                className="text-[12.5px] text-text-accent hover:underline"
              >
                ✎ Hibásan felismert adat javítása
              </button>
            ) : (
              <div className="space-y-1.5 text-[12.5px]">
                <div className="grid grid-cols-2 gap-1.5">
                  <label className="flex flex-col gap-0.5 text-text-muted">
                    Számlaszám
                    <input value={javitas.szamlaszam} onChange={(e) => setJavitas({ ...javitas, szamlaszam: e.target.value })} className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-1 text-text-primary" />
                  </label>
                  <label className="flex flex-col gap-0.5 text-text-muted">
                    Kibocsátó
                    <input value={javitas.kibocsato_nev} onChange={(e) => setJavitas({ ...javitas, kibocsato_nev: e.target.value })} className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-1 text-text-primary" />
                  </label>
                  <label className="flex flex-col gap-0.5 text-text-muted">
                    Nettó
                    <input type="number" value={javitas.netto} onChange={(e) => setJavitas({ ...javitas, netto: e.target.value })} className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-1 text-text-primary" />
                  </label>
                  <label className="flex flex-col gap-0.5 text-text-muted">
                    Bruttó
                    <input type="number" value={javitas.brutto} onChange={(e) => setJavitas({ ...javitas, brutto: e.target.value })} className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-1 text-text-primary" />
                  </label>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      const adat: Record<string, unknown> = {
                        szamlaszam: javitas.szamlaszam,
                        kibocsato_nev: javitas.kibocsato_nev,
                      };
                      if (javitas.netto !== "") adat.netto = Number(javitas.netto);
                      if (javitas.brutto !== "") adat.brutto = Number(javitas.brutto);
                      void patch(adat).then(() => setJavitas(null));
                    }}
                    className="rounded-[var(--radius)] border border-border bg-bg-accent px-2 py-0.5 text-[12px] text-text-accent"
                  >
                    Mentés
                  </button>
                  <button type="button" onClick={() => setJavitas(null)} className="text-[12px] text-text-muted hover:underline">
                    Mégse
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
        {t.hiba_uzenet && <p className="text-[12.5px] text-text-danger">{t.hiba_uzenet}</p>}
        {figyelmeztetesek.length > 0 && (
          <ul className="list-inside list-disc text-[12px] text-text-warning">
            {figyelmeztetesek.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-text-muted">Cél és művelet</p>
        {t.javaslat?.indoklas && <p className="text-[12.5px] text-text-secondary">{t.javaslat.indoklas}</p>}
        {t.cel_link && (
          <a href={t.cel_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12.5px] text-text-accent underline-offset-2 hover:underline">
            <ExternalLink size={12} /> Célrekord megnyitása
          </a>
        )}
        {szerkesztheto && alternativak.length > 0 && (
          <details open={t.allapot === "valasztas"} className="rounded-[var(--radius)] border border-border bg-surface-2 p-2">
            <summary className="cursor-pointer text-[12.5px] text-text-secondary">
              Javasolt célok ({alternativak.length})
            </summary>
            <ul className="mt-1.5 space-y-1.5">
              {alternativak.map((a, i) => (
                <li key={i} className="flex items-start gap-2 text-[12.5px]">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      if (a.tipus === "kulsos_tig") void patch({ cel_certificate_id: a.cel_id });
                      else if (a.tipus === "belsos_tig") void patch({ cel_internal_certificate_id: a.cel_id });
                      else if (a.tipus === "kiadas_csatolas") void patch({ cel_expense_id: a.cel_id });
                      else if (a.tipus === "kiadas_uj") void patch({ cel_tipus: "uj_kiadas", uj_kiadas: { project_code_id: a.cel_id } });
                    }}
                    className="shrink-0 rounded-[var(--radius)] border border-border bg-bg-accent px-2 py-0.5 text-[11.5px] text-text-accent hover:opacity-90 disabled:opacity-50"
                  >
                    Ezt választom
                  </button>
                  <span className="text-text-secondary">
                    <b className="text-text-primary">{a.cimke}</b>
                    {a.indoklas ? ` – ${a.indoklas}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}
        {szerkesztheto && <KeziCelValaszto t={t} busy={busy} patch={patch} />}
        {szerkesztheto && (
          <div className="space-y-1.5 rounded-[var(--radius)] border border-border bg-surface-2 p-2 text-[12.5px]">
            <p className="text-text-muted">Új kiadás tervezete (ha nincs meglévő tétel):</p>
            <div className="flex flex-wrap items-center gap-2">
              <div className="w-[280px]">
                <KeresosSelect
                  value={t.uj_kiadas?.project_code_id ? String(t.uj_kiadas.project_code_id) : ""}
                  onChange={(v: string) =>
                    void patch({ cel_tipus: "uj_kiadas", uj_kiadas: { project_code_id: v ? Number(v) : null, mukodesi: false } })
                  }
                  options={valasztek.projektkodok.map((p) => ({
                    value: String(p.id),
                    label: p.nev ? `${p.kod} – ${p.nev}` : p.kod,
                  }))}
                  placeholder="Projektkód + projekt neve…"
                />
              </div>
              <label className="flex cursor-pointer items-center gap-1.5 text-text-secondary">
                <input
                  type="checkbox"
                  checked={t.cel_tipus === "uj_kiadas" && t.uj_kiadas?.mukodesi === true}
                  disabled={busy}
                  onChange={(e) =>
                    void patch({
                      cel_tipus: "uj_kiadas",
                      uj_kiadas: { mukodesi: e.target.checked, project_code_id: e.target.checked ? null : (t.uj_kiadas?.project_code_id ?? null) },
                    })
                  }
                />
                Működési kiadás (tudatosan projekt nélkül)
              </label>
            </div>
            {t.cel_tipus === "uj_kiadas" && (
              <p className="text-[12px] text-text-muted">
                A kiadás CSAK a jóváhagyás utáni rögzítéskor jön létre - partner: {t.kibocsato_nev || "?"}, nettó:{" "}
                {t.netto != null ? formatSzam(t.netto) : "?"} {t.penznem}, a számla fájlja csatolódik.
              </p>
            )}
          </div>
        )}
        {szerkesztheto && t.allapot === "osszeg_elter" && (
          <label className="flex items-start gap-2 rounded-[var(--radius)] border border-text-danger/40 bg-bg-danger/40 p-2 text-[12.5px] text-text-primary">
            <input
              type="checkbox"
              checked={t.osszeg_elteres_elfogadva}
              disabled={busy}
              onChange={(e) => void patch({ osszeg_elteres_elfogadva: e.target.checked })}
            />
            <span>
              Elfogadom az összeg-eltérést. Részfizetésnél gondold végig: a teljesen fizetett státusz csak akkor
              jogos, ha a kötelezettség teljes összege rendezett.
            </span>
          </label>
        )}
        <div className="rounded-[var(--radius)] border border-border bg-surface-2 p-2 text-[12.5px] text-text-primary">
          <b>{t.allapot === "rogzitve" || LEZART.has(t.allapot) ? "Ez történt:" : "Ez fog történni:"}</b> {ezTortenik(t)}
        </div>
        {canEdit && t.allapot === "rogzitheto" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onJovahagy(t.id)}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[12.5px] font-medium text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Besorolás jóváhagyása
          </button>
        )}
        {t.besorolas_jovahagyva && t.jovahagyva_at && (
          <p className="text-[12px] text-text-muted">Jóváhagyva: {huDatum(t.jovahagyva_at.slice(0, 10))}</p>
        )}
      </div>
    </div>
  );
}
