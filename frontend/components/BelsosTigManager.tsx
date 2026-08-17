"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { SajatPapirFeltoltes } from "@/components/SajatPapirFeltoltes";
import { SelectDropdown } from "@/components/SelectDropdown";
import { TigAllapotSelect } from "@/components/TigAllapotSelect";
import { huEvHonap, tigHonapTeljesitesbol } from "@/lib/huDate";
import { formatHuf } from "@/lib/penz";
import type { BelsosTigMonthEmployee } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";
import { KuldesEllenorzo, type EllenorzoSor } from "@/components/KuldesEllenorzo";
import { KifizetesJeloloDialog } from "@/components/KifizetesJeloloDialog";

type FormState = {
  /** Melyik saját cégéről számlázza ezt a hónapot. Üres = a saját nevében. */
  vallalkozas_id: string;
  netto_osszeg: string;
  plusz_afa: boolean;
  megjegyzes: string;
  megbizas_targya: string;
  teljesites_datuma: string;
  keltezes: string;
};

/** A bejelentett alkalmazott havi fizetése - nála ez a TIG-űrlap helyett áll,
 * mert nincs TIG, nincs számla és nincs kifizetés-jelölés. */
type FizetesForm = {
  /** Ami az emberhez tartozik ("mennyi a fizetése") = a hónap alapbér tétele. */
  netto_ber: string;
};

/** A hónapot követő hónap első napja - ez az alapértelmezett teljesítési
 * dátum, mert a teljesítés MINDIG a lefedett hónap utáni hónapban történik
 * (ebből számolja vissza a rendszer, melyik hónapé a TIG). */
function alapTeljesitesDatum(ev: number, honap: number): string {
  const kovEv = honap === 12 ? ev + 1 : ev;
  const kovHonap = honap === 12 ? 1 : honap + 1;
  return `${kovEv}-${String(kovHonap).padStart(2, "0")}-01`;
}

/** A megbízás tárgya és az áfa-jelölés a munkatárs adatlapjáról jön - de csak
 * amíg a hónap bejegyzésének nincs saját (esetleg átírt) értéke. Az első
 * megnyitáskor még egyáltalán nincs bejegyzés, ezért kell a személy adata is
 * (lásd backend MonthEmployeeInfo). */
function formFromRecord(employee: BelsosTigMonthEmployee, ev: number, honap: number): FormState {
  const record = employee.record;
  return {
    // Ha még nincs kézzel választva, a hónapra érvényes cégével indulunk (lásd
    // backend _ceg_valasztek) - így nem kell minden hónapban újra beállítani.
    vallalkozas_id: String(record?.vallalkozas_id ?? employee.javasolt_vallalkozas_id ?? ""),
    netto_osszeg: record?.netto_osszeg != null ? String(record.netto_osszeg) : "",
    plusz_afa: record?.plusz_afa ?? employee.plusz_afa ?? false,
    megjegyzes: record?.megjegyzes ?? "",
    megbizas_targya: record?.megbizas_targya ?? employee.megbizas_targya ?? "",
    teljesites_datuma: record?.teljesites_datuma ?? alapTeljesitesDatum(ev, honap),
    keltezes: record?.keltezes ?? "",
  };
}

function computeBrutto(nettoOsszeg: string, pluszAfa: boolean): number | null {
  if (!nettoOsszeg.trim()) return null;
  const netto = Number(nettoOsszeg);
  if (Number.isNaN(netto)) return null;
  return pluszAfa ? Math.round(netto * 1.27 * 100) / 100 : netto;
}

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

/** Az állapot-szűrő "nincs szűrés" értéke. */
const MIND = "Összes állapot";

/** Akinek még nincs bejegyzése arra a hónapra, annak nincs is állapota - a
 * szűrőben mégis ez a legfontosabb csoport ("kivel van még teendő"), ezért
 * saját, nevesített értéket kap. */
const NINCS_ELKEZDVE = "Nincs elkezdve";

const ALLAPOT_SZURO_OPCIOK = [MIND, NINCS_ELKEZDVE, "Készítés alatt", "Kiküldve", "Kész", "Kihagyva"];

/** Belsős TIG - havi admin oldal (lásd app/(app)/belsos-tig/page.tsx), ami az
 * adott hónap (alapértelmezetten a folyó hónap) összes belsős munkatársát
 * felsorolja, egy sorban mindegyiket. Ellentétben a Külsős TIG-gel, ez NEM
 * projektenkénti - egy embernek egy hónapban pontosan egy TIG-je van, amit
 * itt admin rögzít (összeg, majd "Kész"), vagy kihagy ("Kihagyva", ha az
 * illető épp nem dolgozott azon a hónapon). "Kész" után jöhet a számla
 * feltöltése és kifizetettként jelölése, ami létrehozza a Pénzügy ->
 * Kiadások-ban megjelenő Expense sort (lásd backend
 * internal_performance_certificates.py /szamla és /szamla-kifizetve). */
export function BelsosTigManager({
  ev,
  honap,
  employees,
  canEdit = true,
}: {
  ev: number;
  honap: number;
  employees: BelsosTigMonthEmployee[];
  /** Az állapot kézi átállítása szerkesztési jogot igényel - enélkül sima
   * címkeként jelenik meg (lásd TigAllapotSelect). */
  canEdit?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [openId, setOpenId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  // A fizetés-űrlap szándékosan külön állapot, nem a TIG-űrlap egy módja: más
  // mezői vannak, más végpontra megy, és a kettő sosem nyílik meg egyszerre.
  const [fizetesId, setFizetesId] = useState<number | null>(null);
  const [fizetesForm, setFizetesForm] = useState<FizetesForm | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [allapotSzuro, setAllapotSzuro] = useState(MIND);
  // Kiküldés előtti áttekintő: a TIG generálása egy Google Docs sablon
  // kitöltése + azonnali e-mail, tehát ami egyszer kiment, azt már csak új
  // papírral lehet javítani (lásd KuldesEllenorzo).
  const [ellenorzoNyitva, setEllenorzoNyitva] = useState(false);
  // Kinek a hónapját jelöljük épp kifizetettnek - a "kerüljön-e Kiadás sorba"
  // döntés miatt nem elég egy igen/nem megerősítés.
  const [kifizetendoId, setKifizetendoId] = useState<number | null>(null);

  const openEmployee = employees.find((e) => e.id === openId) ?? null;
  const fizetesEmployee = employees.find((e) => e.id === fizetesId) ?? null;
  const kifizetendoEmployee = employees.find((e) => e.id === kifizetendoId) ?? null;
  const bruttoOsszeg = form ? computeBrutto(form.netto_osszeg, form.plusz_afa) : null;
  // A teljesítés dátuma dönti el, melyik hónapé a TIG (mindig az azt megelőző
  // hónap) - ha az admin olyat ír be, ami másik hónapra mutat, ezt előre
  // jelezzük, mert a bejegyzés át fog kerülni oda.
  const celHonap = form?.teljesites_datuma ? tigHonapTeljesitesbol(form.teljesites_datuma) : null;
  const celHonapEltero = !!celHonap && (celHonap.ev !== ev || celHonap.honap !== honap);

  function openForm(employee: BelsosTigMonthEmployee) {
    setForm(formFromRecord(employee, ev, honap));
    setOpenId(employee.id);
  }

  function closeForm() {
    setOpenId(null);
    setForm(null);
    setEllenorzoNyitva(false);
  }

  /** PONTOSAN azok a mezők, amiket a backend a sablonba behelyettesít (lásd
   * internal_performance_certificates.generate_and_send `fields`) - ha itt
   * bármi üresen marad, ott is üres hely lesz a kiküldött PDF-en.
   *
   * A cég adatai a választott cégről jönnek, saját névben számlázásnál pedig a
   * munkatárs adatlapjáról - ugyanaz a "cég vagy ember" elágazás, mint a
   * backendben. */
  function ellenorzoSorok(): EllenorzoSor[] {
    if (!openEmployee || !form) return [];
    const ceg = openEmployee.cegek.find((c) => String(c.vallalkozas_id) === form.vallalkozas_id) ?? null;
    const honapCel = form.teljesites_datuma ? tigHonapTeljesitesbol(form.teljesites_datuma) : null;
    return [
      { cimke: "Név a papíron", ertek: ceg ? ceg.nev : openEmployee.full_name },
      { cimke: "Székhely", ertek: ceg ? ceg.szekhely : openEmployee.szekhely },
      { cimke: "Adószám", ertek: ceg ? ceg.adoszam : openEmployee.adoszam },
      { cimke: "Megbízás tárgya", ertek: form.megbizas_targya },
      { cimke: "Melyik hónapról szól", ertek: honapCel ? huEvHonap(honapCel.ev, honapCel.honap) : null },
      {
        cimke: "Nettó összeg",
        ertek: form.netto_osszeg.trim() ? `${formatHuf(Number(form.netto_osszeg))}${form.plusz_afa ? " + ÁFA" : ""}` : null,
      },
      { cimke: "Bruttó összeg", ertek: bruttoOsszeg != null ? formatHuf(bruttoOsszeg) : null },
      // Üresen a backend a kiküldés napját írja rá - itt is azt mutatjuk, hogy
      // ne "hiányzó adatnak" látszódjon, ami valójában automatikus.
      { cimke: "Keltezés", ertek: form.keltezes || new Date().toISOString().slice(0, 10) },
    ];
  }

  /** A fizetés-űrlap a hónap MEGLÉVŐ nettó bérével nyílik: az a hónap alapbér
   * tétele, azt írja felül a mentés. */
  function openFizetes(employee: BelsosTigMonthEmployee) {
    const alapber = employee.tetelek.find((t) => t.tipus === "alapber");
    setFizetesForm({ netto_ber: alapber ? String(alapber.osszeg) : "" });
    setFizetesId(employee.id);
  }

  function closeFizetes() {
    setFizetesId(null);
    setFizetesForm(null);
  }

  /** A havi fizetés mentése - a fizetési jegyzék feltöltése előtt is ez fut
   * le, hogy a papír mellett ott legyen a beírt bér. */
  async function fizetesMentes(): Promise<boolean> {
    if (!fizetesEmployee || !fizetesForm) return false;
    const nettoBer = Number(fizetesForm.netto_ber);
    if (!fizetesForm.netto_ber.trim() || Number.isNaN(nettoBer) || nettoBer <= 0) {
      alert("Add meg a nettó bért.");
      return false;
    }
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${fizetesEmployee.id}/${ev}/${honap}/fizetes`, {
        method: "POST",
        body: JSON.stringify({ netto_ber: nettoBer }),
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

  async function handleFizetesSave() {
    if (!fizetesEmployee) return;
    setBusyId(fizetesEmployee.id);
    try {
      if (!(await fizetesMentes())) return;
      closeFizetes();
      router.refresh();
    } finally {
      setBusyId(null);
    }
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function buildPayload() {
    if (!form) return null;
    return {
      // A -1 a "vissza a saját nevére" jelzés: egy sima null azt jelentené,
      // hogy nem küldtük a mezőt (lásd backend TigDraftIn).
      vallalkozas_id: form.vallalkozas_id ? Number(form.vallalkozas_id) : -1,
      netto_osszeg: form.netto_osszeg.trim() ? Number(form.netto_osszeg) : null,
      plusz_afa: form.plusz_afa,
      megjegyzes: form.megjegyzes || null,
      megbizas_targya: form.megbizas_targya || null,
      teljesites_datuma: form.teljesites_datuma || null,
      keltezes: form.keltezes || null,
    };
  }

  /** A TIG űrlap mentése - a saját TIG feltöltése előtt is ez fut le, hogy a
   * beírt összeg a feltöltött papír mellett legyen. */
  async function mentes(): Promise<boolean> {
    if (!openEmployee) return false;
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${openEmployee.id}/${ev}/${honap}/save`, {
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
    if (!openEmployee) return;
    setBusyId(openEmployee.id);
    try {
      if (!(await mentes())) return;
      closeForm();
      router.refresh();
    } finally {
      setBusyId(null);
    }
  }

  /** A "Generálás és kiküldés" gomb: előbb az áttekintő nyílik meg, a küldés
   * csak a megerősítés után indul. Az összeg-ellenőrzés itt fut, hogy egy
   * biztosan elhasaló küldéshez ne kelljen végignézni az adatokat. */
  function kuldesInditasa() {
    if (!openEmployee || !form) return;
    if (!form.netto_osszeg.trim() || Number.isNaN(Number(form.netto_osszeg)) || Number(form.netto_osszeg) <= 0) {
      alert("Add meg a nettó összeget.");
      return;
    }
    setEllenorzoNyitva(true);
  }

  async function handleKuldes() {
    if (!openEmployee || !form) return;
    setEllenorzoNyitva(false);
    if (!openEmployee.email) {
      alert(`${openEmployee.full_name} nem kapott email címet, így nem lehet kiküldeni a TIG-et.`);
      return;
    }
    setBusyId(openEmployee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${openEmployee.id}/${ev}/${honap}/generalas-es-kuldes`, {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function handleSkip(employee: BelsosTigMonthEmployee) {
    if (!(await confirm(`Biztosan kihagyod ${employee.full_name}-t ebben a hónapban?`))) return;
    setBusyId(employee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/skip`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen kihagyás: ${detail?.detail ?? res.status}`);
        return;
      }
      // A kihagyás mindkét űrlapról indítható (TIG és fizetés) - amelyik
      // nyitva van, azt zárjuk.
      closeForm();
      closeFizetes();
      router.refresh();
    } catch (err) {
      alert(`Sikertelen kihagyás (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  /** Egyszerre több kiválasztott fájl is feltölthető - egymás után megy fel,
   * mert minden hívás egy külön számla-sort hoz létre a backenden. */
  async function uploadSzamla(employee: BelsosTigMonthEmployee, input: HTMLInputElement, files: File[]) {
    setBusyId(employee.id);
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        const res = await authFetch(`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/szamla`, { method: "POST", body: fd });
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

  async function deleteSzamla(employee: BelsosTigMonthEmployee, invoiceId: number, filename: string) {
    if (!(await confirm(`Biztosan törlöd ezt a számlát: "${filename}"?`))) return;
    setBusyId(employee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/szamla/${invoiceId}`, { method: "DELETE" });
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

  async function markKifizetve(employee: BelsosTigMonthEmployee, kiadasbaKerul: boolean, kifizetesDatuma: string) {
    setKifizetendoId(null);
    setBusyId(employee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/szamla-kifizetve`, {
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

  // Állapotra szűrés legördülő listából - a hónap végén jellemzően az a
  // kérdés, kivel van még teendő, nem az egész névsor.
  const szurtEmployees =
    allapotSzuro === MIND
      ? employees
      : employees.filter((e) => (e.record?.allapot ?? NINCS_ELKEZDVE) === allapotSzuro);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <SelectDropdown
          value={allapotSzuro}
          options={ALLAPOT_SZURO_OPCIOK}
          onChange={(value) => setAllapotSzuro(value ?? MIND)}
          placeholder={MIND}
        />
        <span className="text-[12px] text-text-muted">
          {szurtEmployees.length === employees.length
            ? `${employees.length} munkatárs`
            : `${szurtEmployees.length} / ${employees.length} munkatárs`}
        </span>
      </div>

      {szurtEmployees.length === 0 && (
        <p className="mb-3 text-[13px] text-text-muted">Nincs ilyen állapotú munkatárs ebben a hónapban.</p>
      )}

      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-border">
            <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Munkatárs</th>
            <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Állapot</th>
            <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Bruttó</th>
            <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">TIG</th>
            <th className="min-w-[240px] py-1.5 pr-6 text-left font-medium text-text-secondary">Számlák</th>
            <th className="py-1.5 text-right font-medium text-text-secondary">Kifizetés</th>
          </tr>
        </thead>
        <tbody>
          {szurtEmployees.map((employee) => {
            const record = employee.record;
            // Bejelentett alkalmazott: a bérét bérszámfejtés fizeti, tehát
            // nincs TIG, nincs számla és nincs kifizetés-jelölés - egyedül az
            // számít, be van-e írva a hónapra a fizetése (lásd backend
            // models/employee.py BelsosJogviszony).
            const alkalmazott = !employee.kell_tig;
            const vanFizetes = record?.netto_osszeg != null && record.netto_osszeg !== 0;
            const allapot = record?.allapot;
            // A "Kész" a korábbi, küldés nélküli életciklusból maradt - a régi
            // bejegyzések ugyanúgy lezártnak számítanak, mint a "Kiküldve".
            const isKesz = allapot === "Kész" || allapot === "Kiküldve";
            const isTerminal = isKesz || allapot === "Kihagyva";
            const busy = busyId === employee.id;
            const invoices = record?.invoices ?? [];
            return (
              <tr key={employee.id} className="border-b border-border last:border-0 align-top">
                <td className="py-3 pr-6">
                  {employee.full_name}
                  {alkalmazott && (
                    <span className="block text-[11px] text-text-muted">bejelentett alkalmazott</span>
                  )}
                </td>
                <td className="py-3 pr-6">
                  {alkalmazott ? (
                    allapot === "Kihagyva" ? (
                      <StatusBadge label="Kihagyva" tone="neutral" />
                    ) : vanFizetes ? (
                      <StatusBadge label="Fizetés beírva" tone="success" />
                    ) : (
                      <StatusBadge label="Fizetés hiányzik" tone="warning" />
                    )
                  ) : (
                    /* Kézzel is javítható: egy tévesen kiküldöttre állított TIG
                       visszavehető "Készítés alatt"-ra, és újra elkészíthető. */
                    <TigAllapotSelect
                      postPath={`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/allapot`}
                      value={record?.allapot ?? null}
                      canEdit={canEdit}
                    />
                  )}
                </td>
                <td className="py-3 pr-6 text-right whitespace-nowrap">
                  {record?.brutto_osszeg != null ? `${record.brutto_osszeg.toLocaleString("hu-HU")} Ft` : "–"}
                </td>
                <td className="py-3 pr-6">
                  {alkalmazott ? (
                    <span className="text-text-muted" title="Bejelentett alkalmazottnál nincs TIG.">
                      nem kell
                    </span>
                  ) : record?.file_url ? (
                    <a
                      href={record.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-text-accent hover:underline"
                    >
                      Dokumentum
                    </a>
                  ) : (
                    <span className="text-text-muted">–</span>
                  )}
                </td>
                <td className="py-3 pr-6">
                  {alkalmazott ? (
                    <span className="text-text-muted" title="Bejelentett alkalmazottnál nincs számla.">
                      nem kell
                    </span>
                  ) : !isKesz ? (
                    <span className="text-text-muted">–</span>
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
                            onClick={() => deleteSzamla(employee, inv.id, inv.filename)}
                            className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                            title="Számla törlése"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      ))}
                      <label className="w-fit cursor-pointer text-[12px] text-text-accent hover:underline">
                        {busy ? "Feltöltés…" : "+ Számla feltöltése"}
                        <input
                          type="file"
                          multiple
                          disabled={busy}
                          onChange={(e) => {
                            const files = Array.from(e.target.files ?? []);
                            if (files.length > 0) uploadSzamla(employee, e.target, files);
                          }}
                          className="hidden"
                        />
                      </label>
                    </div>
                  )}
                </td>
                <td className="py-3 text-right">
                  {alkalmazott ? (
                    /* Az egyetlen teendő: a hónap két összegének beírása
                       (nettó bér + szuperbruttó) - ezt nyitja ez a gomb. */
                    allapot === "Kihagyva" ? null : (
                      <button
                        type="button"
                        onClick={() => openFizetes(employee)}
                        disabled={busy}
                        className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                      >
                        {vanFizetes ? "Fizetés módosítása" : "Fizetés megadása"}
                      </button>
                    )
                  ) : !isTerminal ? (
                    <button
                      type="button"
                      onClick={() => openForm(employee)}
                      disabled={busy}
                      className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                    >
                      TIG készítése
                    </button>
                  ) : isKesz && record?.szamla_kifizetve ? (
                    <StatusBadge label="Kifizetve" tone="success" />
                  ) : isKesz && invoices.length > 0 ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setKifizetendoId(employee.id)}
                      className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                    >
                      Kifizetve jelölés
                    </button>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Bejelentett alkalmazott havi fizetése: nála nincs TIG és nincs
          számla, ezért egyetlen összeg kell - a nettó bér. */}
      {fizetesEmployee && fizetesForm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6"
          onClick={busyId ? undefined : closeFizetes}
        >
          <div
            className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">
              Fizetés – {fizetesEmployee.full_name} ({huEvHonap(ev, honap)})
            </h3>
            <p className="mb-4 text-[12px] text-text-muted">
              Bejelentett alkalmazott: nincs TIG és nincs számla, csak a fizetése kell.
            </p>
            <div className="grid grid-cols-1 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Nettó bér (Ft) *</label>
                <input
                  type="number"
                  value={fizetesForm.netto_ber}
                  onChange={(e) => setFizetesForm({ ...fizetesForm, netto_ber: e.target.value })}
                  disabled={!!busyId}
                  autoFocus
                  className={inputClass}
                />
                <p className="text-[11px] text-text-muted">
                  Amit az emberhez írunk fel: ez lesz a hónap alapbér tétele.
                </p>
              </div>
              {/* A hónap többi tétele (túlóra, benzin, levonás) itt csak
                  látszik: azokat a munkatárs adatlapján lehet szerkeszteni. */}
              {fizetesEmployee.tetelek.filter((t) => t.tipus !== "alapber").length > 0 && (
                <div className="rounded-[var(--radius)] border border-border bg-surface-3 p-2.5">
                  <p className="t-label mb-1.5">A hónap további tételei</p>
                  <ul className="space-y-1">
                    {fizetesEmployee.tetelek
                      .filter((t) => t.tipus !== "alapber")
                      .map((t) => (
                        <li key={t.id} className="flex items-baseline justify-between gap-3 text-[12.5px]">
                          <span className="min-w-0 truncate text-text-secondary">
                            {t.megnevezes}
                            {t.projektkod ? ` · ${t.projektkod}` : ""}
                          </span>
                          <span className="shrink-0 tabular-nums text-text-primary">
                            {t.tipus === "levonando" ? `− ${formatHuf(t.osszeg)}` : formatHuf(t.osszeg)}
                          </span>
                        </li>
                      ))}
                  </ul>
                  <p className="mt-2 text-[11px] text-text-muted">
                    Ezek is beleszámítanak a hónap nettó összegébe – a{" "}
                    <a href={`/csapat/${fizetesEmployee.id}`} className="text-text-accent hover:underline">
                      munkatárs adatlapján
                    </a>{" "}
                    szerkeszthetők.
                  </p>
                </div>
              )}
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={closeFizetes}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Bezárás
              </button>
              <button
                type="button"
                onClick={() => handleSkip(fizetesEmployee)}
                disabled={!!busyId}
                title="Ebben a hónapban nem dolgozott nálunk"
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Kihagyás
              </button>
              {/* Alkalmazottnál nincs kiküldés, amit ki lehetne hagyni - itt
                  a saját papír a fizetési jegyzék, ami a hónaphoz kerül. */}
              <SajatPapirFeltoltes
                cimke="Fizetési jegyzék feltöltése"
                feltoltesPath={`/api/v1/belsos-tig/${fizetesEmployee.id}/${ev}/${honap}/tig-fajl`}
                elokeszit={fizetesMentes}
                disabled={!!busyId}
                onKesz={() => {
                  closeFizetes();
                  router.refresh();
                }}
              />
              <button
                type="button"
                onClick={handleFizetesSave}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busyId === fizetesEmployee.id ? "Mentés…" : "Mentés"}
              </button>
            </div>
          </div>
        </div>
      )}

      {openEmployee && form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busyId ? undefined : closeForm}>
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">
              Belsős TIG – {openEmployee.full_name} ({huEvHonap(ev, honap)})
            </h3>
            <p className="mb-4 text-[12px] text-text-muted">Állapot: {openEmployee.record?.allapot ?? "Nincs elkezdve"}</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {/* Melyik cégéről számlázza ezt a hónapot? A papírra ennek a
                  cégnek a neve, székhelye és adószáma kerül. A választék a
                  munkatárs adatlapjáról jön, az időszakhoz illő céggel
                  előtöltve (lásd EmberCegek). */}
              {openEmployee.cegek.length > 0 && (
                <div className="flex flex-col gap-1 sm:col-span-2">
                  <label className="text-[11px] text-text-muted">Melyik cégéről számlázza?</label>
                  <KeresosSelect
                    value={form.vallalkozas_id ?? ""}
                    options={[
                      { value: "", label: `Saját nevében (${openEmployee.full_name})` },
                      ...openEmployee.cegek.map((c) => ({
                        value: String(c.vallalkozas_id),
                        label: `${c.nev}${c.ervenyes ? "" : " – erre a hónapra nem érvényes"}`,
                      })),
                    ]}
                    onChange={(ertek) => update("vallalkozas_id", ertek)}
                    disabled={!!busyId}
                  />
                </div>
              )}
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label className="text-[11px] text-text-muted">Megbízás tárgya</label>
                <input
                  value={form.megbizas_targya}
                  onChange={(e) => update("megbizas_targya", e.target.value)}
                  disabled={!!busyId}
                  placeholder="A munkatárs adatlapján sincs megadva"
                  className={inputClass}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Teljesítés dátuma</label>
                <input
                  type="date"
                  value={form.teljesites_datuma}
                  onChange={(e) => update("teljesites_datuma", e.target.value)}
                  disabled={!!busyId}
                  className={inputClass}
                />
                <p className={`text-[11px] ${celHonapEltero ? "text-text-warning" : "text-text-muted"}`}>
                  {celHonap
                    ? celHonapEltero
                      ? `Ez a ${huEvHonap(celHonap.ev, celHonap.honap)} havi TIG lesz – átkerül abba a hónapba.`
                      : `Ez a ${huEvHonap(celHonap.ev, celHonap.honap)} havi TIG.`
                    : "A teljesítést megelőző hónap TIG-je."}
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Keltezés</label>
                <input
                  type="date"
                  value={form.keltezes}
                  onChange={(e) => update("keltezes", e.target.value)}
                  disabled={!!busyId}
                  className={inputClass}
                />
                <p className="text-[11px] text-text-muted">Üresen hagyva a kiküldés napja kerül rá.</p>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Nettó összeg (Ft) *</label>
                <input
                  type="number"
                  value={form.netto_osszeg}
                  onChange={(e) => update("netto_osszeg", e.target.value)}
                  disabled={!!busyId}
                  className={inputClass}
                />
                {/* Ha a hónaphoz vannak tételek (alapbér + extrák), az összeg
                    NEM kézzel számolt: a munkatárs adatlapján felvitt tételek
                    adják ki. Itt mutatjuk a bontást, hogy a TIG készítője
                    lássa, miért annyi - ne kelljen átkattintania érte. */}
                {openEmployee.tetelek.length > 0 && (
                  <div className="mt-1.5 rounded-[var(--radius)] border border-border bg-surface-3 p-2.5">
                    <p className="t-label mb-1.5">A hónap tételeiből</p>
                    <ul className="space-y-1">
                      {openEmployee.tetelek.map((t) => (
                        <li key={t.id} className="flex items-baseline justify-between gap-3 text-[12.5px]">
                          <span className="min-w-0 truncate text-text-secondary">
                            {t.megnevezes}
                            {t.projektkod ? ` · ${t.projektkod}` : ""}
                          </span>
                          <span className="shrink-0 text-text-primary tabular-nums">{formatHuf(t.osszeg)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">PLUSZ áfa</label>
                <label className="flex items-center gap-2 py-1.5 text-[13px] text-text-primary">
                  <input
                    type="checkbox"
                    checked={form.plusz_afa}
                    onChange={(e) => update("plusz_afa", e.target.checked)}
                    disabled={!!busyId}
                  />
                  {form.plusz_afa ? "Igen" : "Nem"}
                </label>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Bruttó összeg (Ft)</label>
                <p className="py-1.5 text-[13px] text-text-secondary">
                  {bruttoOsszeg != null ? `${bruttoOsszeg.toLocaleString("hu-HU")} Ft` : "–"}
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Megjegyzés</label>
                <input
                  value={form.megjegyzes}
                  onChange={(e) => update("megjegyzes", e.target.value)}
                  disabled={!!busyId}
                  className={inputClass}
                />
              </div>
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={closeForm}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Bezárás
              </button>
              <button
                type="button"
                onClick={() => handleSkip(openEmployee)}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busyId === openEmployee.id ? "Kihagyás…" : "Kihagyás"}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busyId === openEmployee.id ? "Mentés…" : "Mentés"}
              </button>
              {/* A kiküldés kihagyása: kész TIG feltöltése. A hónap ettől
                  ugyanúgy "Kiküldve" lesz, tehát mehet rá számla. */}
              <SajatPapirFeltoltes
                cimke="Saját TIG feltöltése"
                feltoltesPath={`/api/v1/belsos-tig/${openEmployee.id}/${ev}/${honap}/tig-fajl`}
                elokeszit={mentes}
                disabled={!!busyId}
                onKesz={() => {
                  closeForm();
                  router.refresh();
                }}
              />
              <button
                type="button"
                onClick={kuldesInditasa}
                disabled={!!busyId}
                title={openEmployee.email ?? "Nincs email cím"}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busyId === openEmployee.id ? "Generálás és küldés…" : "Generálás és kiküldés"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Feltételes renderelés, hogy minden megnyitás friss példány legyen. */}
      {kifizetendoEmployee && (
        <KifizetesJeloloDialog
          nev={`${kifizetendoEmployee.full_name} (${huEvHonap(ev, honap)})`}
          osszeg={
            kifizetendoEmployee.record?.brutto_osszeg != null
              ? `${kifizetendoEmployee.record.brutto_osszeg.toLocaleString("hu-HU")} Ft bruttó`
              : null
          }
          hatarido={kifizetendoEmployee.record?.fizetesi_hatarido ?? null}
          onMegse={() => setKifizetendoId(null)}
          onJelol={(kiadasbaKerul, kifizetesDatuma) =>
            markKifizetve(kifizetendoEmployee, kiadasbaKerul, kifizetesDatuma)
          }
        />
      )}

      {ellenorzoNyitva && openEmployee && form && (
        <KuldesEllenorzo
          cim={`Belsős TIG kiküldése – ${openEmployee.full_name}`}
          cimzett={openEmployee.email}
          bevezeto="Ezekkel az adatokkal készül el a PDF, és megy ki azonnal e-mailben. Kiküldés után csak új papírral javítható."
          sorok={ellenorzoSorok()}
          gombCimke="Generálás és kiküldés"
          onMegse={() => setEllenorzoNyitva(false)}
          onKuld={handleKuldes}
        />
      )}
    </div>
  );
}
