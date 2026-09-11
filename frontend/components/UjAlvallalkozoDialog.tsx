"use client";

import { useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";
import { authFetch } from "@/lib/authFetch";

/** ÚJ ALVÁLLALKOZÓ felvétele felugró ablakban (a felhasználó kérése): a
 * kiadás-űrlap "Alvállalkozó" keresőjéből nyílik, amikor a beírt név nincs a
 * meglévők közt - a név előre kitöltve érkezik, és itt egyben megadható
 * minden adata, a vállalkozási (papírozási) mezőkkel együtt, amikből a
 * szerződés és a TIG előtölt (lásd backend services/szamlazo.SzamlazoFel és
 * schemas/employee.EmployeeCreate).
 *
 * A hívó FELTÉTELESEN rendereli (mint az IndoklasDialog-ot): minden
 * megnyitás friss példány. Sikeres mentés után az onKesz kapja az új ember
 * azonosítóját és nevét - a kiválasztás a hívó dolga. */
export type UjAlvallalkozoElotoltes = Partial<{
  full_name: string;
  email: string;
  telefon: string;
  vallakozas_neve: string;
  vallakozas_szekhely: string;
  vallalkozas_adoszama: string;
  nyilvantartasi_szam: string;
  vallalkozas_kepviselo: string;
  megbizas_targya: string;
  plusz_afa: boolean;
}>;

export function UjAlvallalkozoDialog({
  kezdoNev,
  kezdoAdatok,
  onMegse,
  onKesz,
}: {
  /** A keresőbe beírt név - ezzel előtöltve nyílik az ablak. */
  kezdoNev: string;
  /** A szerződésből/számlából KIOLVASOTT adatok (a felhasználó kérése): az
   * AI-s kitöltés ezekkel tölti elő az űrlapot, és csak a hiányzókat kell
   * kézzel pótolni. Minden mező szabadon javítható. */
  kezdoAdatok?: UjAlvallalkozoElotoltes;
  onMegse: () => void;
  onKesz: (id: number, nev: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [adatok, setAdatok] = useState({
    full_name: kezdoNev,
    email: "",
    telefon: "",
    vallakozas_neve: "",
    vallakozas_szekhely: "",
    vallalkozas_adoszama: "",
    nyilvantartasi_szam: "",
    vallalkozas_kepviselo: "",
    megbizas_targya: "",
    plusz_afa: false,
    ...(kezdoAdatok ?? {}),
  });

  function mezo(kulcs: keyof typeof adatok, ertek: string | boolean) {
    setAdatok((a) => ({ ...a, [kulcs]: ertek }));
    if (hiba) setHiba(null);
  }

  async function ment() {
    if (!adatok.full_name.trim()) {
      setHiba("A név megadása kötelező.");
      return;
    }
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch("/api/v1/crew", {
        method: "POST",
        body: JSON.stringify({
          full_name: adatok.full_name.trim(),
          // Alvállalkozó = KÜLSŐS munkatárs: erről ismeri fel a papírozás,
          // hogy szerződés és TIG jár utána (lásd backend
          // models/finance.Expense.alvallalkozoi_papirt_igenyel).
          tipus: "kulsos",
          email: adatok.email.trim() || null,
          telefon: adatok.telefon.trim() || null,
          vallakozas_neve: adatok.vallakozas_neve.trim() || null,
          vallakozas_szekhely: adatok.vallakozas_szekhely.trim() || null,
          vallalkozas_adoszama: adatok.vallalkozas_adoszama.trim() || null,
          nyilvantartasi_szam: adatok.nyilvantartasi_szam.trim() || null,
          vallalkozas_kepviselo: adatok.vallalkozas_kepviselo.trim() || null,
          megbizas_targya: adatok.megbizas_targya.trim() || null,
          plusz_afa: adatok.plusz_afa,
        }),
      });
      const letrejott = await res.json().catch(() => null);
      if (!res.ok || !letrejott?.id) {
        setHiba(`Sikertelen mentés: ${letrejott?.detail ?? res.status}`);
        return;
      }
      onKesz(letrejott.id, adatok.full_name.trim());
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  const szovegMezok: { kulcs: keyof typeof adatok; cimke: string; placeholder?: string }[] = [
    { kulcs: "email", cimke: "E-mail (ide megy a szerződés és a TIG)" },
    { kulcs: "telefon", cimke: "Telefonszám" },
    { kulcs: "vallakozas_neve", cimke: "Vállalkozás neve (ez kerül a papírra)" },
    { kulcs: "vallakozas_szekhely", cimke: "Székhely" },
    { kulcs: "vallalkozas_adoszama", cimke: "Adószám" },
    { kulcs: "nyilvantartasi_szam", cimke: "Nyilvántartási szám" },
    { kulcs: "vallalkozas_kepviselo", cimke: "Képviselő" },
    { kulcs: "megbizas_targya", cimke: "Megbízás tárgya", placeholder: "Pl. videós szolgáltatás" },
  ];

  return (
    <ModalReteg onClose={onMegse}>
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-2 text-[14px] font-medium text-text-primary">Új alvállalkozó felvétele</h3>
        <p className="mb-4 text-[13px] text-text-secondary">
          Külsős munkatársként kerül a rendszerbe, és mentés után rögtön ki is választódik a kiadáson. A
          vállalkozási adatokból tölt elő a szerződése és a TIG-je – amit most nem tudsz, később a Csapat oldalán
          pótolható.
        </p>
        <div className="mb-1.5">
          <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-text-muted">Név *</label>
          <input
            autoFocus
            value={adatok.full_name}
            onChange={(e) => mezo("full_name", e.target.value)}
            className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary outline-none focus:border-text-accent/40"
          />
        </div>
        <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
          {szovegMezok.map((m) => (
            <div key={m.kulcs} className="mt-3">
              <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-text-muted">
                {m.cimke}
              </label>
              <input
                value={adatok[m.kulcs] as string}
                placeholder={m.placeholder}
                onChange={(e) => mezo(m.kulcs, e.target.value)}
                className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary outline-none focus:border-text-accent/40"
              />
            </div>
          ))}
        </div>
        <label className="mt-4 flex cursor-pointer items-center gap-2 text-[13px] text-text-secondary">
          <input
            type="checkbox"
            checked={adatok.plusz_afa}
            onChange={(e) => mezo("plusz_afa", e.target.checked)}
            className="h-3.5 w-3.5 cursor-pointer accent-[var(--text-accent)]"
          />
          +ÁFA-s számlát ad (a papírokon a nettó mellé ÁFA kerül)
        </label>
        {hiba && <p className="mt-3 text-[12.5px] text-text-danger">{hiba}</p>}
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onMegse}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Mégse
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void ment()}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-primary hover:bg-surface-3 disabled:opacity-50"
          >
            {busy ? "Mentés…" : "Felvétel"}
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
