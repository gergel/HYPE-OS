"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Paperclip, Trash2 } from "lucide-react";
import { useAlertDialog, useConfirm } from "@/components/ConfirmProvider";
import { ModalReteg } from "@/components/ModalReteg";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
// A pénzformázó a FÜGGŐSÉG NÉLKÜLI modulból jön: a lib/api.ts a
// "next/headers"-t is behúzza, amit kliens komponensbe nem lehet bevinni.
import { penzzel } from "@/lib/penz";
import type { DocumentAttachment } from "@/lib/api";

const KATEGORIA_NEVEK: Record<string, string> = {
  szerzodes: "Szerződés",
  tig: "TIG",
  szamla: "Számla",
  diszpo: "Diszpóhoz",
  gyartas: "Gyártáshoz",
  egyeb: "Egyéb",
};

/** A mai nap ISO alakban, HELYI idő szerint - a `toISOString()` UTC-re vált, és
 * este 10 után már a következő napot adná vissza (lásd ugyanez
 * megrendeloi/MegrendeloiSzamla.tsx-ben). */
function maiNap(): string {
  const most = new Date();
  return `${most.getFullYear()}-${String(most.getMonth() + 1).padStart(2, "0")}-${String(most.getDate()).padStart(2, "0")}`;
}

function meret(bajt: number | null): string {
  if (!bajt) return "";
  if (bajt < 1024 * 1024) return `${Math.round(bajt / 1024)} kB`;
  return `${(bajt / 1024 / 1024).toFixed(1)} MB`;
}

/** A számla fizetési állapota egyetlen jelzőben - a határidő és a
 * kifizetés-dátum együtt mondja meg, hol tart. */
function fizetesiJelzo(doc: DocumentAttachment): { label: string; tone: "success" | "warning" | "danger" } | null {
  if (doc.kifizetve_datuma) return { label: `Kifizetve · ${doc.kifizetve_datuma}`, tone: "success" };
  if (doc.fizetesi_hatarido) {
    // Szöveges (nem Date-objektumos) összehasonlítás: az ISO "ÉÉÉÉ-HH-NN" alak
    // ábécé szerint is helyesen rendeződik, és nem kell időzóna-eltolással
    // bajlódni a "ma" meghatározásához.
    const ma = new Date().toISOString().slice(0, 10);
    if (doc.fizetesi_hatarido < ma) return { label: "Lejárt határidő", tone: "danger" };
    return { label: `Határidő: ${doc.fizetesi_hatarido}`, tone: "warning" };
  }
  return null;
}

/** Egy rekordhoz (szerződéshez, projektkódhoz, kiadáshoz…) tartozó fájlok:
 * feltöltés, megnyitás, törlés. A fájl mindig az R2 tárhelyre kerül, nem a
 * szolgáltatás lemezére - lásd backend services/attachments.py.
 *
 * A `kategoria` mondja meg, mi ez a fájl (szerződés / TIG / számla): a havi
 * számla-csomag (Pénzügyek oldal) ez alapján találja meg a számlákat. */
export function DokumentumFeltoltes({
  entityType,
  entityId,
  attachments,
  kategoria = "egyeb",
  canEdit,
  canDelete,
  emptyText = "Nincs feltöltött fájl.",
  maxOsszMeretBajt,
  meretTanacs,
  fizetesiAllapot = false,
  penznem = "HUF",
}: {
  entityType: string;
  entityId: number;
  attachments: DocumentAttachment[];
  kategoria?: DocumentAttachment["kategoria"];
  canEdit: boolean;
  canDelete: boolean;
  emptyText?: string;
  /** Ha meg van adva, az ITT látszó fájlok EGYÜTTES mérete nem lépheti túl -
   * a diszpó mellékleteinél ez a levélbe csatolható méret (lásd backend
   * services/attachments.py DISZPO_MAX_BAJT). A böngésző előre szól, hogy ne
   * kelljen megvárni egy hosszú, úgyis elutasított feltöltést; a valódi
   * kikényszerítés a backenden van. */
  maxOsszMeretBajt?: number;
  /** Mit tegyen a felhasználó, ha nem fér bele (pl. Drive + brief-link). */
  meretTanacs?: string;
  /** SZÁMLA kategóriánál: minden feltöltött fájlhoz KÜLÖN adható meg fizetési
   * határidő, és egy "Fizetés" gombbal - saját bevétel-sorral - jelölhető
   * kifizetettnek (lásd backend models/document_attachment.py és
   * services/megrendeloi_szamla.py). */
  fizetesiAllapot?: boolean;
  /** Milyen pénznemben vállaltuk a munkát - csak a kifizetés-dialógus nettó
   * mezőjének feliratához kell (lásd projektkod/VallalasiAr.tsx). */
  penznem?: string;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  // A méret-hibát felugró ablakban mutatjuk: több soros, és el kell olvasni
  // (mit tegyen a nagy fájllal) - egy magától eltűnő sáv kevés lenne.
  const alertDialog = useAlertDialog();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  // A fizetés-dialógus melyik fájlhoz nyílt - egyszerre csak egyhez.
  const [fizetesDoc, setFizetesDoc] = useState<DocumentAttachment | null>(null);
  // A "Fizetési határidő" mező HELYI, még el nem mentett szerkesztése -
  // fájlonként. A natív dátumválasztó (pl. hónapot visszalépve) egyetlen
  // kattintás közben TÖBB change-eseményt is kiadhat (év/hónap/nap külön
  // szegmens), és ha ez mindegyike azonnal menteni és router.refresh()-elni
  // próbálna, a képernyő az oldal újratöltése miatt "megakadt" és a mezőbe
  // egy régebbi (menet közbeni) érték íródott vissza - ezért csak a mezőből
  // KILÉPÉSKOR (onBlur) mentünk, ugyanúgy, mint a MegrendeloiSzamla
  // "Fizetési határidő" mezője.
  const [helyiHatarido, setHelyiHatarido] = useState<Record<number, string>>({});
  const osszesMeret = attachments.reduce((osszeg, a) => osszeg + (a.meret_bajt ?? 0), 0);
  const sokSzamlaVan = attachments.length > 1;

  function hataridoErteke(doc: DocumentAttachment): string {
    const helyi = helyiHatarido[doc.id];
    return helyi !== undefined ? helyi : (doc.fizetesi_hatarido ?? "");
  }

  /** onBlur-ra hívva: csak akkor ír a szerverre, ha a mező ténylegesen
   * változott a mentett értékhez képest - máskülönben egy puszta
   * rákattintás/elkattintás is fölösleges kört (és router.refresh()-t)
   * váltana ki. */
  async function mentsHataridotHaValtozott(doc: DocumentAttachment) {
    const ujErtek = hataridoErteke(doc) || null;
    if (ujErtek === (doc.fizetesi_hatarido ?? null)) return;
    setSavingId(doc.id);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${doc.id}/fizetesi-allapot`, {
        method: "PUT",
        body: JSON.stringify({ fizetesi_hatarido: ujErtek }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      // A mentett érték innentől a szerverről (a props-ból) jön - a helyi
      // felülírás eltávolítása nélkül a router.refresh() előtti pillanatban
      // még a régi (immár elavult) helyi érték látszódna.
      setHelyiHatarido((elozo) => {
        const { [doc.id]: _kivetel, ...tobbi } = elozo;
        return tobbi;
      });
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setSavingId(null);
    }
  }

  /** "Fizetés" - a dialógusban megadott adatokkal SAJÁT bevétel-sort nyit
   * ennek a fájlnak (lásd backend services/megrendeloi_szamla.
   * jelold_szamlat_kifizetettnek). */
  async function jelolKifizetettnek(
    doc: DocumentAttachment,
    adat: {
      kifizetes_datuma: string;
      netto: number | null;
      plusz_afa: boolean;
      fizetes_modja: string | null;
      bevetelbe_ne_keruljon: boolean;
      kihagyas_oka: string | null;
    },
  ): Promise<string | null> {
    setSavingId(doc.id);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${doc.id}/kifizetve`, {
        method: "POST",
        body: JSON.stringify(adat),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        return detail?.detail ?? `Sikertelen mentés (HTTP ${res.status})`;
      }
      router.refresh();
      return null;
    } catch (err) {
      return `Sikertelen mentés (hálózati hiba): ${err}`;
    } finally {
      setSavingId(null);
    }
  }

  async function vonjVisszaKifizetest(doc: DocumentAttachment) {
    setSavingId(doc.id);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${doc.id}/kifizetve/visszavonas`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setSavingId(null);
    }
  }

  /** Egyszerre több fájl is kiválasztható. EGYENKÉNT, sorban töltjük fel:
   * így egy hibás fájl (pl. túl nagy) csak magát bukja, a többi felmegy - és
   * a felhasználó látja, melyiknél akadt el. */
  async function feltolt(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    const hibak: string[] = [];
    // A már fent lévők mérete a kiindulás: a korlát az EGYÜTTES méretre szól.
    let eddigiMeret = osszesMeret;
    try {
      for (const file of files) {
        if (maxOsszMeretBajt !== undefined && eddigiMeret + file.size > maxOsszMeretBajt) {
          hibak.push(
            `${file.name} (${meret(file.size)}): nem fér bele a ${meret(maxOsszMeretBajt)}-os keretbe` +
              (meretTanacs ? `.\n${meretTanacs}` : "."),
          );
          continue;
        }
        setUploading(file.name);
        try {
          const fd = new FormData();
          fd.append("file", file);
          const res = await authFetch(
            `/api/v1/csatolmanyok/${entityType}/${entityId}?kategoria=${encodeURIComponent(kategoria)}`,
            { method: "POST", body: fd },
          );
          if (!res.ok) {
            const detail = await res.json().catch(() => null);
            hibak.push(`${file.name}: ${detail?.detail ?? res.status}`);
          } else {
            eddigiMeret += file.size;
          }
        } catch (err) {
          hibak.push(`${file.name}: ${err}`);
        }
      }
      if (hibak.length > 0) await alertDialog(`Sikertelen feltöltés:\n${hibak.join("\n")}`);
      router.refresh();
    } finally {
      setUploading(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function torol(doc: DocumentAttachment) {
    if (!(await confirm(`Törlöd a(z) "${doc.filename}" fájlt?`))) return;
    setDeletingId(doc.id);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${doc.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-2">
      {attachments.length === 0 ? (
        <p className="text-[13px] text-text-muted">{emptyText}</p>
      ) : (
        <ul className="space-y-1.5">
          {attachments.map((doc) => {
            const jelzo = fizetesiAllapot ? fizetesiJelzo(doc) : null;
            return (
              <li
                key={doc.id}
                className={`rounded-[var(--radius)] text-[13px] ${
                  fizetesiAllapot ? "border border-border p-2" : ""
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <Paperclip size={13} className="shrink-0 text-text-muted" />
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate text-text-accent hover:underline"
                    >
                      {doc.filename}
                    </a>
                    <span className="shrink-0 text-[12px] text-text-muted">
                      {KATEGORIA_NEVEK[doc.kategoria] ?? doc.kategoria}
                      {doc.meret_bajt ? ` · ${meret(doc.meret_bajt)}` : ""}
                    </span>
                    {jelzo && <StatusBadge label={jelzo.label} tone={jelzo.tone} />}
                  </span>
                  {canDelete && (
                    <button
                      type="button"
                      onClick={() => torol(doc)}
                      disabled={deletingId === doc.id}
                      title="Fájl törlése"
                      className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
                {/* EGYÉNI fizetési állapot ehhez a fájlhoz - nem a projektkód
                    egészéhez, mert egy kódhoz több számla is tartozhat, és
                    azok külön esedékesek/kifizetettek lehetnek. */}
                {fizetesiAllapot && (
                  <div className="mt-2 flex flex-col items-start gap-1.5 text-[12.5px] text-text-secondary">
                    <label className="flex items-center gap-1.5">
                      Fizetési határidő:
                      <input
                        type="date"
                        value={hataridoErteke(doc)}
                        disabled={!canEdit || savingId === doc.id}
                        onChange={(e) => setHelyiHatarido((elozo) => ({ ...elozo, [doc.id]: e.target.value }))}
                        onBlur={() => mentsHataridotHaValtozott(doc)}
                        className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-0.5 text-[12.5px] text-text-primary disabled:opacity-50"
                      />
                    </label>
                    {/* A KIFIZETÉS jelölése egy dialógust nyit (nem sima
                        dátummező), mert saját bevétel-sort is nyit ennek a
                        számlának - a dátum mellett a bevétel-be-kerülés is
                        eldönthető ott (lásd SzamlaFizetesDialog). */}
                    {!doc.kifizetve_datuma && canEdit && (
                      <button
                        type="button"
                        onClick={() => setFizetesDoc(doc)}
                        disabled={savingId === doc.id}
                        className="rounded-[var(--radius)] border border-[color:var(--text-accent)]/40 px-2.5 py-1 text-[12.5px] text-text-accent hover:bg-bg-accent disabled:opacity-50"
                      >
                        Fizetés
                      </button>
                    )}
                    {doc.kifizetve_datuma && canEdit && (
                      <button
                        type="button"
                        onClick={() => vonjVisszaKifizetest(doc)}
                        disabled={savingId === doc.id}
                        className="text-[12px] text-text-muted hover:text-text-secondary disabled:opacity-50"
                      >
                        Kifizetés visszavonása
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {canEdit && (
        <>
          <label className="inline-block cursor-pointer rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
            {uploading ? `Feltöltés… (${uploading})` : "+ Fájlok feltöltése"}
            <input ref={inputRef} type="file" multiple className="hidden" disabled={!!uploading} onChange={feltolt} />
          </label>
          {maxOsszMeretBajt !== undefined && (
            <p className="text-[12px] text-text-muted">
              Összesen {meret(maxOsszMeretBajt)} fér ide{osszesMeret > 0 ? ` (most ${meret(osszesMeret)} van fent)` : ""}.
              {meretTanacs ? ` ${meretTanacs}` : ""}
            </p>
          )}
        </>
      )}

      {fizetesDoc && (
        <SzamlaFizetesDialog
          doc={fizetesDoc}
          sokSzamlaVan={sokSzamlaVan}
          penznem={penznem}
          onClose={() => setFizetesDoc(null)}
          onSubmit={async (adat) => {
            const hiba = await jelolKifizetettnek(fizetesDoc, adat);
            if (!hiba) setFizetesDoc(null);
            return hiba;
          }}
        />
      )}
    </div>
  );
}

/** "Fizetés" - egy konkrét feltöltött számla kifizetettnek jelölése. SAJÁT
 * bevétel-sort nyit (lásd backend services/megrendeloi_szamla.
 * jelold_szamlat_kifizetettnek), ezért kér dátumot és fizetési módot, mint a
 * projektkód-szintű megfelelője (lásd megrendeloi/MegrendeloiSzamla.tsx
 * KifizetesDialog) - csak fájlonként, nem az egész projektkódra.
 *
 * A NETTÓ ÖSSZEG mező csak akkor jelenik meg (és kötelező), ha a
 * projektkódhoz TÖBB számla is tartozik: egyetlen számlánál a projektkód
 * vállalási ára adja az összeget, többnél viszont csak ebből lehet tudni,
 * mennyi bevétel-sor nyíljon és mekkora összeggel. */
function SzamlaFizetesDialog({
  doc,
  sokSzamlaVan,
  penznem,
  onClose,
  onSubmit,
}: {
  doc: DocumentAttachment;
  sokSzamlaVan: boolean;
  penznem: string;
  onClose: () => void;
  onSubmit: (adat: {
    kifizetes_datuma: string;
    netto: number | null;
    plusz_afa: boolean;
    fizetes_modja: string | null;
    bevetelbe_ne_keruljon: boolean;
    kihagyas_oka: string | null;
  }) => Promise<string | null>;
}) {
  const [datum, setDatum] = useState("");
  const [nettoErtek, setNettoErtek] = useState(doc.netto !== null ? String(doc.netto) : "");
  const [afa, setAfa] = useState(doc.plusz_afa ?? false);
  const [mod, setMod] = useState<"Átutalás" | "Készpénz">("Átutalás");
  const [bevetelbeKerul, setBevetelbeKerul] = useState(true);
  const [indok, setIndok] = useState("");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  const netto = nettoErtek.trim() === "" ? null : Number(nettoErtek.replace(/\s/g, "").replace(",", "."));
  const nettoErvenyes = nettoErtek.trim() === "" || Number.isFinite(netto);
  const bruttoErtek = netto === null || !nettoErvenyes ? null : afa ? Math.round(netto * 1.27 * 100) / 100 : netto;
  const nettoHianyzik = sokSzamlaVan && (netto === null || !nettoErvenyes);

  async function jelol() {
    setBusy(true);
    setHiba(null);
    const eredmeny = await onSubmit({
      kifizetes_datuma: datum,
      netto: sokSzamlaVan ? netto : null,
      plusz_afa: afa,
      fizetes_modja: mod,
      bevetelbe_ne_keruljon: !bevetelbeKerul,
      kihagyas_oka: bevetelbeKerul ? null : indok.trim(),
    });
    setBusy(false);
    if (eredmeny) setHiba(eredmeny);
  }

  return (
    <ModalReteg onClose={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">Számla kifizetve</h3>
          <p className="mt-0.5 truncate text-[12.5px] text-text-secondary">{doc.filename}</p>
        </div>

        <div className="space-y-4 p-5">
          {sokSzamlaVan && (
            <div>
              <div className="flex flex-wrap items-end gap-3">
                <label className="block text-[13px] text-text-secondary">
                  Nettó összeg ({penznem})
                  <input
                    type="text"
                    inputMode="numeric"
                    value={nettoErtek}
                    placeholder="Kötelező"
                    onChange={(e) => setNettoErtek(e.target.value)}
                    className="mt-1 w-32 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary"
                  />
                </label>
                <label className="flex cursor-pointer items-center gap-2 pb-1.5 text-[13px] text-text-primary">
                  <input type="checkbox" checked={afa} onChange={(e) => setAfa(e.target.checked)} />+ ÁFA
                </label>
                <p className="pb-1.5 text-[13px] text-text-secondary">
                  Bruttó: <span className="text-text-primary">{bruttoErtek === null ? "–" : penzzel(bruttoErtek, penznem)}</span>
                </p>
              </div>
              <p className="mt-1 text-[12px] text-text-muted">
                Ehhez a projektkódhoz több számla is tartozik - add meg, mekkora ennek a saját nettó összege.
              </p>
              {!nettoErvenyes && <p className="mt-1 text-[12px] text-text-danger">Ez nem szám.</p>}
            </div>
          )}

          <label className="block text-[13px] text-text-primary">
            Mikor érkezett meg a pénz *
            <span className="mt-1 flex items-center gap-2">
              <input
                type="date"
                value={datum}
                onChange={(e) => setDatum(e.target.value)}
                className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary"
              />
              <button
                type="button"
                onClick={() => setDatum(maiNap())}
                className="shrink-0 rounded-[var(--radius)] border border-border px-2 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-3"
              >
                Ma
              </button>
            </span>
          </label>

          <div>
            <p className="text-[13px] text-text-primary">Hogyan érkezett a pénz?</p>
            <div className="mt-1.5 flex gap-2">
              {(["Átutalás", "Készpénz"] as const).map((lehetoseg) => (
                <button
                  key={lehetoseg}
                  type="button"
                  onClick={() => setMod(lehetoseg)}
                  className={`rounded-[var(--radius)] border px-3 py-1.5 text-[13px] ${
                    mod === lehetoseg
                      ? "border-text-accent/40 bg-bg-accent text-text-accent"
                      : "border-border text-text-secondary hover:bg-surface-3"
                  }`}
                >
                  {lehetoseg}
                </button>
              ))}
            </div>
          </div>

          <label className="flex cursor-pointer items-start gap-2.5">
            <input
              type="checkbox"
              checked={bevetelbeKerul}
              onChange={(e) => setBevetelbeKerul(e.target.checked)}
              className="mt-0.5"
            />
            <span className="text-[13px] text-text-primary">
              Kerüljön be a Pénzügy → Bevételek közé
              <span className="mt-0.5 block text-[12px] text-text-muted">
                Ez nyitja a bevétel-sort ennek a számlának az összegével.
              </span>
            </span>
          </label>

          {!bevetelbeKerul && (
            <div className="space-y-2 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
              <p className="text-[12.5px] text-text-secondary">
                A számla „kifizetve” lesz, de <b>nem kerül a bevételek közé</b> - akkor válaszd ezt, ha a pénz máshol
                van elszámolva, és itt csak duplázná az összeget.
              </p>
              <label className="block text-[13px] text-text-primary">
                Miért nem kerül a bevételek közé?
                <textarea
                  rows={2}
                  value={indok}
                  onChange={(e) => setIndok(e.target.value)}
                  placeholder="Pl. beszámítva, a másik cégen át számláztuk…"
                  className="mt-1 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] leading-relaxed text-text-primary"
                />
              </label>
            </div>
          )}

          {hiba && <p className="text-[12.5px] text-text-danger">{hiba}</p>}
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Mégse
          </button>
          <button
            type="button"
            disabled={busy || !datum || nettoHianyzik || !nettoErvenyes || (!bevetelbeKerul && !indok.trim())}
            onClick={jelol}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Kifizetve jelölés
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
