"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { IndoklasDialog } from "@/components/IndoklasDialog";
import { KuldesEllenorzo, type EllenorzoSor } from "@/components/KuldesEllenorzo";
import { formatFt } from "@/lib/ido";
import { SajatPapirFeltoltes } from "@/components/SajatPapirFeltoltes";
import type { PendingSubcontractorProjectCodeEmployee } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

type FormState = {
  ceg_neve: string;
  szekhely: string;
  adoszam: string;
  vallalkozas_kepviseloje: string;
  vallalkozas_nyilvantartasi_szam: string;
  megbizas_targya: string;
  netto_osszeg: string;
  teljesites_szoveg: string;
  keltezes: string;
  plusz_afa: boolean;
};

function formFromEmployee(employee: PendingSubcontractorProjectCodeEmployee): FormState {
  const draft = employee.draft;
  return {
    ceg_neve: draft?.ceg_neve ?? employee.ceg_neve ?? "",
    szekhely: draft?.szekhely ?? employee.szekhely ?? "",
    adoszam: draft?.adoszam ?? employee.adoszam ?? "",
    vallalkozas_kepviseloje: draft?.vallalkozas_kepviseloje ?? employee.kepviselo ?? "",
    vallalkozas_nyilvantartasi_szam: draft?.vallalkozas_nyilvantartasi_szam ?? employee.nyilvantartasi_szam ?? "",
    megbizas_targya: draft?.megbizas_targya ?? employee.megbizas_targya ?? "",
    netto_osszeg: draft?.netto_osszeg != null ? String(draft.netto_osszeg) : "",
    teljesites_szoveg: draft?.teljesites_szoveg ?? "",
    keltezes: draft?.keltezes ?? "",
    plusz_afa: draft?.plusz_afa ?? employee.plusz_afa ?? false,
  };
}

function computeBrutto(nettoOsszeg: string, pluszAfa: boolean): number | null {
  if (!nettoOsszeg.trim()) return null;
  const netto = Number(nettoOsszeg);
  if (Number.isNaN(netto)) return null;
  return pluszAfa ? Math.round(netto * 1.27 * 100) / 100 : netto;
}

/** Ugyanaz, mint a SubcontractorContractManager (forgatáshoz kötött eseti
 * szerződés), csak a PROJEKTKÓDHOZ kötve, forgatás nélkül - tisztán
 * ügynökségi feladatnál (pl. tanácsadás) használt alvállalkozók szerződése.
 *
 * Egyszerűbb a forgatás-alapú változatnál: nincs tétel-választó (egy
 * projektkódon nem kombinálható több nap egy papírra - lásd backend
 * subcontractor_contracts.py "projektkód-szintű ág" fejléce), és nincs
 * "Van már kész szerződése" gomb sem. */
export function SubcontractorContractManagerProjektkod({
  projectCodeId,
  pending,
}: {
  projectCodeId: number;
  pending: PendingSubcontractorProjectCodeEmployee[];
}) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string>("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState<"save" | "send" | "skip" | null>(null);
  const [kihagyasNyitva, setKihagyasNyitva] = useState(false);
  const [kuldesNyitva, setKuldesNyitva] = useState(false);

  const selectedEmployee = pending.find((p) => p.szamlazo === openId) ?? null;
  const bruttoOsszeg = form ? computeBrutto(form.netto_osszeg, form.plusz_afa) : null;
  const alap = `/api/v1/alvallalkozoi-szerzodesek/projektkodok/${projectCodeId}`;

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
      vallalkozas_kepviseloje: form.vallalkozas_kepviseloje || null,
      vallalkozas_nyilvantartasi_szam: form.vallalkozas_nyilvantartasi_szam || null,
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
      { cimke: "Képviselő", ertek: form.vallalkozas_kepviseloje },
      { cimke: "Székhely", ertek: form.szekhely },
      { cimke: "Adószám", ertek: form.adoszam },
      { cimke: "Nyilvántartási szám", ertek: form.vallalkozas_nyilvantartasi_szam },
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

  const busyState = busy !== null;

  return (
    <div>
      <p className="mb-3 text-[13px] text-text-secondary">
        {pending.length === 0
          ? "Nincs olyan alvállalkozó ezen a projektkódon, akinek szerződést kellene készíteni."
          : `${pending.length} alvállalkozónak kell szerződés ezen a projektkódon (nincs hozzá forgatás).`}
      </p>
      {pending.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Alvállalkozó</label>
            <KeresosSelect
              value={selectedId || null}
              options={pending.map((p) => ({
                value: p.szamlazo,
                label: `${p.full_name}${p.draft ? ` (${p.draft.szerzodes_allapota ?? "Készítés alatt"})` : ""}`,
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
            Szerződés készítése
          </button>
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
              Megbízási szerződés – {selectedEmployee.full_name}
            </h3>
            <p className="mb-4 text-[12px] text-text-muted">
              Szerződés állapot: {selectedEmployee.draft?.szerzodes_allapota ?? "Nincs elkezdve"}
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Nyilvántartási szám">
                <input
                  value={form.vallalkozas_nyilvantartasi_szam}
                  onChange={(e) => update("vallalkozas_nyilvantartasi_szam", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
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
              <Field label="Képviselő">
                <input
                  value={form.vallalkozas_kepviseloje}
                  onChange={(e) => update("vallalkozas_kepviseloje", e.target.value)}
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
                {busy === "skip" ? "Kihagyás…" : "Kihagyás (szerződés nélkül)"}
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
                cimke="Saját szerződés feltöltése"
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
          cim="Megbízási szerződés kiküldése"
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
          cim={`${selectedEmployee?.full_name ?? "A megbízott"} kihagyása`}
          leiras="A projektkód szerződés nélkül zárul vele. Írd le, miért - fél év múlva ebből fog kiderülni, hogy szándékos volt."
          onMegse={() => setKihagyasNyitva(false)}
          mezoCimke="A kihagyás oka"
          placeholder="Pl. a munkát a partnercég számlázza, nálunk nincs vele szerződés"
          gombCimke="Kihagyás"
          onKesz={handleSkip}
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
