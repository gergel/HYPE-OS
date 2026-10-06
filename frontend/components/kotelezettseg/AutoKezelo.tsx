"use client";

import { Fragment, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Plus, Sparkles, Trash2, Upload } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { AutoTeendok } from "@/components/kotelezettseg/AutoTeendok";
import { KotelezettsegKezelo } from "@/components/kotelezettseg/KotelezettsegKezelo";
import { PapirFeltoltes } from "@/components/kotelezettseg/PapirFeltoltes";
import { authFetch } from "@/lib/authFetch";
import { huDatum } from "@/lib/huDate";
import { formatHuf } from "@/lib/penz";
import type { Auto, Kotelezettseg } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";
import { KifizetveDatummal } from "@/components/projektkod/KifizetveDatummal";

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

/** Gyors választék a költés megnevezéséhez - nem korlátozás, bármi beírható. */
const KOLTSEG_FAJTAK = ["Tankolás", "Szerviz", "Alkatrész", "Gumi", "Autópálya-matrica", "Parkolás", "Mosás"];

/** Ugyanaz a szókészlet, mint a Pénzügy kiadásainál - a kimutatás így egyben
 * látja az itt és az ott rögzített fizetéseket. */
const FIZETESI_MODOK = ["Átutalás", "Készpénz", "Bankkártya"];

/** Bruttó a nettóból; áfa nélkül a kettő ugyanaz (ugyanaz a szabály, mint a
 * backendben - routes/kotelezettsegek.brutto). */
function bruttoBol(netto: number | null, pluszAfa: boolean): number | null {
  if (netto == null || Number.isNaN(netto)) return null;
  return pluszAfa ? Math.round(netto * 1.27 * 100) / 100 : netto;
}

function hataridoJelzo(allapot: string) {
  if (allapot === "lejart") return { label: "Lejárt papír", tone: "danger" as const };
  if (allapot === "hamarosan") return { label: "Hamarosan lejár", tone: "warning" as const };
  if (allapot === "rendben") return { label: "Papírok rendben", tone: "success" as const };
  return { label: "Nincs határidő felvéve", tone: "neutral" as const };
}

/** Egy autóra felvitt költés űrlapja.
 *
 * Amit itt rögzítünk, az SIMA KIADÁS a Pénzügyben (csak az autóhoz kötve),
 * ezért jelenik meg magától az összesítő kiadások közt is - nem másolat, ami
 * szétcsúszhatna, hanem ugyanaz a sor (lásd backend models/auto.py). */
function KoltsegUrlap({ autoId, onKesz }: { autoId: number; onKesz: () => void }) {
  const router = useRouter();
  const [megnevezes, setMegnevezes] = useState("");
  const [osszeg, setOsszeg] = useState("");
  // A költés PROJEKTHEZ köthető (a felhasználó kérése): pl. a forgatáshoz
  // tankolás a projektkód költségei közt is látszik - de ugyanaz az EGY
  // kiadás-sor marad, a Pénzügyben nem duplázódik.
  const [projektkodId, setProjektkodId] = useState("");
  const [projektkodok, setProjektkodok] = useState<{ id: number; projektkod: string; project_nev: string | null }[]>([]);
  useEffect(() => {
    authFetch("/api/v1/project-codes/valaszthato")
      .then((res) => (res.ok ? res.json() : []))
      .then(setProjektkodok)
      .catch(() => {});
  }, []);
  const [pluszAfa, setPluszAfa] = useState(false);
  const [fizetesiMod, setFizetesiMod] = useState("");
  // NINCS SZÁMLA, NEM IS LESZ (a felhasználó kérése) - csak készpénznél
  // jelölhető; ugyanaz, mint a Kiadások felvitelénél: a Házipénztárban
  // FEKETE kiadásként jelenik meg.
  const [nincsSzamla, setNincsSzamla] = useState(false);
  const keszpenzes = fizetesiMod === "Készpénz";
  const [datum, setDatum] = useState(new Date().toISOString().slice(0, 10));
  // KIFIZETVE-E MÁR (a felhasználó kérése): a legtöbb költés (tankolás,
  // parkolás) azonnal ki van fizetve - ez az alap. Ha viszont számla jött
  // (pl. szerviz), de még nem utaltuk el, csak a fizetési határidőt adjuk
  // meg; a kifizetést később a sor "Fizetés" gombja jelöli, dátummal.
  const [kifizetve, setKifizetve] = useState(true);
  const [hatarido, setHatarido] = useState("");
  const [megjegyzes, setMegjegyzes] = useState("");
  // A bizonylat (számla PDF, blokk-fotó) MÁR A FELVITELKOR csatolható: a
  // költést jellemzően a papírral a kézben rögzítik, és külön lépésben
  // megkeresni a sort, majd ott feltölteni, fölösleges kör - abból lesz a
  // bizonylat nélküli kiadás.
  const [fajlok, setFajlok] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  // AI-KIOLVASÁS a feltöltött számlából/blokkból (a felhasználó kérése) -
  // ugyanaz a kiolvasó, mint a Kiadásoknál (lásd backend
  // services/kiadas_kiolvasas.py). Csak előtölt: minden mező átírható.
  const [aiBusy, setAiBusy] = useState(false);
  const [aiUzenet, setAiUzenet] = useState<string | null>(null);

  async function aiKitolt(fajl: File) {
    setAiBusy(true);
    setAiUzenet(null);
    try {
      const fd = new FormData();
      fd.append("file", fajl);
      const res = await authFetch("/api/v1/autok/kiadasok/kiolvasas", { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setAiUzenet(`Nem sikerült kiolvasni: ${detail?.detail ?? res.status}`);
        return;
      }
      const a = (await res.json()) as Record<string, string | number | null>;
      const szoveg = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim() : null);
      let beirt = 0;
      // "Mire ment" = a számla fő tétele; a partner neve a megjegyzésbe kerül,
      // hogy a költés-sor rövid maradjon, de látszódjon, ki állította ki.
      const mire = szoveg(a.kiadas_leiras) ?? szoveg(a.megnevezes);
      if (mire) {
        setMegnevezes(mire);
        beirt++;
      }
      const partner = szoveg(a.megnevezes);
      if (partner && partner !== mire) {
        setMegjegyzes(partner);
        beirt++;
      }
      if (a.netto !== null && a.netto !== undefined && a.netto !== "") {
        setOsszeg(String(a.netto));
        beirt++;
      }
      setPluszAfa(a.plusz_afa === "igen");
      const mod = szoveg(a.kifizetes_modja);
      const nemFizetett = a.kesz === "false";
      if (nemFizetett) {
        setKifizetve(false);
        if (szoveg(a.fizetes_hatarideje)) {
          setHatarido(String(a.fizetes_hatarideje));
          beirt++;
        }
      } else {
        setKifizetve(true);
        if (szoveg(a.fizetes_datuma)) {
          setDatum(String(a.fizetes_datuma));
          beirt++;
        }
        if (szoveg(a.fizetes_hatarideje)) setHatarido(String(a.fizetes_hatarideje));
      }
      if (mod && FIZETESI_MODOK.includes(mod) && !(nemFizetett && mod === "Készpénz")) {
        setFizetesiMod(mod);
        beirt++;
      }
      // A számla a bizonylatok közé is bekerül - mentéskor feltöltődik.
      setFajlok((elozo) => (elozo.includes(fajl) ? elozo : [...elozo, fajl]));
      const deviza = szoveg(a.penznem);
      setAiUzenet(
        (beirt > 0 ? `Kiolvasva (${beirt} mező) – ellenőrizd mentés előtt.` : "A számlából nem sikerült mezőt kiolvasni.") +
          (nemFizetett ? " A számlán még előttünk álló fizetési határidő van, ezért „Még nem” állásra tettük." : "") +
          (deviza && deviza !== "HUF" ? ` A számla ${deviza}-ban szól – az összeget forintban add meg.` : ""),
      );
    } catch (err) {
      setAiUzenet(`Nem sikerült kiolvasni (hálózati hiba): ${err}`);
    } finally {
      setAiBusy(false);
    }
  }

  async function ment() {
    if (!megnevezes.trim() || !osszeg.trim()) {
      alert("Add meg, mire ment és mennyi.");
      return;
    }
    if (!kifizetve && !hatarido) {
      alert("Add meg a fizetési határidőt.");
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/autok/${autoId}/kiadasok`, {
        method: "POST",
        body: JSON.stringify({
          megnevezes: megnevezes.trim(),
          // NETTÓ megy fel, a bruttót a backend számolja az áfa-jelölésből.
          osszeg: Number(osszeg),
          plusz_afa: pluszAfa,
          fizetesi_mod: fizetesiMod || null,
          nincs_szamla: keszpenzes && nincsSzamla,
          datum: kifizetve ? datum || null : null,
          kifizetve,
          fizetes_hatarideje: kifizetve ? null : hatarido,
          megjegyzes: megjegyzes.trim() || null,
          project_code_id: projektkodId ? Number(projektkodId) : null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      // A fájlok csak a mentés UTÁN mehetnek fel: a csatolmány a most
      // létrejött kiadás-sorhoz tartozik, tehát kell az azonosítója. Ha a
      // feltöltés hibázik, a KÖLTÉS attól még megvan - csak szólunk, hogy a
      // bizonylat kimaradt, és utólag a sorból pótolható.
      if (fajlok.length > 0 && !(keszpenzes && nincsSzamla)) {
        const kiadas = (await res.json()) as { id: number };
        for (const file of fajlok) {
          const fd = new FormData();
          fd.append("file", file);
          const fel = await authFetch(`/api/v1/csatolmanyok/autoKiadas/${kiadas.id}?kategoria=szamla`, {
            method: "POST",
            body: fd,
          });
          if (!fel.ok) {
            const detail = await fel.json().catch(() => null);
            alert(
              `A költés elmentve, de a bizonylat feltöltése nem sikerült (${file.name}): ` +
                `${detail?.detail ?? fel.status}. A sorból utólag pótolhatod.`,
            );
            break;
          }
        }
      }
      setMegnevezes("");
      setOsszeg("");
      setPluszAfa(false);
      setFizetesiMod("");
      setNincsSzamla(false);
      setKifizetve(true);
      setHatarido("");
      setMegjegyzes("");
      setProjektkodId("");
      setFajlok([]);
      setAiUzenet(null);
      onKesz();
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fade-in flex flex-wrap items-end gap-3 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
      <div className="flex w-full flex-wrap items-center gap-3">
        <label
          className={`flex w-fit items-center gap-1.5 rounded-[var(--radius)] border border-border px-2 py-1.5 text-[12.5px] ${
            aiBusy ? "opacity-50" : "cursor-pointer text-text-secondary hover:bg-surface-2"
          }`}
        >
          <Sparkles size={13} />
          {aiBusy ? "Kiolvasás…" : "Kitöltés számlából (AI)"}
          <input
            type="file"
            accept="application/pdf,image/*"
            disabled={aiBusy}
            onChange={(e) => {
              const fajl = e.target.files?.[0];
              e.target.value = "";
              if (fajl) void aiKitolt(fajl);
            }}
            className="hidden"
          />
        </label>
        {aiUzenet && <span className="text-[12px] text-text-accent">{aiUzenet}</span>}
      </div>
      <label className="flex flex-col gap-1.5">
        <span className="t-label">Mire ment</span>
        <input
          list="auto-koltseg-fajtak"
          value={megnevezes}
          onChange={(e) => setMegnevezes(e.target.value)}
          placeholder="pl. Tankolás"
          className={`${inputClass} w-[200px]`}
        />
        <datalist id="auto-koltseg-fajtak">
          {KOLTSEG_FAJTAK.map((f) => (
            <option key={f} value={f} />
          ))}
        </datalist>
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="t-label">Nettó összeg (Ft)</span>
        <input type="number" value={osszeg} onChange={(e) => setOsszeg(e.target.value)} className={`${inputClass} w-[130px]`} />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="t-label">ÁFA</span>
        <span className="flex h-[34px] items-center gap-2 text-[13px] text-text-primary">
          <input type="checkbox" checked={pluszAfa} onChange={(e) => setPluszAfa(e.target.checked)} />
          Plusz ÁFA
        </span>
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="t-label">Bruttó</span>
        <span className="flex h-[34px] items-center text-[13px] text-text-secondary">
          {osszeg.trim() ? formatHuf(bruttoBol(Number(osszeg), pluszAfa)) : "–"}
        </span>
      </label>
      <div className="flex flex-col gap-1.5">
        <span className="t-label">Kifizetve?</span>
        <span className="flex h-[34px] items-center gap-1 rounded-[var(--radius)] border border-border p-0.5 text-[12.5px]">
          {[
            { ertek: true, cimke: "Igen, kifizetve" },
            { ertek: false, cimke: "Még nem (számla jött)" },
          ].map((o) => (
            <button
              key={String(o.ertek)}
              type="button"
              onClick={() => {
                setKifizetve(o.ertek);
                // Készpénzes költés nem lehet kifizetetlen: a pénz helyben
                // kiment a kasszából - ilyenkor a fizetési mód üresre áll.
                if (!o.ertek && keszpenzes) {
                  setFizetesiMod("");
                  setNincsSzamla(false);
                }
              }}
              className={`rounded-[calc(var(--radius)-2px)] px-2 py-1 ${
                kifizetve === o.ertek ? "bg-surface-2 text-text-primary" : "text-text-muted hover:text-text-primary"
              }`}
            >
              {o.cimke}
            </button>
          ))}
        </span>
      </div>
      <label className="flex flex-col gap-1.5">
        <span className="t-label">{kifizetve ? "Hogyan fizettük" : "Hogyan fizetjük"}</span>
        <KeresosSelect
          value={fizetesiMod || null}
          options={FIZETESI_MODOK.filter((m) => kifizetve || m !== "Készpénz").map((m) => ({ value: m, label: m }))}
          onChange={setFizetesiMod}
          placeholder="–"
          className="w-[160px]"
        />
      </label>
      {keszpenzes && (
        <label className="flex flex-col gap-1.5">
          <span className="t-label">Számla</span>
          <span className="flex h-[34px] items-center gap-2 text-[13px] text-text-primary">
            <input type="checkbox" checked={nincsSzamla} onChange={(e) => setNincsSzamla(e.target.checked)} />
            Nincs számla, nem is lesz
          </span>
        </label>
      )}
      {kifizetve ? (
        <label className="flex flex-col gap-1.5">
          <span className="t-label">Mikor</span>
          <input type="date" value={datum} onChange={(e) => setDatum(e.target.value)} className={`${inputClass} w-[160px]`} />
        </label>
      ) : (
        <label className="flex flex-col gap-1.5">
          <span className="t-label">Fizetési határidő</span>
          <input
            type="date"
            value={hatarido}
            onChange={(e) => setHatarido(e.target.value)}
            className={`${inputClass} w-[160px]`}
          />
        </label>
      )}
      <label className="flex flex-col gap-1.5">
        <span className="t-label">Megjegyzés</span>
        <input value={megjegyzes} onChange={(e) => setMegjegyzes(e.target.value)} className={`${inputClass} w-[220px]`} />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="t-label">Projekt (nem kötelező)</span>
        <KeresosSelect
          value={projektkodId || null}
          options={[
            { value: "", label: "– nincs projekthez kötve –" },
            ...projektkodok.map((pk) => ({
              value: String(pk.id),
              label: pk.project_nev ? `${pk.projektkod} – ${pk.project_nev}` : pk.projektkod,
            })),
          ]}
          onChange={(v) => setProjektkodId(v ?? "")}
          placeholder="Projektkód…"
          className="w-[240px]"
        />
      </label>
      {!(keszpenzes && nincsSzamla) && (
      <label className="flex flex-col gap-1.5">
        <span className="t-label">Bizonylat</span>
        <span
          className={`flex h-[34px] w-fit items-center gap-1.5 rounded-[var(--radius)] border border-border px-2 text-[12.5px] ${
            busy ? "opacity-50" : "cursor-pointer text-text-secondary hover:bg-surface-2"
          }`}
        >
          <Upload size={13} />
          {fajlok.length === 0
            ? "Számla vagy fotó a gépről"
            : `${fajlok.length} fájl kiválasztva`}
          <input
            type="file"
            multiple
            accept="application/pdf,image/*"
            disabled={busy}
            onChange={(e) => setFajlok(Array.from(e.target.files ?? []))}
            className="hidden"
          />
        </span>
      </label>
      )}
      <button type="button" onClick={ment} disabled={busy} className="btn btn-primary">
        {busy ? "Mentés…" : "Hozzáadás"}
      </button>
      <button type="button" onClick={onKesz} className="btn btn-ghost">
        Mégse
      </button>
    </div>
  );
}

/** Céges autók: a papírjaik lejárata és a rájuk költött pénz.
 *
 * A határidőket (forgalmi, biztosítás) ugyanaz a szerkesztő kezeli, mint az
 * előfizetéseket - ezért kapnak ugyanúgy értesítést és feladatot a lejárat
 * előtt. */
export function AutoKezelo({
  autok,
  hataridok,
  emberek,
  teendoEmberek,
  canEdit,
  canCreate,
  canDelete,
}: {
  autok: Auto[];
  /** Az autókhoz kötött kötelezettségek (forgalmi, biztosítás) - a beágyazott
   * szerkesztő ezekkel dolgozik. */
  hataridok: Kotelezettseg[];
  emberek: { id: number; full_name: string }[];
  /** A teendő-felelős választó szűkített listája: csak akik hozzáférnek az
   * Autók oldalhoz (a backend is ezt ellenőrzi - routes/autok.py). */
  teendoEmberek: { id: number; full_name: string }[];
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitott, setNyitott] = useState<number | null>(autok.length === 1 ? autok[0].id : null);
  const [koltsegUrlap, setKoltsegUrlap] = useState<number | null>(null);
  const [ujAuto, setUjAuto] = useState(false);
  const [rendszam, setRendszam] = useState("");
  const [megnevezes, setMegnevezes] = useState("");
  const [felelosId, setFelelosId] = useState("");
  const [busy, setBusy] = useState(false);

  async function autoMentes() {
    if (!rendszam.trim()) {
      alert("A rendszám kötelező.");
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/autok", {
        method: "POST",
        body: JSON.stringify({
          rendszam: rendszam.trim(),
          megnevezes: megnevezes.trim() || null,
          felelos_id: felelosId ? Number(felelosId) : null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setRendszam("");
      setMegnevezes("");
      setFelelosId("");
      setUjAuto(false);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function autoTorles(auto: Auto) {
    if (!(await confirm(`Törlöd ezt az autót: ${auto.rendszam}? A rá könyvelt kiadások megmaradnak a Pénzügyben.`)))
      return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/autok/${auto.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function koltsegTorles(kiadasId: number, megnevezes: string) {
    if (!(await confirm(`Törlöd ezt a költést: "${megnevezes}"? A Pénzügy kiadásai közül is eltűnik.`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/autok/kiadasok/${kiadasId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {autok.length === 0 && <p className="mb-3 text-[13px] text-text-muted">Még nincs felvéve autó.</p>}

      <div className="space-y-3">
        {autok.map((auto) => {
          const jelzo = hataridoJelzo(auto.hatarido_allapot);
          const nyitva = nyitott === auto.id;
          const autoHataridok = hataridok.filter((k) => k.auto_id === auto.id);
          return (
            <div key={auto.id} className="rounded-[var(--radius)] border border-border">
              <div className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                <button
                  type="button"
                  onClick={() => setNyitott(nyitva ? null : auto.id)}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                >
                  {nyitva ? (
                    <ChevronDown size={14} className="shrink-0 text-text-muted" />
                  ) : (
                    <ChevronRight size={14} className="shrink-0 text-text-muted" />
                  )}
                  <span className="min-w-0">
                    <span className="text-[13.5px] font-medium text-text-primary">{auto.rendszam}</span>
                    {auto.megnevezes && <span className="ml-2 text-[12.5px] text-text-muted">{auto.megnevezes}</span>}
                  </span>
                </button>
                <StatusBadge label={jelzo.label} tone={jelzo.tone} />
                <span className="text-[12.5px] text-text-secondary">
                  Eddigi költés (nettó): <span className="text-text-primary">{formatHuf(auto.koltseg_osszesen)}</span>
                </span>
                {auto.felelos_nev && <span className="text-[12.5px] text-text-muted">{auto.felelos_nev}</span>}
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => autoTorles(auto)}
                    disabled={busy}
                    title="Autó törlése"
                    className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>

              {nyitva && (
                <div className="fade-in space-y-6 border-t border-border px-3 py-4">
                  {/* Papírok: forgalmi, biztosítás. Ugyanaz a szerkesztő, mint
                      az előfizetéseknél - így a lejáratról ugyanúgy értesítés
                      és feladat keletkezik. */}
                  <div>
                    <p className="t-label mb-2">Papírok, lejáratok</p>
                    <KotelezettsegKezelo
                      kotelezettsegek={autoHataridok}
                      emberek={emberek}
                      alapTipus="forgalmi"
                      canEdit={canEdit}
                      canCreate={canCreate}
                      canDelete={canDelete}
                      autoId={auto.id}
                    />
                  </div>

                  {/* A jármű saját papírjai fájlként: a forgalmi másolata, a
                      biztosítási kötvény - a lejáratokat a fenti kötelezettség-
                      szerkesztő kezeli, itt maga a dokumentum van (lásd backend
                      services/attachments.py "auto" entitás). */}
                  <div>
                    <p className="t-label mb-2">Dokumentumok (forgalmi, biztosítás…)</p>
                    <PapirFeltoltes
                      entityType="auto"
                      entityId={auto.id}
                      canEdit={canEdit}
                      canDelete={canDelete}
                      uresSzoveg="Nincs feltöltött dokumentum ehhez az autóhoz."
                    />
                  </div>

                  {/* Teendők az autóhoz - pipálható lista (a felhasználó
                      kérése): "vinni műszakira", "izzót cserélni"... */}
                  <div>
                    <p className="t-label mb-2">Teendők</p>
                    <AutoTeendok
                      autoId={auto.id}
                      teendok={auto.teendok ?? []}
                      emberek={teendoEmberek}
                      canEdit={canEdit}
                      canDelete={canDelete}
                    />
                  </div>

                  <div>
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="t-label">Költések</p>
                      <p className="text-[12px] text-text-muted">
                        Ezek a sorok a Pénzügy → Kiadások közt is ott vannak (a még ki nem fizetett számla a kifizetése után, addig az Utalásra várók közt).
                      </p>
                    </div>
                    {auto.kiadasok.length === 0 ? (
                      <p className="text-[12.5px] text-text-muted">Erre az autóra még nincs költés felvezetve.</p>
                    ) : (
                      <div className="overflow-x-auto">
                      <table className="os-table min-w-full border-collapse text-[12.5px]">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="py-1 pr-4 text-left font-medium text-text-muted">Mikor</th>
                            <th className="py-1 pr-4 text-left font-medium text-text-muted">Mire</th>
                            <th className="py-1 pr-4 text-right font-medium text-text-muted">Nettó</th>
                            <th className="py-1 pr-4 text-right font-medium text-text-muted">Bruttó</th>
                            <th className="py-1 pr-4 text-left font-medium text-text-muted">Fizetés</th>
                            <th className="py-1 pr-4 text-left font-medium text-text-muted">Dokumentum</th>
                            <th className="py-1 text-right font-medium text-text-muted" />
                          </tr>
                        </thead>
                        <tbody>
                          {auto.kiadasok.map((kiadas) => (
                            <tr key={kiadas.id} className="border-b border-border last:border-0">
                              <td className="py-1.5 pr-4 whitespace-nowrap text-text-secondary">
                                {kiadas.datum ? huDatum(kiadas.datum) : "–"}
                              </td>
                              <td className="py-1.5 pr-4 text-text-primary">
                                {kiadas.megnevezes}
                                {kiadas.megjegyzes && (
                                  <span className="block text-[11.5px] text-text-muted">{kiadas.megjegyzes}</span>
                                )}
                                {/* Melyik projekt költsége - kattintva a kód
                                    adatlapjára visz. */}
                                {kiadas.projektkod && kiadas.project_code_id && (
                                  <a
                                    href={`/projektek/project-kodok/${kiadas.project_code_id}`}
                                    className="block text-[11.5px] text-text-accent hover:underline"
                                  >
                                    {kiadas.projektkod}
                                  </a>
                                )}
                              </td>
                              {/* A NETTÓ a hangsúlyos: az összesítés (és
                                  minden elszámolás) abból megy - lásd backend
                                  services/elszamolas.py. A bruttó halványabb,
                                  de ott van: annyi megy ki a számláról. */}
                              <td className="py-1.5 pr-4 text-right tabular-nums text-text-primary">
                                {kiadas.netto != null ? formatHuf(kiadas.netto) : "–"}
                                {kiadas.plusz_afa && <span className="ml-1 text-[11px] text-text-muted">+ ÁFA</span>}
                              </td>
                              <td className="py-1.5 pr-4 text-right tabular-nums text-text-secondary">
                                {kiadas.osszeg != null
                                  ? kiadas.penznem === "HUF"
                                    ? formatHuf(kiadas.osszeg)
                                    : `${kiadas.osszeg.toLocaleString("hu-HU")} ${kiadas.penznem}`
                                  : "–"}
                              </td>
                              <td className="py-1.5 pr-4 text-text-muted">
                                {kiadas.fizetesi_mod ?? "–"}
                                {/* A MÉG KI NEM FIZETETT számla (pl. szerviz):
                                    a határidő, és a "Fizetés" gomb, ami a
                                    fizetés dátumát is bekérdezi - ugyanaz, mint
                                    a projektkód kiadásainál. */}
                                {(!kiadas.kesz || kiadas.fizetes_hatarideje) && (
                                  <span className="mt-1 flex flex-wrap items-center gap-2">
                                    {canEdit ? (
                                      <KifizetveDatummal
                                        patchPath={`/api/v1/autok/kiadasok/${kiadas.id}`}
                                        kifizetve={kiadas.kesz}
                                      />
                                    ) : (
                                      <StatusBadge
                                        label={kiadas.kesz ? "Kifizetve" : "Fizetésre vár"}
                                        tone={kiadas.kesz ? "success" : "warning"}
                                      />
                                    )}
                                    {!kiadas.kesz && kiadas.fizetes_hatarideje && (
                                      <span
                                        className={`whitespace-nowrap text-[11.5px] ${
                                          kiadas.fizetes_hatarideje < new Date().toISOString().slice(0, 10)
                                            ? "text-text-danger"
                                            : "text-text-muted"
                                        }`}
                                      >
                                        határidő: {huDatum(kiadas.fizetes_hatarideje)}
                                      </span>
                                    )}
                                  </span>
                                )}
                              </td>
                              {/* A bizonylat (számla, blokk) magához a
                                  kiadás-sorhoz tartozik - az AUTÓK oldalának
                                  jogosultságával (lásd backend
                                  routes/autok.py KIADAS_ENTITAS). */}
                              <td className="py-1.5 pr-4">
                                {kiadas.nincs_szamla ? (
                                  // Készpénzes FEKETE kiadás: nem lesz
                                  // számlája, tehát feltölteni sincs mit.
                                  <StatusBadge label="Nincs számla, nem is lesz" tone="danger" />
                                ) : (
                                <PapirFeltoltes
                                  entityType="autoKiadas"
                                  entityId={kiadas.id}
                                  kategoria="szamla"
                                  canEdit={canEdit}
                                  canDelete={canDelete}
                                  uresSzoveg="–"
                                />
                                )}
                              </td>
                              <td className="py-1.5 text-right">
                                {canDelete && (
                                  <button
                                    type="button"
                                    onClick={() => koltsegTorles(kiadas.id, kiadas.megnevezes)}
                                    disabled={busy}
                                    title="Költés törlése"
                                    className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                                  >
                                    <Trash2 size={12} />
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      </div>
                    )}
                    {canCreate &&
                      (koltsegUrlap === auto.id ? (
                        <div className="mt-3">
                          <KoltsegUrlap autoId={auto.id} onKesz={() => setKoltsegUrlap(null)} />
                        </div>
                      ) : (
                        <button type="button" onClick={() => setKoltsegUrlap(auto.id)} className="btn btn-ghost mt-3">
                          <Plus size={13} /> Költés hozzáadása
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {canCreate &&
        (ujAuto ? (
          <div className="fade-in mt-4 flex flex-wrap items-end gap-3 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
            <label className="flex flex-col gap-1.5">
              <span className="t-label">Rendszám *</span>
              <input value={rendszam} onChange={(e) => setRendszam(e.target.value)} className={`${inputClass} w-[140px]`} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="t-label">Megnevezés</span>
              <input
                value={megnevezes}
                onChange={(e) => setMegnevezes(e.target.value)}
                placeholder="pl. Ford Transit – gyártásos"
                className={`${inputClass} w-[240px]`}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="t-label">Felelős</span>
              <KeresosSelect
                value={felelosId || null}
                options={emberek.map((e) => ({ value: String(e.id), label: e.full_name }))}
                onChange={setFelelosId}
                placeholder="–"
                className="w-[200px]"
              />
            </label>
            <button type="button" onClick={autoMentes} disabled={busy} className="btn btn-primary">
              {busy ? "Mentés…" : "Hozzáadás"}
            </button>
            <button type="button" onClick={() => setUjAuto(false)} className="btn btn-ghost">
              Mégse
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setUjAuto(true)} className="btn btn-primary mt-4">
            <Plus size={13} /> Autó felvétele
          </button>
        ))}
    </div>
  );
}
