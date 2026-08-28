"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { IndoklasDialog } from "@/components/IndoklasDialog";
import { KuldesEllenorzo, type EllenorzoSor } from "@/components/KuldesEllenorzo";
import { formatFt } from "@/lib/ido";
import { SajatPapirFeltoltes } from "@/components/SajatPapirFeltoltes";
import type { PendingTigProjectCodeEmployee } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

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

function formFromEmployee(employee: PendingTigProjectCodeEmployee): FormState {
  const draft = employee.draft;
  const sz = employee.szerzodes;
  const ures = (ertek: string | null | undefined) => (ertek?.trim() ? ertek : null);
  return {
    ceg_neve: draft?.ceg_neve ?? ures(sz?.ceg_neve) ?? employee.ceg_neve ?? "",
    szekhely: draft?.szekhely ?? ures(sz?.szekhely) ?? employee.szekhely ?? "",
    adoszam: draft?.adoszam ?? ures(sz?.adoszam) ?? employee.adoszam ?? "",
    megbizas_targya: draft?.megbizas_targya ?? ures(sz?.megbizas_targya) ?? employee.megbizas_targya ?? "",
    netto_osszeg:
      draft?.netto_osszeg != null ? String(draft.netto_osszeg) : sz?.netto_osszeg != null ? String(sz.netto_osszeg) : "",
    teljesites_szoveg: draft?.teljesites_szoveg ?? ures(sz?.teljesites_szoveg) ?? "",
    keltezes: draft?.keltezes ?? "",
    plusz_afa: draft?.plusz_afa ?? sz?.plusz_afa ?? employee.plusz_afa ?? false,
  };
}

function computeBrutto(nettoOsszeg: string, pluszAfa: boolean): number | null {
  if (!nettoOsszeg.trim()) return null;
  const netto = Number(nettoOsszeg);
  if (Number.isNaN(netto)) return null;
  return pluszAfa ? Math.round(netto * 1.27 * 100) / 100 : netto;
}

/** Ugyanaz, mint a PerformanceCertificateManager (forgatáshoz kötött TIG),
 * csak a PROJEKTKÓDHOZ kötve, forgatás nélkül - lásd
 * SubcontractorContractManagerProjektkod (a szerződés-oldali megfelelője) és
 * backend performance_certificates.py "projektkód-szintű ág".
 *
 * A `szerzodesreVaro` azok, akiknek a szerződése még nincs meg - róluk TIG
 * nem készíthető, de KIHAGYNI már most is lehet őket. */
export function PerformanceCertificateManagerProjektkod({
  projectCodeId,
  pending,
  szerzodesreVaro = [],
}: {
  projectCodeId: number;
  pending: PendingTigProjectCodeEmployee[];
  szerzodesreVaro?: PendingTigProjectCodeEmployee[];
}) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string>("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState<"save" | "send" | "skip" | null>(null);
  const [kihagyasNyitva, setKihagyasNyitva] = useState(false);
  const [kuldesNyitva, setKuldesNyitva] = useState(false);
  const [varoKihagyas, setVaroKihagyas] = useState<PendingTigProjectCodeEmployee | null>(null);
  const [varoBusy, setVaroBusy] = useState<string | null>(null);

  const selectedEmployee = pending.find((p) => p.szamlazo === openId) ?? null;
  const bruttoOsszeg = form ? computeBrutto(form.netto_osszeg, form.plusz_afa) : null;
  const alap = `/api/v1/teljesitesi-igazolasok/projektkodok/${projectCodeId}`;

  function openForm() {
    if (!selectedId) return;
    const employee = pending.find((p) => p.szamlazo === selectedId);
    if (!employee) return;
    setForm(formFromEmployee(employee));
    setOpenId(employee.szamlazo);
  }

  function closeForm() {
    setOpenId(null);
    setForm(null);
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function buildPayload() {
    if (!form) return null;
    const netto = form.netto_osszeg.trim() ? Number(form.netto_osszeg) : null;
    return {
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

  async function mentes(): Promise<boolean> {
    if (!selectedEmployee || !form) return false;
    try {
      const res = await authFetch(`${alap}/${selectedEmployee.szamlazo}/save`, {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return false;
      }
      return true;
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
      return false;
    }
  }

  async function handleSave() {
    setBusy("save");
    try {
      if (!(await mentes())) return;
      closeForm();
      router.refresh();
    } finally {
      setBusy(null);
    }
  }

  function kuldesInditasa() {
    if (!selectedEmployee || !form) return;
    if (!form.netto_osszeg.trim() || Number.isNaN(Number(form.netto_osszeg)) || Number(form.netto_osszeg) <= 0) {
      alert("Add meg a nettó összeget.");
      return;
    }
    setKuldesNyitva(true);
  }

  function ellenorzoSorok(): EllenorzoSor[] {
    if (!form) return [];
    const netto = form.netto_osszeg.trim() ? Number(form.netto_osszeg) : null;
    return [
      { cimke: "Cég neve", ertek: form.ceg_neve },
      { cimke: "Székhely", ertek: form.szekhely },
      { cimke: "Adószám", ertek: form.adoszam },
      { cimke: "Megbízás tárgya", ertek: form.megbizas_targya },
      {
        cimke: "Nettó összeg",
        ertek: netto === null ? null : `${formatFt(netto)}${form.plusz_afa ? " + ÁFA" : ""}`,
      },
      { cimke: "Teljesítés ideje", ertek: form.teljesites_szoveg },
      { cimke: "Keltezés", ertek: form.keltezes },
    ];
  }

  async function handleGenerateAndSend() {
    if (!selectedEmployee || !form) return;
    setKuldesNyitva(false);
    setBusy("send");
    try {
      const res = await authFetch(`${alap}/${selectedEmployee.szamlazo}/generate-and-send`, {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });
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

  async function handleSkip(indok: string) {
    if (!selectedEmployee) return;
    setKihagyasNyitva(false);
    setBusy("skip");
    try {
      const res = await authFetch(`${alap}/${selectedEmployee.szamlazo}/skip`, {
        method: "POST",
        body: JSON.stringify({ kihagyas_oka: indok }),
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

  async function handleVaroKihagyas(indok: string) {
    if (!varoKihagyas) return;
    setVaroBusy(varoKihagyas.szamlazo);
    try {
      const res = await authFetch(`${alap}/${varoKihagyas.szamlazo}/skip`, {
        method: "POST",
        body: JSON.stringify({ kihagyas_oka: indok }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen kihagyás: ${detail?.detail ?? res.status}`);
        return;
      }
      setVaroKihagyas(null);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen kihagyás (hálózati hiba): ${err}`);
    } finally {
      setVaroBusy(null);
    }
  }

  const busyState = busy !== null;

  return (
    <div>
      <p className="mb-3 text-[13px] text-text-secondary">
        {pending.length === 0
          ? "Nincs olyan alvállalkozó, akiről most készíthető TIG ezen a projektkódon."
          : `${pending.length} alvállalkozóról készíthető TIG ezen a projektkódon.`}
      </p>
      {pending.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Alvállalkozó</label>
            <KeresosSelect
              value={selectedId || null}
              options={pending.map((p) => ({
                value: p.szamlazo,
                label: `${p.full_name}${p.draft ? ` (${p.draft.allapot ?? "Készítés alatt"})` : ""}`,
              }))}
              onChange={setSelectedId}
              placeholder="Válassz embert…"
              className="min-w-[220px]"
            />
          </div>
          <button
            type="button"
            onClick={openForm}
            disabled={!selectedId}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            TIG készítése
          </button>
        </div>
      )}

      {/* Akiknek még nincs meg a szerződése - róluk TIG nem készíthető, de
          kihagyni már most is lehet őket (a két lépés egymástól független). */}
      {szerzodesreVaro.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <p className="mb-2 text-[12.5px] text-text-muted">
            Még nincs meg a szerződésük - róluk egyelőre csak a TIG kihagyása lehetséges:
          </p>
          <ul className="space-y-1.5">
            {szerzodesreVaro.map((p) => (
              <li key={p.szamlazo} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                <span className="text-text-secondary">{p.full_name}</span>
                <button
                  type="button"
                  onClick={() => setVaroKihagyas(p)}
                  disabled={varoBusy === p.szamlazo}
                  className="text-[12px] text-text-muted hover:text-text-primary disabled:opacity-50"
                >
                  TIG kihagyása
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {selectedEmployee && form && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6"
          onClick={busyState ? undefined : closeForm}
        >
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">
              Teljesítési igazolás – {selectedEmployee.full_name}
            </h3>
            <p className="mb-4 text-[12px] text-text-muted">TIG állapot: {selectedEmployee.draft?.allapot ?? "Nincs elkezdve"}</p>
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
              <Field label="Teljesítés ideje">
                <input
                  value={form.teljesites_szoveg}
                  onChange={(e) => update("teljesites_szoveg", e.target.value)}
                  disabled={busyState}
                  placeholder="Pl. 2026. július"
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
                onClick={() => setKihagyasNyitva(true)}
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
              <SajatPapirFeltoltes
                cimke="Saját TIG feltöltése"
                feltoltesPath={`${alap}/${selectedEmployee.szamlazo}/sajat-fajl`}
                elokeszit={mentes}
                disabled={busyState}
                onKesz={() => {
                  closeForm();
                  setSelectedId("");
                  router.refresh();
                }}
              />
              <button
                type="button"
                onClick={kuldesInditasa}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busy === "send" ? "Küldés…" : "Generálás és küldés"}
              </button>
            </div>
          </div>
        </div>
      )}
      {kuldesNyitva && selectedEmployee && (
        <KuldesEllenorzo
          cim="Teljesítési igazolás kiküldése"
          bevezeto="A dokumentum ezekkel az adatokkal generálódik, és azonnal ki is megy e-mailben."
          cimzett={selectedEmployee.email}
          sorok={ellenorzoSorok()}
          tetelek={[]}
          gombCimke="Generálás és küldés"
          onMegse={() => setKuldesNyitva(false)}
          onKuld={handleGenerateAndSend}
        />
      )}
      {kihagyasNyitva && (
        <IndoklasDialog
          cim={`${selectedEmployee?.full_name ?? "A megbízott"} TIG-jének kihagyása`}
          leiras="A projektkód TIG nélkül zárul vele. Írd le, miért - fél év múlva ebből fog kiderülni, hogy szándékos volt."
          onMegse={() => setKihagyasNyitva(false)}
          mezoCimke="A kihagyás oka"
          placeholder="Pl. a munkát a partnercég számlázza, nálunk nincs vele TIG"
          gombCimke="Kihagyás"
          onKesz={handleSkip}
        />
      )}
      {varoKihagyas && (
        <IndoklasDialog
          cim={`${varoKihagyas.full_name} TIG-jének kihagyása`}
          leiras="A projektkód TIG nélkül zárul vele. Írd le, miért - fél év múlva ebből fog kiderülni, hogy szándékos volt."
          onMegse={() => setVaroKihagyas(null)}
          mezoCimke="A kihagyás oka"
          placeholder="Pl. a munkát a partnercég számlázza, nálunk nincs vele TIG"
          gombCimke="Kihagyás"
          onKesz={handleVaroKihagyas}
        />
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
