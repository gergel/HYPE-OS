"use client";

import { useState } from "react";
import { KuldesEllenorzo, type EllenorzoSor } from "@/components/KuldesEllenorzo";
import { SajatPapirFeltoltes } from "@/components/SajatPapirFeltoltes";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";
import { authFetch } from "@/lib/authFetch";
import { datum } from "@/lib/utokovetes";
import type { MegrendeloiKeret, MegrendeloiKeretModositas } from "@/lib/api";

/** A kísérőlevél alapszövege - ezzel nyílik a szerkesztő mező, és innentől a
 * felhasználóé a szöveg. Ugyanez a backend tartaléka is (lásd
 * services/keret_modositas.py ALAP_LEVEL_SZOVEG); ha itt változik, ott is
 * változtasd. Az aláírást NEM ide írjuk: azt a küldő fiók Gmail-beállításából
 * teszi a levél végére a backend. */
export const ALAP_LEVEL_SZOVEG = `Kedves Partnerünk!

Mellékelten küldjük a köztünk fennálló megbízási szerződés módosítását.
Kérjük, ellenőrizzék az adatokat, és aláírva szíveskedjenek visszaküldeni.`;

/** A szerződésmódosítás ugyanazokkal a cégadatokkal generálódik, mint a
 * keretszerződés - a sablon ezt az öt mezőt írja át. A kiküldés előtti
 * áttekintő ezért pont ezeket mutatja: ami itt üres, az a papíron is üres
 * lesz. */
export function modositasEllenorzoSorok(k: MegrendeloiKeret): EllenorzoSor[] {
  return [
    { cimke: "Cég neve", ertek: k.ceg_neve ?? k.client_nev },
    { cimke: "Székhely", ertek: k.szekhely },
    { cimke: "Nyilvántartási szám", ertek: k.nyilvantartasi_szam },
    { cimke: "Adószám", ertek: k.adoszam },
    { cimke: "Képviselő", ertek: k.kepviselo },
  ];
}

/** A módosítás kiküldése. A hívó dolga a megerősítés és a lista frissítése -
 * innen csak a hibaüzenet jön vissza (üresen: sikerült).
 *
 * Azért van kiemelve a komponensből, mert két helyről indul ugyanez a
 * folyamat: a keretszerződés listasorából és az adatlapról. Két másolatból
 * előbb-utóbb két különböző viselkedés lenne. */
export async function kuldjModositast(keretId: number, levelSzoveg: string): Promise<string | null> {
  try {
    const res = await authFetch(
      `/api/v1/megrendeloi-keretszerzodesek/${keretId}/modositasok/generalas-es-kuldes`,
      { method: "POST", body: JSON.stringify({ level_szoveg: levelSzoveg }) },
    );
    if (!res.ok) {
      const reszlet = await res.json().catch(() => null);
      return String(reszlet?.detail ?? res.status);
    }
    return null;
  } catch (err) {
    return `hálózati hiba: ${err}`;
  }
}

/** A kiküldés előtti ablak: az adatok ellenőrzése ÉS a kísérőlevél megírása.
 *
 * A többi papír fix szöveggel megy; a módosításnál a levél maga is része az
 * ügynek (mit módosítunk, mire hivatkozva), ezért itt szerkeszthető. Az
 * aláírás nincs benne: azt a küldő fiók Gmail-beállításából teszi a levél
 * végére a backend, hogy egy helyen legyen karbantartva. */
export function ModositasKuldesModal({
  keret,
  onMegse,
  onKuld,
}: {
  keret: MegrendeloiKeret;
  onMegse: () => void;
  onKuld: (levelSzoveg: string) => void;
}) {
  const [szoveg, setSzoveg] = useState(ALAP_LEVEL_SZOVEG);

  return (
    <KuldesEllenorzo
      cim="Szerződésmódosítás kiküldése"
      bevezeto="A módosítás ezekkel az adatokkal generálódik, és a lenti levéllel megy ki az admin címről. A kész PDF a Drive mappába kerül."
      cimzett={keret.email}
      sorok={modositasEllenorzoSorok(keret)}
      gombCimke="Generálás és küldés"
      onMegse={onMegse}
      onKuld={() => onKuld(szoveg)}
    >
      <div className="mt-4">
        <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-text-muted">
          A levél szövege
        </label>
        <textarea
          value={szoveg}
          onChange={(e) => setSzoveg(e.target.value)}
          rows={7}
          className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-2 text-[13px] leading-relaxed text-text-primary focus:outline-none"
        />
        <p className="mt-1 text-[11.5px] text-text-muted">
          Az aláírás automatikusan a végére kerül (az admin fiók Gmail-aláírása), a módosítás PDF-je
          pedig csatolmányként megy.
        </p>
      </div>
    </KuldesEllenorzo>
  );
}

function Jelzo({ m }: { m: MegrendeloiKeretModositas }) {
  if (m.allapot === "Kész") return <StatusBadge label="Kész" tone="success" />;
  if (m.allapot === "Aláírásra vár") return <StatusBadge label="Aláírásra vár" tone="warning" />;
  return <StatusBadge label={m.allapot ?? "Készítés alatt"} tone="warning" />;
}

/** A keretszerződéshez tartozó szerződésmódosítások - az adatlapon.
 *
 * Egy keretszerződést az évek alatt többször is módosítanak, ezért ez LISTA,
 * nem egyetlen papír. A folyamat: generálás és kiküldés (a levél az admin
 * fiókból megy, a kész PDF a Drive-ra kerül) -> a módosítás aláírásra vár ->
 * az aláírva visszakapott példány feltöltése zárja le.
 *
 * Ez a szakasz - a projektkódok papírjaival ellentétben - SZERKESZTHETŐ: a
 * módosítás a kerethez tartozik, nincs másik hely, ahol intézni lehetne. */
export function KeretModositasok({
  keret,
  modositasok,
  canCreate,
  canEdit,
  canDelete,
  onValtozas,
}: {
  keret: MegrendeloiKeret;
  modositasok: MegrendeloiKeretModositas[];
  canCreate: boolean;
  canEdit: boolean;
  canDelete: boolean;
  onValtozas: () => void;
}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const [kuldendo, setKuldendo] = useState(false);

  async function kuldes(levelSzoveg: string) {
    setKuldendo(false);
    setBusy(true);
    const hiba = await kuldjModositast(keret.id, levelSzoveg);
    setBusy(false);
    if (hiba) {
      toast(`Sikertelen küldés: ${hiba}`);
      return;
    }
    toast("A szerződésmódosítás kiment. Most már aláírásra vár.");
    onValtozas();
  }

  async function alairtFeltoltes(modositasId: number, file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await authFetch(
        `/api/v1/megrendeloi-keretszerzodesek/${keret.id}/modositasok/${modositasId}/alairt-fajl`,
        { method: "POST", body: fd },
      );
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen feltöltés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      toast("Az aláírt módosítás feltöltve - a papír kész.");
      onValtozas();
    } catch (err) {
      toast(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    }
  }

  async function torles(m: MegrendeloiKeretModositas) {
    if (!(await confirm("Biztosan törlöd ezt a szerződésmódosítást?"))) return;
    setBusy(true);
    try {
      const res = await authFetch(
        `/api/v1/megrendeloi-keretszerzodesek/${keret.id}/modositasok/${m.id}`,
        { method: "DELETE" },
      );
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen törlés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      onValtozas();
    } catch (err) {
      toast(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-b border-border px-5 py-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[13px] font-medium text-text-primary">
          Szerződésmódosítások ({modositasok.length})
        </p>
        <div className="flex flex-wrap items-center gap-3 text-[12.5px]">
          {canCreate && (
            <button
              type="button"
              onClick={() => {
                if (!keret.email?.trim()) {
                  toast("Nincs e-mail cím a keretszerződésen, így nem lehet kiküldeni a módosítást.");
                  return;
                }
                setKuldendo(true);
              }}
              disabled={busy}
              className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Küldés…" : "Módosítás generálása és küldése"}
            </button>
          )}
          {canCreate && (
            <SajatPapirFeltoltes
              cimke="Saját módosítás feltöltése"
              feltoltesPath={`/api/v1/megrendeloi-keretszerzodesek/${keret.id}/modositasok/sajat-fajl`}
              disabled={busy}
              onKesz={onValtozas}
            />
          )}
        </div>
      </div>

      {modositasok.length === 0 ? (
        <p className="text-[12.5px] text-text-muted">
          Ehhez a keretszerződéshez még nem készült szerződésmódosítás.
        </p>
      ) : (
        <ul className="space-y-2">
          {modositasok.map((m) => (
            <li key={m.id} className="rounded-[var(--radius)] border border-border p-3 text-[12.5px]">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-text-primary">Keltezés: {datum(m.keltezes)}</span>
                <Jelzo m={m} />
              </div>
              <p className="mt-0.5 text-text-muted">
                {m.kikuldve ? `Kiküldve: ${datum(m.kikuldve)}` : "Még nem ment ki"}
                {m.kikuldte ? ` · ${m.kikuldte}` : ""}
                {m.email ? ` · ${m.email}` : ""}
              </p>
              {m.level_szoveg && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-[11.5px] text-text-muted hover:text-text-secondary">
                    A kiküldött levél szövege
                  </summary>
                  <p className="mt-1 whitespace-pre-wrap text-[12px] text-text-secondary">{m.level_szoveg}</p>
                </details>
              )}
              {m.megjegyzes && <p className="mt-0.5 text-text-secondary">{m.megjegyzes}</p>}
              <div className="mt-2 flex flex-wrap items-center gap-3">
                {m.file_url && (
                  <a
                    href={m.file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-accent hover:underline"
                  >
                    Módosítás megnyitása
                  </a>
                )}
                {m.alairt_file_url && (
                  <a
                    href={m.alairt_file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-accent hover:underline"
                  >
                    Aláírt példány
                  </a>
                )}
                {canEdit && !m.alairt_file_url && (
                  <label className="cursor-pointer text-text-secondary hover:underline">
                    + Aláírt példány feltöltése
                    <input
                      type="file"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) alairtFeltoltes(m.id, file);
                        e.target.value = "";
                      }}
                    />
                  </label>
                )}
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => torles(m)}
                    disabled={busy}
                    className="text-text-danger hover:underline disabled:opacity-50"
                  >
                    Törlés
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {kuldendo && (
        <ModositasKuldesModal keret={keret} onMegse={() => setKuldendo(false)} onKuld={kuldes} />
      )}
    </div>
  );
}
