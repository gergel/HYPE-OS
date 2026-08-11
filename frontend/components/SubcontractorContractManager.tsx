"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import { KihagyasDialog } from "@/components/KihagyasDialog";
import { PapirTetelValaszto, tetelKulcs, type PapirTetel } from "@/components/PapirTetelValaszto";
import { SajatPapirFeltoltes } from "@/components/SajatPapirFeltoltes";
import type { PendingSubcontractorEmployee } from "@/lib/api";
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
  // A kiválasztás SZÁMLÁZÓ FÉL szerint megy ("e12" / "v3"), nem ember szerint:
  // egy szerződés több stábtag munkáját is fedheti (lásd backend
  // services/szamlazo.py).
  const [selectedId, setSelectedId] = useState<string>("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState<"save" | "send" | "skip" | "marvan" | null>(null);
  const [kihagyasNyitva, setKihagyasNyitva] = useState(false);

  // A szerződés TÉTELEI: mire szól a papír. Alapból a projekten hozzá tartozó
  // stábtagok, de más projektek nyitott munkái is rátehetők - így három nap
  // forgatásról egy szerződés köthető, az összevont TIG mellé.
  const [valaszthato, setValaszthato] = useState<PapirTetel[]>([]);
  const [kivalasztott, setKivalasztott] = useState<Set<string>>(new Set());
  const [osszegek, setOsszegek] = useState<Record<string, string>>({});
  const [tetelekToltodnek, setTetelekToltodnek] = useState(false);

  const selectedEmployee = pending.find((p) => p.szamlazo === openId) ?? null;
  const bruttoOsszeg = form ? computeBrutto(form.netto_osszeg, form.plusz_afa) : null;

  // A nyitott tételeket a fél kiválasztásakor kérjük le - más projektek
  // munkái csak a szerveren láthatók (lásd backend list_nyitott_tetelek).
  useEffect(() => {
    if (!selectedEmployee) return;
    let ervenyes = true;
    setTetelekToltodnek(true);
    authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.szamlazo}/nyitott-tetelek`)
      .then((res) => (res.ok ? res.json() : []))
      .then((nyitott: PapirTetel[]) => {
        if (!ervenyes) return;
        const mar = selectedEmployee.draft?.tetelek ?? selectedEmployee.lefedettek;
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

  function billen(kulcs: string) {
    setKivalasztott((elozo) => {
      const uj = new Set(elozo);
      if (uj.has(kulcs)) uj.delete(kulcs);
      else uj.add(kulcs);
      return uj;
    });
  }

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

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function buildPayload() {
    if (!form) return null;
    const netto = form.netto_osszeg.trim() ? Number(form.netto_osszeg) : null;
    // A tétel-összeg elhagyható: összevont szerződésnél nem mindig tudható,
    // melyik nap mennyibe került. A szerződés fejösszege az igazság.
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
      vallalkozas_kepviseloje: form.vallalkozas_kepviseloje || null,
      vallalkozas_nyilvantartasi_szam: form.vallalkozas_nyilvantartasi_szam || null,
      megbizas_targya: form.megbizas_targya || null,
      netto_osszeg: netto,
      teljesites_szoveg: form.teljesites_szoveg || null,
      keltezes: form.keltezes || null,
      plusz_afa: form.plusz_afa,
    };
  }

  /** Az űrlap mentése - a saját szerződés feltöltése előtt is ez fut le, hogy
   * a beírt adatok (összeg, tételek) a feltöltött papír mellett legyenek. */
  async function mentes(): Promise<boolean> {
    if (!selectedEmployee || !form) return false;
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.szamlazo}/save`, {
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
        `/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.szamlazo}/generate-and-send`,
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

  /** Kihagyás - az indoklás kötelező, ezért felugró ablakban kérjük be
   * (lásd KihagyasDialog), nem sima igen/nem megerősítéssel. */
  async function handleSkip(indok: string) {
    if (!selectedEmployee) return;
    setKihagyasNyitva(false);
    setBusy("skip");
    try {
      const res = await authFetch(`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.szamlazo}/skip`, {
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

  /** "Van már kész szerződése" - a fél lekerül a listáról, de NEM
   * kihagyottként. A Notionból áthozott embereknél gyakori: van érvényes,
   * aláírt papír, a rendszer mégis kérné. Itt nincs indoklás-kényszer, mert
   * maga az állapot megmondja, mi történt. */
  async function handleMarVan() {
    if (!selectedEmployee) return;
    if (
      !(await confirm(
        `${selectedEmployee.full_name}: van már kész szerződése, ezért lekerül a listáról. Nem kihagyottként fog szerepelni, hanem "${"Van már szerződés"}" állapotban, és a TIG-je is elkészíthető lesz.`,
      ))
    )
      return;
    setBusy("marvan");
    try {
      const res = await authFetch(
        `/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.szamlazo}/mar-van`,
        { method: "POST", body: JSON.stringify({}) },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      setSelectedId("");
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  const busyState = busy !== null;

  return (
    <div>
      <p className="mb-3 text-[13px] text-text-secondary">
        {pending.length === 0
          ? "Nincs olyan fél a projekten, akinek szerződést kellene készíteni."
          : `${pending.length} félnek kell szerződés (nincs keretszerződése és nem belsős). Ha valaki más nevében számláz, egy szerződés fedi mindkettőjük munkáját.`}
      </p>
      {pending.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Számlázó fél</label>
            <KeresosSelect
              value={selectedId || null}
              options={pending.map((p) => ({
                value: p.szamlazo,
                // A piszkozat állapota a címke része, mint a korábbi natív
                // listában - enélkül nem látszana, kinél van már félkész papír.
                label: `${p.cimke}${p.draft ? ` (${p.draft.szerzodes_allapota ?? "Készítés alatt"})` : ""}`,
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busyState ? undefined : closeForm}>
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">Megbízási szerződés – {selectedEmployee.full_name}</h3>
            <p className="mb-1 text-[12px] text-text-muted">
              Szerződés állapot: {selectedEmployee.draft?.szerzodes_allapota ?? "Nincs elkezdve"}
            </p>
            {/* Ha a fél más(ok) munkáját is számlázza, ez az EGY szerződés fedi
                mindet - a lefedettek attól még teljes értékű stábtagok. */}
            {selectedEmployee.lefedettek.length > 1 && (
              <p className="mb-4 text-[12px] text-text-secondary">
                Ez a szerződés {selectedEmployee.lefedettek.map((l) => l.employee_nev ?? `#${l.employee_id}`).join(", ")}{" "}
                munkáját fedi.
              </p>
            )}
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

            <PapirTetelValaszto
              tetelek={valaszthato}
              kivalasztott={kivalasztott}
              osszegek={osszegek}
              toltodik={tetelekToltodnek}
              tiltva={busyState}
              onBillen={billen}
              onOsszeg={(kulcs, ertek) => setOsszegek((elozo) => ({ ...elozo, [kulcs]: ertek }))}
              fejOsszeg={form.netto_osszeg}
              cim="Mire szól ez a szerződés?"
              leiras="Pipáld ki, kinek a munkájára szól ez az egy szerződés. Más projekt munkája is rátehető – így három nap forgatásról egy szerződés köthető, az összevont TIG mellé. A tételenkénti összeg elhagyható."
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
                onClick={() => setKihagyasNyitva(true)}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busy === "skip" ? "Kihagyás…" : "Kihagyás (szerződés nélkül)"}
              </button>
              <button
                type="button"
                onClick={handleMarVan}
                disabled={busyState}
                title="A papír létezik, csak nem itt készült - nem kihagyásként kerül rá a jelölés"
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busy === "marvan" ? "Mentés…" : "Van már kész szerződése"}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busy === "save" ? "Mentés…" : "Mentés"}
              </button>
              {/* A kiküldés kihagyása: kész szerződés feltöltése. A bejegyzés
                  ugyanúgy "Kiküldve" lesz, tehát mehet tovább a TIG-fázisba. */}
              <SajatPapirFeltoltes
                cimke="Saját szerződés feltöltése"
                feltoltesPath={`/api/v1/alvallalkozoi-szerzodesek/${projectId}/${selectedEmployee.szamlazo}/sajat-fajl`}
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
      {kihagyasNyitva && (
      <KihagyasDialog
        cim={`${selectedEmployee?.full_name ?? "A megbízott"} kihagyása`}
        leiras="A projekt szerződés nélkül zárul vele. Írd le, miért - fél év múlva ebből fog kiderülni, hogy szándékos volt."
        onMegse={() => setKihagyasNyitva(false)}
        onKihagy={handleSkip}
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
