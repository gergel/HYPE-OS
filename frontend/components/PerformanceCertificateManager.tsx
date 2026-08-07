"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import type { PendingTigEmployee, TigTetel } from "@/lib/api";

/** Egy tétel azonosítója a felületen: melyik ember melyik projekten végzett
 * munkája. Ez a TIG-tétel kulcsa (lásd backend
 * models/performance_certificate.py PerformanceCertificateTetel). */
function tetelKulcs(t: { project_id: number; employee_id: number }): string {
  return `${t.project_id}:${t.employee_id}`;
}

type FormState = {
  ceg_neve: string;
  szekhely: string;
  adoszam: string;
  megbizas_targya: string;
  netto_osszeg: string;
  teljesites_szoveg: string;
  keltezes: string;
  plusz_afa: boolean;
};

/** `teljesitesAlap`: a projekt forgatási dátumából képzett alapértelmezett
 * szöveg - az űrlap ezzel indul, amíg nincs mentett bejegyzés (az akkor még
 * nem is létezik, tehát nem lenne miből előtölteni). */
function formFromEmployee(employee: PendingTigEmployee, teljesitesAlap: string): FormState {
  const draft = employee.draft;
  return {
    ceg_neve: draft?.ceg_neve ?? employee.ceg_neve ?? "",
    szekhely: draft?.szekhely ?? employee.szekhely ?? "",
    adoszam: draft?.adoszam ?? employee.adoszam ?? "",
    megbizas_targya: draft?.megbizas_targya ?? employee.megbizas_targya ?? "",
    netto_osszeg: draft?.netto_osszeg != null ? String(draft.netto_osszeg) : "",
    teljesites_szoveg: draft?.teljesites_szoveg ?? teljesitesAlap,
    keltezes: draft?.keltezes ?? "",
    plusz_afa: draft?.plusz_afa ?? employee.plusz_afa ?? false,
  };
}

/** Bruttó = nettó * 1,27, ha a megbízottnak plusz ÁFA-t kell felszámolni,
 * egyébként megegyezik a nettóval. */
function computeBrutto(nettoOsszeg: string, pluszAfa: boolean): number | null {
  if (!nettoOsszeg.trim()) return null;
  const netto = Number(nettoOsszeg);
  if (Number.isNaN(netto)) return null;
  return pluszAfa ? Math.round(netto * 1.27 * 100) / 100 : netto;
}

/** A projekten résztvevő, még nem kezelt (nem belsős - a keretszerződéseseket
 * IS beleértve) emberek listája + a hozzájuk tartozó teljesítési igazolás
 * kétlépéses (mentés majd generálás-és-küldés, vagy kihagyás) szerkesztő
 * űrlapja. Ugyanaz a mintázat, mint a SubcontractorContractManager-nél, csak
 * kevesebb mezővel (nincs Nyilvántartási szám / Képviselő - ezek nem
 * szerepelnek a TIG sablonban). */
export function PerformanceCertificateManager({
  projectId,
  pending,
  teljesitesAlap = "",
}: {
  projectId: number;
  pending: PendingTigEmployee[];
  /** A teljesítés idejének alapértelmezett szövege (a projekt forgatási
   * dátumából) - lásd backend PendingProjectDetail.teljesites_szoveg_alap. */
  teljesitesAlap?: string;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  // A kiválasztás SZÁMLÁZÓ FÉL szerint megy ("e12" / "v3"): egy TIG több ember
  // munkájáról is szólhat (lásd backend services/szamlazo.py).
  const [selectedId, setSelectedId] = useState<string>("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState<"save" | "send" | "skip" | null>(null);

  // A TIG TÉTELEI: mit igazol ez a papír. Alapból a projekten hozzá tartozó
  // stábtagok, de más projektek nyitott munkái is rátehetők - ez az "egy ember
  // egyben küld be több projektet" eset.
  const [valaszthato, setValaszthato] = useState<TigTetel[]>([]);
  const [kivalasztott, setKivalasztott] = useState<Set<string>>(new Set());
  const [osszegek, setOsszegek] = useState<Record<string, string>>({});
  const [tetelekToltodnek, setTetelekToltodnek] = useState(false);

  const selectedEmployee = pending.find((p) => p.szamlazo === openId) ?? null;
  const bruttoOsszeg = form ? computeBrutto(form.netto_osszeg, form.plusz_afa) : null;

  // A nyitott tételeket a fél kiválasztásakor kérjük le - más projektek
  // munkái csak a szerveren láthatók (lásd getNyitottTigTetelek).
  useEffect(() => {
    if (!selectedEmployee) return;
    let ervenyes = true;
    setTetelekToltodnek(true);
    authFetch(`/api/v1/teljesitesi-igazolasok/${projectId}/${selectedEmployee.szamlazo}/nyitott-tetelek`)
      .then((res) => (res.ok ? res.json() : []))
      .then((nyitott: TigTetel[]) => {
        if (!ervenyes) return;
        const mar = selectedEmployee.draft?.tetelek ?? selectedEmployee.lefedettek;
        // A már rajta lévő tételek nem szerepelnek a "nyitott" listán (nem
        // nyitottak) - ezért kell összefésülni a kettőt.
        const egyben = [...mar];
        for (const t of nyitott) {
          if (!egyben.some((m) => tetelKulcs(m) === tetelKulcs(t))) egyben.push(t);
        }
        setValaszthato(egyben);
        setKivalasztott(new Set(mar.map(tetelKulcs)));
        setOsszegek(
          Object.fromEntries(
            mar.filter((t) => t.netto_osszeg != null).map((t) => [tetelKulcs(t), String(t.netto_osszeg)]),
          ),
        );
      })
      .finally(() => ervenyes && setTetelekToltodnek(false));
    return () => {
      ervenyes = false;
    };
  }, [projectId, selectedEmployee]);

  function openForm() {
    if (!selectedId) return;
    const employee = pending.find((p) => p.szamlazo === selectedId);
    if (!employee) return;
    setForm(formFromEmployee(employee, teljesitesAlap));
    setOpenId(employee.szamlazo);
  }

  function closeForm() {
    setOpenId(null);
    setForm(null);
    setValaszthato([]);
    setKivalasztott(new Set());
    setOsszegek({});
  }

  function billen(kulcs: string) {
    setKivalasztott((elozo) => {
      const uj = new Set(elozo);
      if (uj.has(kulcs)) uj.delete(kulcs);
      else uj.add(kulcs);
      return uj;
    });
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function buildPayload() {
    if (!form) return null;
    const netto = form.netto_osszeg.trim() ? Number(form.netto_osszeg) : null;
    // A tétel-összeg szándékosan elhagyható: összevont számlánál nem mindig
    // tudható, mi mennyibe került. A TIG fejösszege az igazság.
    const tetelek = valaszthato
      .filter((t) => kivalasztott.has(tetelKulcs(t)))
      .map((t) => {
        const nyers = (osszegek[tetelKulcs(t)] ?? "").trim();
        return {
          project_id: t.project_id,
          employee_id: t.employee_id,
          netto_osszeg: nyers && !Number.isNaN(Number(nyers)) ? Number(nyers) : null,
        };
      });
    return {
      tetelek,
      ceg_neve: form.ceg_neve || null,
      szekhely: form.szekhely || null,
      adoszam: form.adoszam || null,
      megbizas_targya: form.megbizas_targya || null,
      netto_osszeg: netto,
      teljesites_szoveg: form.teljesites_szoveg || null,
      keltezes: form.keltezes || null,
      plusz_afa: form.plusz_afa,
    };
  }

  async function handleSave() {
    if (!selectedEmployee || !form) return;
    setBusy("save");
    try {
      const res = await authFetch(`/api/v1/teljesitesi-igazolasok/${projectId}/${selectedEmployee.szamlazo}/save`, {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  async function handleGenerateAndSend() {
    if (!selectedEmployee || !form) return;
    if (!form.netto_osszeg.trim() || Number.isNaN(Number(form.netto_osszeg)) || Number(form.netto_osszeg) <= 0) {
      alert("Add meg a nettó összeget.");
      return;
    }
    if (!(await confirm(`Elküldi a teljesítési igazolást ${selectedEmployee.full_name} email címére?`))) return;
    setBusy("send");
    try {
      const res = await authFetch(
        `/api/v1/teljesitesi-igazolasok/${projectId}/${selectedEmployee.szamlazo}/generate-and-send`,
        { method: "POST", body: JSON.stringify(buildPayload()) },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen küldés: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      setSelectedId("");
      router.refresh();
    } catch (err) {
      alert(`Sikertelen küldés (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  async function handleSkip() {
    if (!selectedEmployee) return;
    if (!(await confirm(`Biztosan kihagyod ${selectedEmployee.full_name}-t? A projekt teljesítési igazolás nélkül zárul vele.`))) return;
    setBusy("skip");
    try {
      const res = await authFetch(`/api/v1/teljesitesi-igazolasok/${projectId}/${selectedEmployee.szamlazo}/skip`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen kihagyás: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      setSelectedId("");
      router.refresh();
    } catch (err) {
      alert(`Sikertelen kihagyás (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  const busyState = busy !== null;

  return (
    <div>
      <p className="mb-3 text-[13px] text-text-secondary">
        {pending.length === 0
          ? "Nincs olyan fél a projekten, akinek teljesítési igazolást kellene készíteni."
          : `${pending.length} félnek kell teljesítési igazolás (nem belsős - a keretszerződéseseket is beleértve). Egy TIG több ember és több projekt munkáját is igazolhatja.`}
      </p>
      {pending.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Számlázó fél</label>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="min-w-[220px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
            >
              <option value="">Válassz embert…</option>
              {pending.map((p) => (
                <option key={p.szamlazo} value={p.szamlazo}>
                  {p.cimke}
                  {p.draft ? ` (${p.draft.allapot ?? "Készítés alatt"})` : ""}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={openForm}
            disabled={!selectedId}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Teljesítési igazolás készítése
          </button>
        </div>
      )}

      {selectedEmployee && form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busyState ? undefined : closeForm}>
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">Teljesítési igazolás – {selectedEmployee.full_name}</h3>
            <p className="mb-4 text-[12px] text-text-muted">
              TIG állapot: {selectedEmployee.draft?.allapot ?? "Nincs elkezdve"}
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Megbízott neve">
                <input
                  value={form.ceg_neve}
                  onChange={(e) => update("ceg_neve", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
              <Field label="Megbízott székhely">
                <input
                  value={form.szekhely}
                  onChange={(e) => update("szekhely", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
              <Field label="Megbízott adószám">
                <input
                  value={form.adoszam}
                  onChange={(e) => update("adoszam", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
              <Field label="Megbízás tárgya">
                <input
                  value={form.megbizas_targya}
                  onChange={(e) => update("megbizas_targya", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
              {/* Szabad szöveg, nem dátum: a papírra nem mindig egy naptári
                  intervallum kerül ("2026. július", felsorolás, stb.). */}
              <Field label="Teljesítés ideje">
                <input
                  value={form.teljesites_szoveg}
                  onChange={(e) => update("teljesites_szoveg", e.target.value)}
                  disabled={busyState}
                  placeholder="Pl. 2026.07.06. - 2026.07.08. vagy 2026. július"
                  className={inputClass}
                />
              </Field>
              <Field label="Nettó összeg (Ft) *">
                <input
                  type="number"
                  value={form.netto_osszeg}
                  onChange={(e) => update("netto_osszeg", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
              <Field label="PLUSZ áfa">
                <label className="flex items-center gap-2 py-1.5 text-[13px] text-text-primary">
                  <input
                    type="checkbox"
                    checked={form.plusz_afa}
                    onChange={(e) => update("plusz_afa", e.target.checked)}
                    disabled={busyState}
                  />
                  {form.plusz_afa ? "Igen" : "Nem"}
                </label>
              </Field>
              <Field label="Bruttó összeg (Ft)">
                <p className="py-1.5 text-[13px] text-text-secondary">
                  {bruttoOsszeg != null ? `${bruttoOsszeg.toLocaleString("hu-HU")} Ft` : "–"}
                </p>
              </Field>
              <Field label="Keltezés dátuma">
                <input
                  type="date"
                  value={form.keltezes}
                  onChange={(e) => update("keltezes", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
            </div>

            <TetelValaszto
              tetelek={valaszthato}
              kivalasztott={kivalasztott}
              osszegek={osszegek}
              toltodik={tetelekToltodnek}
              tiltva={busyState}
              onBillen={billen}
              onOsszeg={(kulcs, ertek) => setOsszegek((elozo) => ({ ...elozo, [kulcs]: ertek }))}
              fejOsszeg={form.netto_osszeg}
            />
            <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={closeForm}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Bezárás
              </button>
              <button
                type="button"
                onClick={handleSkip}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busy === "skip" ? "Kihagyás…" : "Kihagyás (TIG nélkül)"}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busy === "save" ? "Mentés…" : "Mentés"}
              </button>
              <button
                type="button"
                onClick={handleGenerateAndSend}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busy === "send" ? "Küldés…" : "Generálás és küldés"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Mit igazol ez a TIG: kinek a munkáját, melyik projekten.
 *
 * Két dolgot old meg egyszerre:
 * - a projekten belül több ember munkáját (ha valaki más nevében is számláz),
 * - és MÁS projektek munkáit (ha valaki több forgatást egy számlán küld be).
 *
 * A tételenkénti összeg szándékosan elhagyható: összevont számlánál nem mindig
 * tudható, mi mennyibe került. Ha kitöltik, a projekt-jövedelmezőség abból
 * számol; ha nem, a TIG fejösszege marad az egyetlen igazság - egyenlően
 * SOSEM osztjuk szét, mert az kitalált számokat vinne a kimutatásokba. */
function TetelValaszto({
  tetelek,
  kivalasztott,
  osszegek,
  toltodik,
  tiltva,
  onBillen,
  onOsszeg,
  fejOsszeg,
}: {
  tetelek: TigTetel[];
  kivalasztott: Set<string>;
  osszegek: Record<string, string>;
  toltodik: boolean;
  tiltva: boolean;
  onBillen: (kulcs: string) => void;
  onOsszeg: (kulcs: string, ertek: string) => void;
  fejOsszeg: string;
}) {
  if (toltodik) {
    return <p className="mt-4 border-t border-border pt-4 text-[12px] text-text-muted">Tételek betöltése…</p>;
  }
  if (tetelek.length === 0) return null;

  const bontott = tetelek
    .filter((t) => kivalasztott.has(tetelKulcs(t)))
    .map((t) => Number((osszegek[tetelKulcs(t)] ?? "").trim()))
    .filter((n) => !Number.isNaN(n) && n > 0);
  const bontasOsszege = bontott.reduce((a, b) => a + b, 0);
  const fej = Number(fejOsszeg);
  const elter = bontott.length > 0 && !Number.isNaN(fej) && fej > 0 && Math.abs(bontasOsszege - fej) > 0.5;

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="mb-1 text-[13px] font-medium text-text-primary">Mit igazol ez a TIG?</p>
      <p className="mb-3 text-[12px] text-text-muted">
        Pipáld ki, kinek a munkája kerül erre az egy igazolásra. Más projekt munkája is rátehető, ha egy számlán
        érkezik. A tételenkénti összeg elhagyható – ha nem tudható, mi mennyibe került, elég a fenti nettó összeg.
      </p>
      <div className="flex flex-col gap-1.5">
        {tetelek.map((t) => {
          const kulcs = tetelKulcs(t);
          const be = kivalasztott.has(kulcs);
          return (
            <div key={kulcs} className="flex flex-wrap items-center gap-2 text-[13px]">
              <label className="flex min-w-[280px] flex-1 items-center gap-2 text-text-primary">
                <input type="checkbox" checked={be} onChange={() => onBillen(kulcs)} disabled={tiltva} />
                <span>
                  {t.employee_nev ?? `#${t.employee_id}`}
                  <span className="text-text-muted">
                    {" – "}
                    {t.projektkod ? `${t.projektkod} · ` : ""}
                    {t.project_nev ?? `#${t.project_id}`}
                    {t.forgatas_datuma ? ` (${t.forgatas_datuma})` : ""}
                  </span>
                </span>
              </label>
              <input
                type="number"
                value={osszegek[kulcs] ?? ""}
                onChange={(e) => onOsszeg(kulcs, e.target.value)}
                disabled={tiltva || !be}
                placeholder="ebből ennyi az övé (nem kötelező)"
                className="w-[240px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary focus:outline-none disabled:opacity-40"
              />
            </div>
          );
        })}
      </div>
      {elter && (
        <p className="mt-2 text-[12px] text-text-secondary">
          A kitöltött tételek összege {bontasOsszege.toLocaleString("hu-HU")} Ft, a TIG nettó összege{" "}
          {fej.toLocaleString("hu-HU")} Ft. Ez nem hiba – a bontás lehet részleges –, de érdemes ránézni.
        </p>
      )}
    </div>
  );
}

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] text-text-muted">{label}</label>
      {children}
    </div>
  );
}
