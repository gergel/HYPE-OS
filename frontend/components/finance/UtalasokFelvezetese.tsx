"use client";

/** UTALÁSOK FELVEZETÉSE - egy már elutalt számlacsomag adminisztrálása.
 *
 * ZIP feltöltése → KÖTELEZŐ közös utalási dátum → háttér-felismerés és
 * párosítás → ellenőrző táblázat → a kijelölt tételek kifizetésének
 * rögzítése → naplózott visszavonás. Banki utalást NEM indít.
 *
 * A számla vevője (jellemzően HYPE) nem dönti el az elszámolási helyet: a
 * HYPE/Krumpello választás tételenként (vagy kijelöltekre tömegesen)
 * történik. A Krumpellóhoz sorolt tételeket egyelőre csak listázzuk - a
 * felvezetésük később készül el (a felhasználó kérése). */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, RefreshCw, Upload } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { formatSzam } from "@/lib/penz";
import { huDatum } from "@/lib/huDate";
import { KeresosSelect } from "@/components/KeresosSelect";
import { StatusBadge } from "@/components/StatusBadge";
import type { UtalasAdag, UtalasAdagReszlet, UtalasTetel } from "@/lib/api";

type Valasztek = { projektkodok: { id: number; kod: string }[]; emberek: { id: number; nev: string }[] };

const ALLAPOT_TONE: Record<string, "success" | "warning" | "danger" | "neutral" | "accent" | "blue" | "teal" | "orange"> = {
  rogzitheto: "success",
  valasztas: "orange",
  nincs_talalat: "warning",
  mar_kifizetve: "blue",
  osszeg_elter: "danger",
  duplikatum: "neutral",
  nem_feldolgozhato: "danger",
  rogzitve: "teal",
  feldolgozas: "neutral",
};

const ELSZAMOLAS_CIMKE: Record<string, string> = { hype: "HYPE", krumpello: "Krumpello", tisztazando: "Tisztázandó" };

function bruttoSzoveg(t: UtalasTetel): string {
  if (t.brutto != null) return `${formatSzam(t.brutto)} ${t.penznem}`;
  if (t.netto != null) return `${formatSzam(t.netto)} ${t.penznem} (nettó)`;
  return "–";
}

/** Az "Ez fog történni" emberi összefoglalója egy tételhez. */
function ezTortenik(t: UtalasTetel): string {
  const datum = t.ervenyes_datum ? huDatum(t.ervenyes_datum) : "?";
  if (t.elszamolas === "krumpello")
    return "Krumpellóhoz sorolt tétel - itt nem rögzítünk semmit, a listában marad (a Krumpello-felvezetés később készül el).";
  if (t.allapot === "rogzitve") {
    const n = (t.rogzites_naplo || {}) as { mar_igy_volt?: boolean };
    return `Felvezetve: a tétel ${datum} nappal kifizetettként rögzült${n.mar_igy_volt ? " (már eleve így volt, nem módosítottunk)" : ""}.`;
  }
  if (t.allapot === "mar_kifizetve")
    return `Ez a tétel már kifizetett${t.cel_fizetesi_allapot?.datum ? ` (${huDatum(t.cel_fizetesi_allapot.datum)})` : ""} - nem írjuk felül; ellenőrizd, melyik adat az igaz.`;
  if (t.allapot === "duplikatum") return t.hiba_uzenet || "Ugyanez a számla már szerepel - nem vezetjük fel kétszer.";
  if (t.allapot === "nem_feldolgozhato") return t.hiba_uzenet || "Ez a fájl nem dolgozható fel.";
  if (t.allapot === "osszeg_elter")
    return "A számla összege eltér a megtalált tétel összegétől - részfizetés/eltérés csak kifejezett elfogadással rögzíthető (lent pipálható).";
  if (t.cel_tipus === "uj_kiadas")
    return `ÚJ kiadás jön létre (${t.kibocsato_nev || "?"}), a számla csatolásával, és ${datum} nappal kifizetettként rögzül.`;
  if (t.cel_tipus && t.cel_cimke)
    return `Ezt a számlát a(z) „${t.cel_cimke}” tételhez kapcsoljuk, és ${datum} nappal teljesen kifizetettnek jelöljük.`;
  return "Válaszd ki, melyik meglévő tételhez tartozik - vagy készíts belőle új kiadást.";
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

/** Új adag: ZIP + KÖTELEZŐ utalási dátum (nincs "mai nap" alapérték). */
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
        <b className="text-text-primary">Új adag:</b> töltsd fel az elutalt számlákat egy ZIP-ben, és add meg az
        adag közös utalási dátumát. A feltöltéstől még semmi nem válik fizetetté - előbb ellenőrzöl, aztán rögzítesz.
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
      <table className="w-full min-w-[760px] text-[13px]">
        <thead>
          <tr className="border-b border-border text-left text-[11.5px] uppercase tracking-wide text-text-muted">
            <th className="py-2 pr-3">Adag</th>
            <th className="py-2 pr-3">Utalás dátuma</th>
            <th className="py-2 pr-3">Számlák</th>
            <th className="py-2 pr-3">Felvezetve</th>
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
              <td className="py-2 pr-3 text-text-secondary">{a.rogzitett_darab}</td>
              <td className="py-2 pr-3">
                <StatusBadge
                  label={a.allapot === "feldolgozas" ? "Feldolgozás alatt" : a.allapot === "hiba" ? "Hiba" : "Ellenőrizhető"}
                  tone={a.allapot === "hiba" ? "danger" : a.allapot === "feldolgozas" ? "neutral" : "success"}
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

/** Az adag ellenőrző nézete: táblázat + összegzés + műveletek. */
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
  const krumplisok = tetelek.filter((t) => t.elszamolas === "krumpello");
  const rogzithetoKijelolt = tetelek.filter(
    (t) => kijelolt.has(t.id) && t.allapot === "rogzitheto" && t.elszamolas === "hype",
  );
  const rogzitettKijelolt = tetelek.filter((t) => kijelolt.has(t.id) && t.allapot === "rogzitve");

  // Összegzés a véglegesítés előtt.
  const darab = (allapot: string) => tetelek.filter((t) => t.allapot === allapot).length;
  const penznemOsszegek: Record<string, number> = {};
  for (const t of tetelek) {
    if (t.brutto != null) penznemOsszegek[t.penznem] = (penznemOsszegek[t.penznem] || 0) + t.brutto;
  }
  const meglevoValtozik = tetelek.filter((t) => t.allapot === "rogzitheto" && t.cel_tipus && t.cel_tipus !== "uj_kiadas" && t.elszamolas === "hype").length;
  const ujJonLetre = tetelek.filter((t) => t.allapot === "rogzitheto" && t.cel_tipus === "uj_kiadas" && t.elszamolas === "hype").length;
  const tisztazando = tetelek.filter((t) => !["rogzitve", "rogzitheto", "duplikatum"].includes(t.allapot) || t.elszamolas === "tisztazando").length;

  async function tomegesElszamolas(ertek: string) {
    if (kijelolt.size === 0) return;
    setBusy(true);
    try {
      const r = await authFetch(`/api/v1/utalasok/${adag.id}/elszamolas`, {
        method: "POST",
        body: JSON.stringify({ tetel_idk: [...kijelolt], elszamolas: ertek }),
      });
      if (!r.ok) setUzenet(`Sikertelen (${r.status})`);
      onFrissit();
    } finally {
      setBusy(false);
    }
  }

  async function rogzites() {
    if (rogzithetoKijelolt.length === 0) return;
    if (
      !confirm(
        `${rogzithetoKijelolt.length} kijelölt tétel kifizetését rögzítjük a megadott utalási dátumokkal. ` +
          "A művelet a meglévő tételeket kifizetettre állítja, és ahol kell, csatolja a számlát. Folytatod?",
      )
    )
      return;
    setBusy(true);
    setUzenet(null);
    try {
      const r = await authFetch(`/api/v1/utalasok/${adag.id}/rogzites`, {
        method: "POST",
        body: JSON.stringify({ tetel_idk: rogzithetoKijelolt.map((t) => t.id) }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setUzenet(`Sikertelen: ${d?.detail ?? r.status}`);
      } else {
        const hibak = (d.eredmenyek || []).filter((e: { siker: boolean }) => !e.siker);
        setUzenet(
          `${d.sikeres} tétel felvezetve` +
            (d.sikertelen ? `, ${d.sikertelen} nem ment át: ${hibak.map((h: { tetel_id: number; hiba: string }) => `#${h.tetel_id}: ${h.hiba}`).join(" · ")}` : ".") ,
        );
        setKijelolt(new Set());
      }
      onFrissit();
    } catch (err) {
      setUzenet(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function visszavonas() {
    if (rogzitettKijelolt.length === 0) return;
    if (
      !confirm(
        `${rogzitettKijelolt.length} felvezetés visszavonása: a rendszerbeli adminisztrációt állítjuk vissza (a banki utalást nem érinti), ` +
          "és csak azt, amit ez a felvezetés írt - a későbbi kézi módosításokhoz nem nyúlunk. Folytatod?",
      )
    )
      return;
    setBusy(true);
    setUzenet(null);
    try {
      const r = await authFetch(`/api/v1/utalasok/${adag.id}/visszavonas`, {
        method: "POST",
        body: JSON.stringify({ tetel_idk: rogzitettKijelolt.map((t) => t.id) }),
      });
      const d = await r.json().catch(() => null);
      setUzenet(r.ok ? `${d.sikeres} felvezetés visszavonva.` : `Sikertelen: ${d?.detail ?? r.status}`);
      setKijelolt(new Set());
      onFrissit();
    } finally {
      setBusy(false);
    }
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
            <RefreshCw size={12} className="animate-spin" /> Feldolgozás fut - a lista magától frissül
          </span>
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

      {/* Összegzés a véglegesítés előtt */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[12.5px] text-text-secondary">
        <span><b className="text-text-success">{darab("rogzitheto")}</b> rögzíthető</span>
        <span><b className="text-text-primary">{tisztazando}</b> tisztázandó</span>
        <span><b className="text-text-primary">{darab("rogzitve")}</b> felvezetve</span>
        <span>
          HYPE: <b className="text-text-primary">{tetelek.filter((t) => t.elszamolas === "hype").length}</b> · Krumpello:{" "}
          <b className="text-text-primary">{krumplisok.length}</b> · Tisztázandó:{" "}
          <b className="text-text-primary">{tetelek.filter((t) => t.elszamolas === "tisztazando").length}</b>
        </span>
        <span>{meglevoValtozik} meglévő tétel változik, {ujJonLetre} új kiadás jön létre</span>
        {/* Különböző pénznemeket nem adunk össze - pénznemenként külön összeg. */}
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
        <table className="w-full min-w-[1040px] text-[12.5px]">
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
              <th className="py-2 pr-3">Megtalált cél</th>
              <th className="py-2 pr-3">Jelenlegi fiz. állapot</th>
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
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Műveletsáv */}
      <div className="sticky bottom-0 flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2">
        <span className="text-[12.5px] text-text-secondary">{kijelolt.size} kijelölve</span>
        {canEdit && (
          <>
            <button
              type="button"
              disabled={busy || kijelolt.size === 0}
              onClick={() => void tomegesElszamolas("hype")}
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Kijelöltek → HYPE
            </button>
            <button
              type="button"
              disabled={busy || kijelolt.size === 0}
              onClick={() => void tomegesElszamolas("krumpello")}
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Kijelöltek → Krumpello
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
                ? "Jelölj ki Rögzíthető állapotú, HYPE-elszámolású tételeket"
                : undefined
            }
          >
            Kijelölt tételek kifizetésének rögzítése ({rogzithetoKijelolt.length})
          </button>
        )}
      </div>

      {/* Krumpello-lista (egyelőre csak listázás - a felhasználó kérése) */}
      {krumplisok.length > 0 && (
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2">
          <p className="mb-1 text-[12.5px] font-medium text-text-primary">
            Krumpellóhoz sorolt tételek ({krumplisok.length}) - egyelőre csak lista, a felvezetésük később készül el
          </p>
          <ul className="space-y-0.5 text-[12px] text-text-secondary">
            {krumplisok.map((t) => (
              <li key={t.id}>
                {t.kibocsato_nev || t.fajl_nev || `#${t.id}`} – {t.szamlaszam || "számlaszám nélkül"} – {bruttoSzoveg(t)}
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
}) {
  const [busy, setBusy] = useState(false);
  const elteroDatum = !!t.utalas_datum && t.utalas_datum !== adag.utalas_datum;

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
        <td className="max-w-[220px] cursor-pointer py-2 pr-3 align-top" onClick={onNyit}>
          <span className="block truncate font-medium text-text-primary">{t.szamlaszam || t.fajl_nev || `#${t.id}`}</span>
          <span className="block truncate text-[11.5px] text-text-muted">{t.fajl_utvonal}</span>
        </td>
        <td className="max-w-[180px] cursor-pointer py-2 pr-3 align-top" onClick={onNyit}>
          <span className="block truncate text-text-secondary">{t.kibocsato_nev || "–"}</span>
        </td>
        <td className="py-2 pr-3 text-right align-top text-text-primary">{bruttoSzoveg(t)}</td>
        <td className="py-2 pr-3 align-top">
          {canEdit && t.allapot !== "rogzitve" ? (
            <select
              value={t.elszamolas}
              disabled={busy}
              onChange={(e) => void patch({ elszamolas: e.target.value })}
              className={`rounded-[var(--radius)] border px-1.5 py-1 text-[12px] ${t.elszamolas === "tisztazando" ? "border-text-warning/60 bg-bg-warning text-text-warning" : "border-border bg-surface-2 text-text-primary"}`}
            >
              <option value="hype">HYPE</option>
              <option value="krumpello">Krumpello</option>
              <option value="tisztazando">Tisztázandó</option>
            </select>
          ) : (
            <span className="text-text-secondary">{ELSZAMOLAS_CIMKE[t.elszamolas] ?? t.elszamolas}</span>
          )}
        </td>
        <td className="max-w-[240px] cursor-pointer py-2 pr-3 align-top" onClick={onNyit}>
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
            {canEdit && t.allapot !== "rogzitve" ? (
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
          <button type="button" onClick={onNyit} className="text-left">
            <StatusBadge label={t.allapot_cimke ?? t.allapot} tone={ALLAPOT_TONE[t.allapot] ?? "neutral"} />
          </button>
        </td>
      </tr>
      {nyitva && (
        <tr className="border-b border-border/60 bg-surface-3/40">
          <td colSpan={9} className="px-3 py-3">
            <TetelReszletek t={t} valasztek={valasztek} canEdit={canEdit} busy={busy} patch={patch} />
          </td>
        </tr>
      )}
    </>
  );
}

function TetelReszletek({
  t,
  valasztek,
  canEdit,
  busy,
  patch,
}: {
  t: UtalasTetel;
  valasztek: Valasztek;
  canEdit: boolean;
  busy: boolean;
  patch: (adat: Record<string, unknown>) => Promise<void>;
}) {
  const alternativak = t.javaslat?.alternativak ?? [];
  const figyelmeztetesek = t.javaslat?.figyelmeztetesek ?? [];
  const szerkesztheto = canEdit && t.allapot !== "rogzitve";

  return (
    <div className="grid gap-4 md:grid-cols-[1fr_1fr]">
      <div className="space-y-2">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-text-muted">Mit olvastunk ki</p>
        <dl className="grid grid-cols-[130px_1fr] gap-y-1 text-[12.5px]">
          <dt className="text-text-muted">Kibocsátó</dt>
          <dd className="text-text-primary">{t.kibocsato_nev || "–"} {t.kibocsato_adoszam ? `(${t.kibocsato_adoszam})` : ""}</dd>
          <dt className="text-text-muted">Vevő</dt>
          <dd className="text-text-primary">{t.vevo_nev || "–"} <span className="text-text-muted">(a vevőt a belső elszámolás nem írja át)</span></dd>
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
              Választható célok ({alternativak.length})
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
        {szerkesztheto && (
          <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
            <span className="text-text-muted">Új kiadás előkészítése:</span>
            <div className="w-[220px]">
              <KeresosSelect
                value={t.uj_kiadas?.project_code_id ? String(t.uj_kiadas.project_code_id) : ""}
                onChange={(v: string) =>
                  void patch({ cel_tipus: "uj_kiadas", uj_kiadas: { project_code_id: v ? Number(v) : null } })
                }
                options={valasztek.projektkodok.map((p) => ({ value: String(p.id), label: p.kod }))}
                placeholder="Projektkód (üres = működési)"
              />
            </div>
            {t.cel_tipus === "uj_kiadas" && (
              <span className="text-text-muted">Új kiadás készül - jóváhagyáskor jön létre, kifizetettként.</span>
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
              Elfogadom az összeg-eltérést, és így is rögzítem a kifizetést. Részfizetésnél gondold végig: a
              teljesen fizetett státusz csak akkor jogos, ha a kötelezettség teljes összege rendezett.
            </span>
          </label>
        )}
        <div className="rounded-[var(--radius)] border border-border bg-surface-2 p-2 text-[12.5px] text-text-primary">
          <b>Ez fog történni:</b> {ezTortenik(t)}
        </div>
      </div>
    </div>
  );
}
