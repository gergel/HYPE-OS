"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import type { PendingSubcontractorEmployee } from "@/lib/api";

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

/** `teljesitesAlap`: a projekt forgatási dátumából képzett alapértelmezett
 * teljesítés-szöveg (lásd backend PendingProjectDetail.teljesites_szoveg_alap). */
function formFromEmployee(employee: PendingSubcontractorEmployee, teljesitesAlap: string): FormState {
  const draft = employee.draft;
  return {
    ceg_neve: draft?.ceg_neve ?? employee.ceg_neve ?? "",
    szekhely: draft?.szekhely ?? employee.szekhely ?? "",
    adoszam: draft?.adoszam ?? employee.adoszam ?? "",
    vallalkozas_kepviseloje: draft?.vallalkozas_kepviseloje ?? employee.kepviselo ?? "",
    vallalkozas_nyilvantartasi_szam: draft?.vallalkozas_nyilvantartasi_szam ?? employee.nyilvantartasi_szam ?? "",
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

/** A projekten résztvevő, még nem kezelt (sem belsős, sem keretszerződéses)
 * emberek listája + a hozzájuk tartozó eseti megbízási szerződés kétlépéses
 * (mentés majd generálás-és-küldés, vagy kihagyás) szerkesztő űrlapja. A form
 * mindig a legutóbb mentett draft-ból (vagy - ha még nincs draft - a munkatárs
 * alapadataiból) töltődik elő. */
export function SubcontractorContractManager({
  projectId,
  pending,
  teljesitesAlap = "",
}: {
  projectId: number;
  pending: PendingSubcontractorEmployee[];
  /** A teljesítés idejének előtöltése (a projekt forgatási dátumából) - lásd
   * backend PendingProjectDetail.teljesites_szoveg_alap. */
  teljesitesAlap?: string;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState<"save" | "send" | "skip" | null>(null);

  const selectedEmployee = pending.find((p) => p.id === openId) ?? null;
  const bruttoOsszeg = form ? computeBrutto(form.netto_osszeg, form.plusz_afa) : null;

  function openForm() {
    if (!selectedId) return;
    const employee = pending.find((p) => p.id === selectedId);
    if (!employee) return;
    setForm(formFromEmployee(employee, teljesitesAlap));
    setOpenId(employee.id);
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

  async function handleSave() {
    if (!selectedEmployee || !form) return;
    setBusy("save");
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.id}/save`, {
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
    if (!(await confirm(`Elküldi a megbízási szerződést ${selectedEmployee.full_name} email címére?`))) return;
    setBusy("send");
    try {
      const res = await authFetch(
        `/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.id}/generate-and-send`,
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
    if (!(await confirm(`Biztosan kihagyod ${selectedEmployee.full_name}-t? A projekt szerződés nélkül zárul vele.`))) return;
    setBusy("skip");
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.id}/skip`, {
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
          ? "Nincs olyan ember a projekten, akinek szerződést kellene készíteni."
          : `${pending.length} embernek kell szerződés (nincs keretszerződése és nem belsős).`}
      </p>
      {pending.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Megbízott</label>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : "")}
              className="min-w-[220px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
            >
              <option value="">Válassz embert…</option>
              {pending.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name}
                  {p.draft ? ` (${p.draft.szerzodes_allapota ?? "Készítés alatt"})` : ""}
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
            Szerződés készítése
          </button>
        </div>
      )}

      {selectedEmployee && form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busyState ? undefined : closeForm}>
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">Megbízási szerződés – {selectedEmployee.full_name}</h3>
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
              {/* Szabad szöveg, nem dátumpár: a szerződésre nem mindig egy
                  naptól-napig tartomány kerül ("május 3-5.", "a projekt teljes
                  időtartama") - pontosan az kell megjelenjen, amit ide írnak. */}
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
