"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Copy } from "lucide-react";
import { Card } from "@/components/Card";
import { KeresosSelect } from "@/components/KeresosSelect";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import type { Ajanlatkeres, AjanlatkeresReszlet, Employee, MunkaMeghivott } from "@/lib/api";

const BASE = "/api/v1/munkafelajanlasok";

const ALLAPOT_CIMKE: Record<string, { label: string; tone: "neutral" | "blue" | "warning" | "success" | "danger" }> = {
  piszkozat: { label: "Piszkozat", tone: "neutral" },
  ajanlatadas: { label: "Ajánlatadás folyamatban", tone: "blue" },
  dontesre_var: { label: "Döntésre vár", tone: "warning" },
  kiosztva: { label: "Kiosztva", tone: "success" },
  lezarva_nyertes_nelkul: { label: "Lezárva nyertes nélkül", tone: "neutral" },
  visszavonva: { label: "Visszavonva", tone: "danger" },
};

function osszegSzoveg(osszeg: number, penznem: string, brutto: boolean): string {
  return `${osszeg.toLocaleString("hu-HU")} ${penznem} (${brutto ? "bruttó" : "nettó"})`;
}

function idopont(iso: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleString("hu-HU", { timeZone: "Europe/Budapest", dateStyle: "short", timeStyle: "short" });
}

export type ProjektOpcio = { id: number; nev: string; kod: string | null };

/** Az ÚJ ajánlatkérés űrlapja. Felajánlott díjat SZÁNDÉKOSAN nem lehet
 * megadni: az árat a meghívott külsősök ajánlják meg (a felhasználó kérése).
 * A projekt a MEGLÉVŐ projektek közül választandó - nem szabad szöveg. */
function UjAjanlatkeres({ employees, projektek, onKesz }: { employees: Employee[]; projektek: ProjektOpcio[]; onKesz: () => void }) {
  const [nyitva, setNyitva] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [mezok, setMezok] = useState({
    munkakor: "",
    leiras: "",
    helyszin: "",
    munkavegzes_idopont: "",
    teljesitesi_hatarido: "",
    valaszadasi_hatarido: "",
    kapcsolattarto_id: "",
  });
  const [meghivottak, setMeghivottak] = useState<number[]>([]);
  const [szuro, setSzuro] = useState("");

  const valaszthato = useMemo(
    () =>
      employees
        .filter((e) => e.is_active)
        .filter((e) => !szuro.trim() || e.full_name.toLocaleLowerCase("hu-HU").includes(szuro.trim().toLocaleLowerCase("hu-HU")))
        .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu")),
    [employees, szuro],
  );

  function m(nev: keyof typeof mezok, ertek: string) {
    setMezok((elozo) => ({ ...elozo, [nev]: ertek }));
  }

  async function mentes() {
    setHiba(null);
    if (!projectId) {
      setHiba("Válaszd ki a projektet a meglévő projektek közül.");
      return;
    }
    if (!mezok.munkakor.trim()) {
      setHiba("A munkakör megadása kötelező.");
      return;
    }
    if (!mezok.valaszadasi_hatarido) {
      setHiba("A válaszadási határidő megadása kötelező (pontos dátum + időpont).");
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch(BASE, {
        method: "POST",
        body: JSON.stringify({
          ...mezok,
          project_id: Number(projectId),
          kapcsolattarto_id: mezok.kapcsolattarto_id ? Number(mezok.kapcsolattarto_id) : null,
          meghivott_employee_ids: meghivottak,
        }),
      });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        setHiba(`Sikertelen mentés: ${adat?.detail ?? res.status}`);
        return;
      }
      setNyitva(false);
      setProjectId(null);
      setMezok({
        munkakor: "", leiras: "", helyszin: "",
        munkavegzes_idopont: "", teljesitesi_hatarido: "", valaszadasi_hatarido: "", kapcsolattarto_id: "",
      });
      setMeghivottak([]);
      onKesz();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!nyitva) {
    return (
      <button type="button" onClick={() => setNyitva(true)} className="mb-3 text-[13px] text-text-accent hover:underline">
        + Új ajánlatkérés
      </button>
    );
  }

  const beviteli = "w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none";

  return (
    <div className="fade-in mb-4 space-y-3 rounded-[var(--radius-lg)] border border-border bg-surface-3 p-4">
      <p className="text-[13px] font-medium text-text-primary">Új ajánlatkérés (piszkozatként jön létre - a kiküldés külön lépés)</p>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="block text-[12px] text-text-muted">Projekt * <span className="normal-case">(a meglévő projektek közül)</span>
          <KeresosSelect
            value={projectId}
            options={projektek.map((p) => ({
              value: String(p.id),
              label: p.nev,
              sublabel: p.kod ?? undefined,
            }))}
            onChange={(v) => setProjectId(v)}
            placeholder="Válassz projektet…"
            className="mt-0.5"
          />
        </div>
        <label className="block text-[12px] text-text-muted">Munkakör * <span className="normal-case">(külön munkakör = külön ajánlatkérés)</span>
          <input value={mezok.munkakor} onChange={(e) => m("munkakor", e.target.value)} placeholder="pl. Operatőr" className={beviteli} />
        </label>
        <label className="block text-[12px] text-text-muted md:col-span-2">Feladatleírás
          <textarea value={mezok.leiras} onChange={(e) => m("leiras", e.target.value)} rows={2} className={beviteli} />
        </label>
        <label className="block text-[12px] text-text-muted">Helyszín
          <input value={mezok.helyszin} onChange={(e) => m("helyszin", e.target.value)} className={beviteli} />
        </label>
        <label className="block text-[12px] text-text-muted">A munkavégzés várható időpontja
          <input value={mezok.munkavegzes_idopont} onChange={(e) => m("munkavegzes_idopont", e.target.value)} placeholder="pl. 2026. október 12-14." className={beviteli} />
        </label>
        <label className="block text-[12px] text-text-muted">Teljesítési határidő (ha van)
          <input value={mezok.teljesitesi_hatarido} onChange={(e) => m("teljesitesi_hatarido", e.target.value)} placeholder="pl. 2026. október 20." className={beviteli} />
        </label>
        <label className="block text-[12px] text-text-muted">Válaszadási határidő * (magyar idő szerint)
          <input type="datetime-local" value={mezok.valaszadasi_hatarido} onChange={(e) => m("valaszadasi_hatarido", e.target.value)} className={beviteli} />
        </label>
        <label className="block text-[12px] text-text-muted">Kapcsolattartó
          <select value={mezok.kapcsolattarto_id} onChange={(e) => m("kapcsolattarto_id", e.target.value)} className={beviteli}>
            <option value="">– nincs megadva –</option>
            {employees.filter((e) => e.is_active).map((e) => (
              <option key={e.id} value={e.id}>{e.full_name}</option>
            ))}
          </select>
        </label>
      </div>

      <div>
        <p className="mb-1 text-[12px] text-text-muted">Meghívott külsősök ({meghivottak.length}) - mindenki külön, személyre szóló levelet és saját linket kap</p>
        <input value={szuro} onChange={(e) => setSzuro(e.target.value)} placeholder="Keresés név szerint…" className={`${beviteli} mb-1.5 max-w-xs`} />
        <div className="flex max-h-44 flex-wrap gap-x-4 gap-y-1 overflow-y-auto rounded-[var(--radius)] border border-border p-2">
          {valaszthato.map((e) => (
            <label key={e.id} className={`flex items-center gap-1.5 text-[12.5px] ${e.email ? "text-text-secondary" : "text-text-muted"}`}>
              <input
                type="checkbox"
                checked={meghivottak.includes(e.id)}
                onChange={() =>
                  setMeghivottak((elozo) => (elozo.includes(e.id) ? elozo.filter((i) => i !== e.id) : [...elozo, e.id]))
                }
              />
              {e.full_name}
              {!e.email && <span className="text-[11px] text-text-danger">(nincs e-mail!)</span>}
            </label>
          ))}
        </div>
      </div>

      {hiba && <p className="text-[12.5px] text-text-danger">{hiba}</p>}
      <div className="flex gap-2">
        <button type="button" disabled={busy} onClick={() => void mentes()} className="btn btn-primary disabled:opacity-50">
          {busy ? "Mentés…" : "Piszkozat mentése"}
        </button>
        <button type="button" onClick={() => setNyitva(false)} className="text-[13px] text-text-muted hover:text-text-primary">Mégse</button>
      </div>
    </div>
  );
}

/** Egy ajánlatkérés kibontott részletei: meghívottak + összehasonlító tábla +
 * műveletek (kiküldés, kiválasztás, lezárás, újraküldés). */
function Reszletek({
  ak,
  canEdit,
  canDelete,
  onValtozas,
}: {
  ak: AjanlatkeresReszlet;
  canEdit: boolean;
  canDelete: boolean;
  onValtozas: (friss: AjanlatkeresReszlet | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  // Kétfázisú megerősítések (házon belüli UX-elv: natív confirm() helyett):
  // melyik művelet vár megerősítésre.
  const [megerosites, setMegerosites] = useState<
    | { tipus: "kikuldes" }
    | { tipus: "kivalasztas"; meghivott: MunkaMeghivott }
    | { tipus: "lezaras" }
    | { tipus: "visszavonas" }
    | { tipus: "torles" }
    | null
  >(null);
  const [lezarasMegjegyzes, setLezarasMegjegyzes] = useState("");

  async function hivas(ut: string, method = "POST", torzs?: unknown): Promise<void> {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(ut, { method, body: torzs !== undefined ? JSON.stringify(torzs) : undefined });
      if (res.status === 204) {
        onValtozas(null);
        return;
      }
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        setHiba(`Sikertelen: ${adat?.detail ?? res.status}`);
        return;
      }
      onValtozas(adat as AjanlatkeresReszlet);
      setMegerosites(null);
    } catch (err) {
      setHiba(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  const kuldesHibak = ak.meghivottak.filter((m) => m.meghivo_hiba || m.eredmeny_hiba);
  const vanElo = ak.meghivottak.some((m) => m.ajanlat && !m.ajanlat.visszavonva);

  return (
    <div className="space-y-3 border-t border-border pt-3">
      <div className="grid gap-x-6 gap-y-1 text-[12.5px] md:grid-cols-2">
        {ak.leiras && <p><span className="text-text-muted">Feladat:</span> <span className="text-text-secondary">{ak.leiras}</span></p>}
        {ak.helyszin && <p><span className="text-text-muted">Helyszín:</span> <span className="text-text-secondary">{ak.helyszin}</span></p>}
        {ak.munkavegzes_idopont && <p><span className="text-text-muted">Munkavégzés:</span> <span className="text-text-secondary">{ak.munkavegzes_idopont}</span></p>}
        {ak.teljesitesi_hatarido && <p><span className="text-text-muted">Teljesítési határidő:</span> <span className="text-text-secondary">{ak.teljesitesi_hatarido}</span></p>}
        {ak.kapcsolattarto_nev && <p><span className="text-text-muted">Kapcsolattartó:</span> <span className="text-text-secondary">{ak.kapcsolattarto_nev}</span></p>}
        {ak.allapot === "kiosztva" && ak.elfogadott_osszeg !== null && (
          <p><span className="text-text-muted">Elfogadott feltételek:</span>{" "}
            <span className="font-medium text-text-success">
              {osszegSzoveg(ak.elfogadott_osszeg, ak.elfogadott_penznem ?? "HUF", !!ak.elfogadott_brutto)}
            </span>
          </p>
        )}
        {ak.lezaras_megjegyzes && <p><span className="text-text-muted">Lezárás indoka:</span> <span className="text-text-secondary">{ak.lezaras_megjegyzes}</span></p>}
      </div>

      {/* Meghívottak + ajánlatok összehasonlító táblája */}
      {ak.meghivottak.length === 0 ? (
        <p className="text-[12.5px] italic text-text-muted">Még nincs meghívott külsős.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                <th className="py-1.5 pr-3 font-medium">Külsős</th>
                <th className="py-1.5 pr-3 font-medium">Meghívó</th>
                <th className="py-1.5 pr-3 font-medium">Ajánlott összeg</th>
                <th className="py-1.5 pr-3 font-medium">Megjegyzés / feltétel</th>
                <th className="py-1.5 pr-3 font-medium">Beküldve / módosítva</th>
                <th className="py-1.5 pr-3 font-medium">Ajánlat állapota</th>
                <th className="py-1.5 font-medium" />
              </tr>
            </thead>
            <tbody>
              {ak.meghivottak.map((mh) => (
                <tr key={mh.id} className={`border-b border-border/60 align-top ${mh.nyertes ? "bg-bg-success/30" : ""}`}>
                  <td className="py-2 pr-3">
                    <p className="text-text-primary">{mh.nev}{mh.nyertes && <span className="ml-1.5 text-[11px] font-semibold uppercase text-text-success">nyertes</span>}</p>
                    <p className="text-[11.5px] text-text-muted">{mh.email ?? "nincs e-mail"}</p>
                  </td>
                  <td className="py-2 pr-3">
                    {mh.meghivo_kikuldve ? (
                      <StatusBadge label="Kiküldve" tone="success" />
                    ) : mh.meghivo_hiba ? (
                      <span title={mh.meghivo_hiba}><StatusBadge label="Küldési hiba" tone="danger" /></span>
                    ) : (
                      <StatusBadge label="Nincs kiküldve" tone="neutral" />
                    )}
                    {mh.eredmeny_hiba && (
                      <p className="mt-0.5 text-[11px] text-text-danger" title={mh.eredmeny_hiba}>eredmény-levél hiba</p>
                    )}
                    {mh.eredmeny_kikuldve && <p className="mt-0.5 text-[11px] text-text-muted">eredmény kiküldve</p>}
                  </td>
                  <td className="py-2 pr-3 text-text-primary">
                    {mh.ajanlat ? osszegSzoveg(mh.ajanlat.osszeg, mh.ajanlat.penznem, mh.ajanlat.brutto) : <span className="text-text-muted">–</span>}
                  </td>
                  <td className="max-w-[220px] py-2 pr-3 text-text-secondary [overflow-wrap:anywhere]">{mh.ajanlat?.megjegyzes ?? "–"}</td>
                  <td className="py-2 pr-3 text-text-secondary">
                    {mh.ajanlat ? (
                      <>
                        {idopont(mh.ajanlat.bekuldve)}
                        {mh.ajanlat.modositva && <p className="text-[11px] text-text-muted">mód.: {idopont(mh.ajanlat.modositva)}</p>}
                      </>
                    ) : "–"}
                  </td>
                  <td className="py-2 pr-3">
                    {mh.ajanlat ? (
                      <StatusBadge
                        label={{ bekuldve: "Beküldve", visszavonva: "Visszavonva", elfogadva: "Elfogadva", elutasitva: "Elutasítva" }[mh.ajanlat.allapot]}
                        tone={{ bekuldve: "blue" as const, visszavonva: "neutral" as const, elfogadva: "success" as const, elutasitva: "neutral" as const }[mh.ajanlat.allapot]}
                      />
                    ) : (
                      <StatusBadge label="Nem adott ajánlatot" tone="neutral" />
                    )}
                  </td>
                  <td className="py-2 text-right">
                    <button
                      type="button"
                      title="A személyes ajánlati link másolása"
                      onClick={() => void navigator.clipboard?.writeText(mh.link).catch(() => {})}
                      className="p-1 text-text-muted hover:text-text-secondary"
                    >
                      <Copy size={13} />
                    </button>
                    {canEdit && ak.allapot === "dontesre_var" && mh.ajanlat && !mh.ajanlat.visszavonva && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => setMegerosites({ tipus: "kivalasztas", meghivott: mh })}
                        className="ml-2 rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-primary hover:bg-surface-2 disabled:opacity-50"
                      >
                        Kiválasztom
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {/* ÜRES állapot (a felhasználó kérése): lejárt, de egyetlen ajánlat sem jött. */}
          {ak.allapot === "dontesre_var" && !vanElo && (
            <p className="mt-2 rounded-[var(--radius)] bg-bg-warning px-3 py-2 text-[12.5px] text-text-warning">
              Nem érkezett ajánlat a határidőig. Az ajánlatkérés lezárható nyertes nélkül.
            </p>
          )}
        </div>
      )}

      {/* Megerősítő panelek (kétfázisú, natív confirm() nélkül) */}
      {megerosites?.tipus === "kivalasztas" && megerosites.meghivott.ajanlat && (
        <div className="rounded-[var(--radius)] border border-text-accent/40 bg-surface-3 p-3 text-[13px]">
          <p className="font-medium text-text-primary">A kiválasztás megerősítése</p>
          <p className="mt-1 text-text-secondary">
            Feladat: <strong>{ak.projekt_nev} – {ak.munkakor}</strong><br />
            Vállalkozó: <strong>{megerosites.meghivott.nev}</strong><br />
            Elfogadott ajánlat: <strong>{osszegSzoveg(megerosites.meghivott.ajanlat.osszeg, megerosites.meghivott.ajanlat.penznem, megerosites.meghivott.ajanlat.brutto)}</strong>
          </p>
          <p className="mt-1 text-[12px] text-text-muted">
            A megerősítés rögzíti a megbízott személyét és az elfogadott feltételeket, majd mindenki megkapja a
            személyre szabott értesítést. Egy pozícióhoz csak egy nyertes tartozhat.
          </p>
          <div className="mt-2 flex gap-2">
            <button type="button" disabled={busy} onClick={() => void hivas(`${BASE}/${ak.id}/kivalasztas`, "POST", { meghivott_id: megerosites.meghivott.id })} className="btn btn-primary disabled:opacity-50">
              {busy ? "Rögzítés…" : "Megerősítem a kiválasztást"}
            </button>
            <button type="button" onClick={() => setMegerosites(null)} className="text-[13px] text-text-muted hover:text-text-primary">Mégse</button>
          </div>
        </div>
      )}
      {megerosites?.tipus === "kikuldes" && (
        <div className="rounded-[var(--radius)] border border-text-accent/40 bg-surface-3 p-3 text-[13px]">
          <p className="text-text-secondary">
            Kiküldöd az ajánlatkérést <strong>{ak.meghivott_db} meghívottnak</strong>? Mindenki külön, személyre szóló
            levelet és saját linket kap; a válaszadási határidő: <strong>{ak.valaszadasi_hatarido_szoveg}</strong> (magyar idő szerint).
          </p>
          <div className="mt-2 flex gap-2">
            <button type="button" disabled={busy} onClick={() => void hivas(`${BASE}/${ak.id}/kikuldes`)} className="btn btn-primary disabled:opacity-50">
              {busy ? "Küldés…" : "Kiküldés most"}
            </button>
            <button type="button" onClick={() => setMegerosites(null)} className="text-[13px] text-text-muted hover:text-text-primary">Mégse</button>
          </div>
        </div>
      )}
      {megerosites?.tipus === "lezaras" && (
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 p-3 text-[13px]">
          <p className="text-text-secondary">Lezárod az ajánlatkérést <strong>nyertes kihirdetése nélkül</strong>? A meghívottak ennek megfelelő értesítést kapnak.</p>
          <input
            value={lezarasMegjegyzes}
            onChange={(e) => setLezarasMegjegyzes(e.target.value)}
            placeholder="Belső megjegyzés (nem megy ki e-mailben)…"
            className="mt-2 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
          <div className="mt-2 flex gap-2">
            <button type="button" disabled={busy} onClick={() => void hivas(`${BASE}/${ak.id}/lezaras-nyertes-nelkul`, "POST", { megjegyzes: lezarasMegjegyzes })} className="btn btn-primary disabled:opacity-50">
              {busy ? "Lezárás…" : "Lezárás nyertes nélkül"}
            </button>
            <button type="button" onClick={() => setMegerosites(null)} className="text-[13px] text-text-muted hover:text-text-primary">Mégse</button>
          </div>
        </div>
      )}
      {megerosites?.tipus === "visszavonas" && (
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 p-3 text-[13px]">
          <p className="text-text-secondary">Visszavonod az ajánlatkérést? Aki már kapott meghívót, visszavonó értesítést kap, és a linkje lezárul.</p>
          <div className="mt-2 flex gap-2">
            <button type="button" disabled={busy} onClick={() => void hivas(`${BASE}/${ak.id}/visszavonas`)} className="rounded-[var(--radius)] border border-text-danger px-3 py-1.5 text-[13px] text-text-danger hover:bg-surface-2 disabled:opacity-50">
              {busy ? "Visszavonás…" : "Visszavonás megerősítése"}
            </button>
            <button type="button" onClick={() => setMegerosites(null)} className="text-[13px] text-text-muted hover:text-text-primary">Mégse</button>
          </div>
        </div>
      )}
      {megerosites?.tipus === "torles" && (
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 p-3 text-[13px]">
          <p className="text-text-secondary">Törlöd ezt a piszkozatot? Ez nem visszavonható.</p>
          <div className="mt-2 flex gap-2">
            <button type="button" disabled={busy} onClick={() => void hivas(`${BASE}/${ak.id}`, "DELETE")} className="rounded-[var(--radius)] border border-text-danger px-3 py-1.5 text-[13px] text-text-danger hover:bg-surface-2 disabled:opacity-50">
              {busy ? "Törlés…" : "Törlés megerősítése"}
            </button>
            <button type="button" onClick={() => setMegerosites(null)} className="text-[13px] text-text-muted hover:text-text-primary">Mégse</button>
          </div>
        </div>
      )}

      {hiba && <p className="text-[12.5px] text-text-danger">{hiba}</p>}

      {/* Műveletek */}
      {canEdit && !megerosites && (
        <div className="flex flex-wrap gap-2">
          {ak.allapot === "piszkozat" && (
            <>
              <button type="button" disabled={busy || ak.meghivott_db === 0} onClick={() => setMegerosites({ tipus: "kikuldes" })} className="btn btn-primary disabled:opacity-50" title={ak.meghivott_db === 0 ? "Előbb válassz meghívottakat" : undefined}>
                Ajánlatkérés kiküldése
              </button>
              {canDelete && (
                <button type="button" disabled={busy} onClick={() => setMegerosites({ tipus: "torles" })} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:text-text-danger disabled:opacity-50">
                  Piszkozat törlése
                </button>
              )}
            </>
          )}
          {ak.allapot === "ajanlatadas" && (
            <>
              <p className="w-full text-[12.5px] text-text-muted">
                Az ajánlatok a határidő előtt is megtekinthetők, de a végleges kiválasztás csak a határidő lejárta
                után lesz elérhető. A rendszer nem választ automatikusan sem a leggyorsabb, sem a legolcsóbb ajánlat alapján.
              </p>
              <button type="button" disabled={busy} onClick={() => setMegerosites({ tipus: "visszavonas" })} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:text-text-danger disabled:opacity-50">
                Ajánlatkérés visszavonása
              </button>
            </>
          )}
          {ak.allapot === "dontesre_var" && (
            <>
              <button type="button" disabled={busy} onClick={() => setMegerosites({ tipus: "lezaras" })} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-2 disabled:opacity-50">
                Lezárás nyertes nélkül
              </button>
              <button type="button" disabled={busy} onClick={() => setMegerosites({ tipus: "visszavonas" })} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:text-text-danger disabled:opacity-50">
                Visszavonás
              </button>
            </>
          )}
          {kuldesHibak.length > 0 && ak.allapot !== "piszkozat" && (
            <button type="button" disabled={busy} onClick={() => void hivas(`${BASE}/${ak.id}/ujrakuldes`)} className="rounded-[var(--radius)] border border-text-warning/50 px-3 py-1.5 text-[13px] text-text-warning hover:bg-surface-2 disabled:opacity-50">
              Sikertelen küldések újrapróbálása ({kuldesHibak.length})
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function MunkafelajanlasContent({
  kezdeti,
  employees,
  projektek = [],
  canCreate,
  canEdit,
  canDelete,
}: {
  kezdeti: Ajanlatkeres[];
  employees: Employee[];
  /** A választható projektek (a felhasználó kérése: a projekt a meglévők
   * közül választandó, nem szabad szöveg). */
  projektek?: ProjektOpcio[];
  canCreate: boolean;
  canEdit: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const [lista, setLista] = useState(kezdeti);
  const [nyitott, setNyitott] = useState<number | null>(null);
  const [reszletek, setReszletek] = useState<Record<number, AjanlatkeresReszlet>>({});

  async function frissit() {
    const res = await authFetch(BASE);
    if (res.ok) setLista((await res.json()) as Ajanlatkeres[]);
    router.refresh();
  }

  async function kibont(id: number) {
    if (nyitott === id) {
      setNyitott(null);
      return;
    }
    setNyitott(id);
    const res = await authFetch(`${BASE}/${id}`);
    if (res.ok) {
      const adat = (await res.json()) as AjanlatkeresReszlet;
      setReszletek((elozo) => ({ ...elozo, [id]: adat }));
    }
  }

  function reszletValtozas(id: number, friss: AjanlatkeresReszlet | null) {
    if (friss === null) {
      setLista((elozo) => elozo.filter((x) => x.id !== id));
      setNyitott(null);
      void frissit();
      return;
    }
    setReszletek((elozo) => ({ ...elozo, [id]: friss }));
    setLista((elozo) => elozo.map((x) => (x.id === id ? { ...x, ...friss } : x)));
  }

  return (
    <Card title={`Munkafelajánlások (${lista.length})`}>
      <p className="mb-3 text-[12.5px] text-text-muted">
        Feladat létrehozása → külsősök meghívása → árajánlatok a válaszadási határidőig → belső kiválasztás a
        határidő lejárta után → értesítések. Az árat a meghívott külsősök ajánlják meg; senki nem kapja meg
        automatikusan a munkát.
      </p>
      {canCreate && <UjAjanlatkeres employees={employees} projektek={projektek} onKesz={() => void frissit()} />}
      {lista.length === 0 && <p className="text-[13px] text-text-muted">Még nincs ajánlatkérés.</p>}
      <div className="space-y-2">
        {lista.map((ak) => {
          const cimke = ALLAPOT_CIMKE[ak.allapot] ?? ALLAPOT_CIMKE.piszkozat;
          const resz = reszletek[ak.id];
          return (
            <div key={ak.id} className="rounded-[var(--radius)] border border-border bg-surface-2 p-3">
              <button type="button" onClick={() => void kibont(ak.id)} className="flex w-full flex-wrap items-center gap-2 text-left">
                {nyitott === ak.id ? <ChevronDown size={14} className="shrink-0 text-text-muted" /> : <ChevronRight size={14} className="shrink-0 text-text-muted" />}
                <span className="text-[14px] font-medium text-text-primary">{ak.projekt_nev}</span>
                <span className="text-[13px] text-text-secondary">/ {ak.munkakor}</span>
                <StatusBadge label={cimke.label} tone={cimke.tone} />
                {ak.kuldes_hiba_db > 0 && <StatusBadge label={`${ak.kuldes_hiba_db} küldési hiba`} tone="danger" />}
                <span className="ml-auto text-[12px] text-text-muted">
                  {ak.meghivott_db} meghívott · {ak.ajanlat_db} ajánlat · határidő: {ak.valaszadasi_hatarido_szoveg}
                </span>
              </button>
              {nyitott === ak.id && (
                resz ? (
                  <div className="mt-3">
                    <Reszletek ak={resz} canEdit={canEdit} canDelete={canDelete} onValtozas={(f) => reszletValtozas(ak.id, f)} />
                  </div>
                ) : (
                  <p className="mt-3 text-[12.5px] text-text-muted">Betöltés…</p>
                )
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
