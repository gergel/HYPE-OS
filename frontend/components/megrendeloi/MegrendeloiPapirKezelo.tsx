"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { IndoklasDialog } from "@/components/IndoklasDialog";
import { KeresosSelect } from "@/components/KeresosSelect";
import { KuldesEllenorzo, type EllenorzoSor } from "@/components/KuldesEllenorzo";
import { SajatPapirFeltoltes } from "@/components/SajatPapirFeltoltes";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";
import { authFetch } from "@/lib/authFetch";
import { penznemKod, penzzel } from "@/lib/penz";
import type {
  MegrendeloiElotoltes,
  MegrendeloiKontakt,
  MegrendeloiPapir,
  MegrendeloiPapirFajta,
} from "@/lib/api";

type Urlap = {
  ceg_neve: string;
  szekhely: string;
  adoszam: string;
  kepviselo: string;
  nyilvantartasi_szam: string;
  email: string;
  megbizas_targya: string;
  projekt_nev: string;
  teljesites_szoveg: string;
  netto_osszeg: string;
  plusz_afa: boolean;
  keltezes: string;
  megjegyzes: string;
  client_id: number | null;
  contact_id: number | null;
  keretszerzodes_id: number | null;
};

const URES: Urlap = {
  ceg_neve: "",
  szekhely: "",
  adoszam: "",
  kepviselo: "",
  nyilvantartasi_szam: "",
  email: "",
  megbizas_targya: "",
  projekt_nev: "",
  teljesites_szoveg: "",
  netto_osszeg: "",
  plusz_afa: false,
  keltezes: "",
  megjegyzes: "",
  client_id: null,
  contact_id: null,
  keretszerzodes_id: null,
};

function urlapPapirbol(p: MegrendeloiPapir): Urlap {
  return {
    ceg_neve: p.ceg_neve ?? "",
    szekhely: p.szekhely ?? "",
    adoszam: p.adoszam ?? "",
    kepviselo: p.kepviselo ?? "",
    nyilvantartasi_szam: p.nyilvantartasi_szam ?? "",
    email: p.email ?? "",
    megbizas_targya: p.megbizas_targya ?? "",
    projekt_nev: p.projekt_nev ?? "",
    teljesites_szoveg: p.teljesites_szoveg ?? "",
    netto_osszeg: p.netto_osszeg != null ? String(p.netto_osszeg) : "",
    plusz_afa: p.plusz_afa ?? false,
    keltezes: p.keltezes ?? "",
    megjegyzes: p.megjegyzes ?? "",
    client_id: p.client_id,
    contact_id: p.contact_id,
    keretszerzodes_id: p.keretszerzodes_id,
  };
}

function urlapElotoltesbol(e: MegrendeloiElotoltes): Urlap {
  return {
    ...URES,
    ceg_neve: e.ceg_neve ?? "",
    szekhely: e.szekhely ?? "",
    adoszam: e.adoszam ?? "",
    kepviselo: e.kepviselo ?? "",
    nyilvantartasi_szam: e.nyilvantartasi_szam ?? "",
    email: e.email ?? "",
    megbizas_targya: e.megbizas_targya ?? "",
    projekt_nev: e.projekt_nev ?? "",
    teljesites_szoveg: e.teljesites_szoveg ?? "",
    netto_osszeg: e.netto_osszeg != null ? String(e.netto_osszeg) : "",
    plusz_afa: e.plusz_afa ?? false,
    client_id: e.client_id,
    contact_id: e.contact_id,
    keretszerzodes_id: e.keretszerzodes_id,
  };
}

/** Bruttó = nettó * 1,27, ha plusz ÁFA-t számolunk fel - egyébként a nettóval
 * egyezik. Ugyanaz a szabály, mint az alvállalkozói papíroknál. */
function brutto(netto: string, pluszAfa: boolean): number | null {
  if (!netto.trim()) return null;
  const szam = Number(netto);
  if (Number.isNaN(szam)) return null;
  return pluszAfa ? Math.round(szam * 1.27 * 100) / 100 : szam;
}

function allapotJelzo(p: MegrendeloiPapir) {
  if (p.allapot === "Kihagyva") return <StatusBadge label="Kihagyva" tone="neutral" />;
  // Az ALÁÍRT példány a legerősebb bizonyíték: ha megvan, a papír kész -
  // bármit is mond az állapot-mező. (A backend is így zárja le a feltöltéskor,
  // lásd routes/megrendeloi_papirok.py; ez a sor arra való, hogy a RÉGI,
  // feltöltés előtti sorokon se lássunk teendőt ott, ahol nincs.)
  if (p.alairt_file_url) return <StatusBadge label="Aláírva" tone="success" />;
  if (p.allapot === "Van már papír") return <StatusBadge label="Van már papír" tone="success" />;
  if (p.allapot === "Kiküldve") return <StatusBadge label="Kiküldve, aláírásra vár" tone="warning" />;
  return <StatusBadge label={p.allapot ?? "Készítés alatt"} tone="warning" />;
}

/** A MEGRENDELŐ felé menő papír (eseti szerződés vagy TIG) kezelése egy
 * projektkódon.
 *
 * Ugyanaz a folyamat, mint az alvállalkozói oldalon (lásd
 * PerformanceCertificateManager és SubcontractorContractManager), csak a másik
 * irányba - és ezért ugyanazok a lépések is: piszkozat, generálás és kiküldés,
 * kihagyás indokkal, saját papír, végül az aláírt példány.
 *
 * A SZERZŐDŐ FELET a MEGRENDELŐK közül választjuk, és mellé a
 * kapcsolattartót (neki megy a levél). A cégadatokat a szerver tölti elő a
 * legjobb ismert forrásból - ha van élő keretszerződés az ügyféllel, onnan,
 * mert ott a cégadatok már egyszer kimentek egy aláírt papíron (lásd backend
 * services/megrendeloi_papir.szerzodo_fel_adatai). A választás után minden
 * mező szerkeszthető marad: a papírra az kerül, ami itt látszik, nem az, ami
 * az ügyfél adatlapján áll. */
export function MegrendeloiPapirKezelo({
  projectCodeId,
  fajta,
  papirok,
  ugyfelek,
  kontaktok,
  canEdit,
  canDelete = false,
  kellPapir,
  nincsPapirOka,
  penznem = "HUF",
}: {
  projectCodeId: number;
  fajta: MegrendeloiPapirFajta;
  papirok: MegrendeloiPapir[];
  /** A MEGRENDELŐK (ügyfelek), akikkel a papír szólhat. Innen választunk
   * szerződő felet - nem a keretszerződésekből: az egy másik kérdés (van-e
   * álló megállapodás), és arra a lista amúgy is szűk. Ha a választott
   * ügyféllel van élő keret, azt a szerver az előtöltéssel adja vissza. */
  ugyfelek: { id: number; nev: string }[];
  kontaktok: MegrendeloiKontakt[];
  canEdit: boolean;
  /** Az ELKEZDETT papír eldobható - amíg csak készül, egy rossz adattal
   * elindított szerződést/TIG-et tiszta lappal kell tudni újrakezdeni. */
  canDelete?: boolean;
  /** Ha a projektkód kapcsolói szerint nem kell papír, csak jelezzük - a
   * meglévő papírokat attól még mutatjuk (egy régebbi bejegyzés nem tűnhet el
   * attól, hogy a kapcsolót átbillentették). */
  kellPapir: boolean;
  /** MIÉRT nem kell papír, ha nem a kapcsolók miatt (pl. elmaradt esemény).
   * Az ok kiírása nem díszítés: enélkül a "nem kell papír" mondat mögött nem
   * látszik, hogy honnan jön - és a felhasználó a kapcsolókat kezdi keresni,
   * amiken nincs is mit átállítani. */
  nincsPapirOka?: string;
  /** Milyen pénznemben vállaltuk a munkát (a projektkód `penznem` mezője).
   * A papíron AZ az összeg áll, amiben megállapodtunk - ha a megbízás euróban
   * szól, a szerződésen és a TIG-en is euró a helyes, nem forint. A bevétel
   * ettől még forintban keletkezik (lásd backend services/penznem.py). */
  penznem?: string;
}) {
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const [nyitva, setNyitva] = useState(false);
  const [szerkesztett, setSzerkesztett] = useState<MegrendeloiPapir | null>(null);
  const [urlap, setUrlap] = useState<Urlap>(URES);
  const [toltodik, setToltodik] = useState(false);
  const [munka, setMunka] = useState<"mentes" | "kuldes" | "kihagyas" | null>(null);
  const [kihagyasNyitva, setKihagyasNyitva] = useState(false);
  const [kuldesNyitva, setKuldesNyitva] = useState(false);
  // Van-e a választott megrendelővel ÉLŐ keretszerződés. Nem tiltás, csak
  // figyelmeztetés: a keret alatt eseti szerződés nem kell (a TIG viszont
  // igen), és jobb ezt a papír megírása ELŐTT tudni.
  const [eloKeret, setEloKeret] = useState(false);

  const cimke = fajta === "szerzodes" ? "megrendelői szerződés" : "teljesítési igazolás";
  // A címkékben a KÓD álljon ("EUR"), ne a Notionből örökölt szabad szöveg
  // ("Forint") - lásd lib/penz.penznemKod.
  const valutaKod = penznemKod(penznem);
  const dolgozik = munka !== null;
  const bruttoOsszeg = brutto(urlap.netto_osszeg, urlap.plusz_afa);

  function frissit<K extends keyof Urlap>(kulcs: K, ertek: Urlap[K]) {
    setUrlap((elozo) => ({ ...elozo, [kulcs]: ertek }));
  }

  /** Új papír: a szerverről kérjük az előtöltést, mert az tudja, honnan a
   * legjobb az adat (keretszerződés > ügyfél > projektkód örökölt mezői). */
  async function elotoltesBetoltese(params: URLSearchParams) {
    setToltodik(true);
    try {
      const res = await authFetch(
        `/api/v1/megrendeloi-papirok/${fajta}/elotoltes/${projectCodeId}?${params.toString()}`,
      );
      if (!res.ok) {
        toast("Nem sikerült betölteni a szerződő fél adatait.");
        return null;
      }
      const adat: MegrendeloiElotoltes = await res.json();
      setUrlap(urlapElotoltesbol(adat));
      setEloKeret(adat.van_elo_keretszerzodes);
      return adat;
    } finally {
      setToltodik(false);
    }
  }

  async function ujPapir() {
    setSzerkesztett(null);
    mentettId.current = null;
    setUrlap(URES);
    setNyitva(true);
    await elotoltesBetoltese(new URLSearchParams());
  }

  function meglevoSzerkesztese(p: MegrendeloiPapir) {
    setSzerkesztett(p);
    mentettId.current = null;
    setUrlap(urlapPapirbol(p));
    setNyitva(true);
  }

  function bezar() {
    setNyitva(false);
    setSzerkesztett(null);
    mentettId.current = null;
    setUrlap(URES);
  }

  /** A szerződő fél cseréje: az előtöltést ÚJRA lekérjük, hogy a cégadatok is
   * a most választott forrásból jöjjenek - különben a régi fél adószáma
   * maradna az új fél nevén. */
  async function felValtas(mezo: "client_id" | "contact_id", ertek: number | null) {
    // ÜRESRE állításnál nem kérünk új előtöltést: az a projektkód ügyfelére
    // esne vissza, tehát a most kivett felet azonnal visszatenné. Csak a
    // választást töröljük - a már beírt cégadatokhoz nem nyúlunk, azok
    // lehetnek kézzel javítva.
    if (ertek === null) {
      setUrlap((elozo) =>
        mezo === "client_id"
          ? { ...elozo, client_id: null, contact_id: null }
          : { ...elozo, contact_id: null },
      );
      return;
    }
    const params = new URLSearchParams();
    // Az ÜGYFÉL cseréjekor a kapcsolattartó nem maradhat: az egy másik cég
    // embere lenne, és neki menne ki a papír.
    const ugyfel = mezo === "client_id" ? ertek : urlap.client_id;
    const kontakt = mezo === "client_id" ? null : ertek;
    if (ugyfel != null) params.set("client_id", String(ugyfel));
    if (kontakt != null) params.set("contact_id", String(kontakt));
    // A kontakt cége adja a cégadatot, ha ügyfelet külön nem választottak.
    const kontaktSor = kontakt != null ? kontaktok.find((k) => k.id === kontakt) : null;
    if (ugyfel == null && kontaktSor) params.set("client_id", String(kontaktSor.client_id));

    // A megbízás tárgyát / összeget a felhasználó már átírhatta - azt NEM
    // dobjuk el a fél cseréjekor, csak a cégadatokat cseréljük.
    const megtartott = {
      megbizas_targya: urlap.megbizas_targya,
      projekt_nev: urlap.projekt_nev,
      teljesites_szoveg: urlap.teljesites_szoveg,
      netto_osszeg: urlap.netto_osszeg,
      plusz_afa: urlap.plusz_afa,
      keltezes: urlap.keltezes,
      megjegyzes: urlap.megjegyzes,
    };
    const adat = await elotoltesBetoltese(params);
    if (adat) {
      setUrlap((elozo) => ({ ...elozo, ...megtartott }));
      setEloKeret(adat.van_elo_keretszerzodes);
    }
  }

  function torzs() {
    const netto = urlap.netto_osszeg.trim() ? Number(urlap.netto_osszeg) : null;
    return {
      client_id: urlap.client_id,
      contact_id: urlap.contact_id,
      keretszerzodes_id: urlap.keretszerzodes_id,
      ceg_neve: urlap.ceg_neve || null,
      szekhely: urlap.szekhely || null,
      adoszam: urlap.adoszam || null,
      kepviselo: urlap.kepviselo || null,
      nyilvantartasi_szam: urlap.nyilvantartasi_szam || null,
      email: urlap.email || null,
      megbizas_targya: urlap.megbizas_targya || null,
      projekt_nev: urlap.projekt_nev || null,
      teljesites_szoveg: urlap.teljesites_szoveg || null,
      netto_osszeg: netto != null && !Number.isNaN(netto) ? netto : null,
      plusz_afa: urlap.plusz_afa,
      keltezes: urlap.keltezes || null,
      megjegyzes: urlap.megjegyzes || null,
    };
  }

  /** A meglévő papírt módosítjuk, ha van - így a "mentés, majd küldés"
   * kétlépéses menetből nem lesz két külön bejegyzés.
   *
   * A `szerkesztett` mellett a MOST MENTETT papírt is nézzük: a "saját papír
   * feltöltése" két HTTP-hívás (előbb az űrlap mentése, utána a fájl), és a
   * második a React állapotból még nem látná az elsőben keletkezett papírt (a
   * setState nem azonnali). Enélkül a feltöltés EGY MÁSIK, üres papírt hozott
   * létre a mentett mellé: a felhasználó egy kitöltött piszkozatot és egy
   * "Nincs megadva cég"-et kapott, ahelyett hogy az aláírt fájl rögtön a
   * kitöltött papírra került volna. Ezért ref, nem state. */
  const mentettId = useRef<number | null>(null);

  function utvonal(muvelet: string) {
    const papirId = szerkesztett?.id ?? mentettId.current;
    const qs = papirId != null ? `?papir_id=${papirId}` : "";
    return `/api/v1/megrendeloi-papirok/${fajta}/${projectCodeId}/${muvelet}${qs}`;
  }

  /** A válasz JSON-ja, vagy null, ha nem sikerült - a hívó ebből tudja meg,
   * melyik papír keletkezett/frissült. */
  async function hivas(
    url: string,
    torzsAdat: unknown,
    hibaCimke: string,
  ): Promise<Record<string, unknown> | null> {
    try {
      const res = await authFetch(url, { method: "POST", body: JSON.stringify(torzsAdat) });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`${hibaCimke}: ${reszlet?.detail ?? res.status}`);
        return null;
      }
      return ((await res.json().catch(() => ({}))) ?? {}) as Record<string, unknown>;
    } catch (err) {
      toast(`${hibaCimke} (hálózati hiba): ${err}`);
      return null;
    }
  }

  /** A saját papír feltöltése előtt is ez fut le: a fájl mellé a beírt adatok
   * (összeg, keltezés) is odakerülnek. */
  async function mentes(): Promise<boolean> {
    const valasz = await hivas(utvonal("mentes"), torzs(), "Sikertelen mentés");
    if (valasz === null) return false;
    // A további műveletek EZT a papírt folytassák, ne csináljanak újat.
    if (typeof valasz.id === "number") mentettId.current = valasz.id;
    return true;
  }

  async function mentesGomb() {
    setMunka("mentes");
    try {
      if (!(await mentes())) return;
      bezar();
      router.refresh();
    } finally {
      setMunka(null);
    }
  }

  /** Küldés előtt áttekintő: a generálás és az e-mail EGY lépés, tehát a hibás
   * adat már a megrendelőnél landol, és csak új papírral javítható. */
  function kuldesInditasa() {
    if (!urlap.netto_osszeg.trim() || Number.isNaN(Number(urlap.netto_osszeg))) {
      toast("Add meg a nettó összeget.");
      return;
    }
    setKuldesNyitva(true);
  }

  function ellenorzoSorok(): EllenorzoSor[] {
    const netto = urlap.netto_osszeg.trim() ? Number(urlap.netto_osszeg) : null;
    const sorok: EllenorzoSor[] = [
      { cimke: "Cég neve", ertek: urlap.ceg_neve },
      { cimke: "Székhely", ertek: urlap.szekhely },
      { cimke: "Adószám", ertek: urlap.adoszam },
      { cimke: "Képviselő", ertek: urlap.kepviselo },
      { cimke: "Nyilvántartási szám", ertek: urlap.nyilvantartasi_szam },
      { cimke: "Megbízás tárgya", ertek: urlap.megbizas_targya },
    ];
    if (fajta === "szerzodes") sorok.push({ cimke: "Projekt neve", ertek: urlap.projekt_nev });
    sorok.push(
      {
        cimke: "Nettó összeg",
        ertek: netto === null ? null : `${penzzel(netto, penznem)}${urlap.plusz_afa ? " + ÁFA" : ""}`,
      },
      { cimke: "Teljesítés ideje", ertek: urlap.teljesites_szoveg },
      { cimke: "Keltezés", ertek: urlap.keltezes },
    );
    return sorok;
  }

  async function kuldes() {
    setKuldesNyitva(false);
    setMunka("kuldes");
    try {
      if ((await hivas(utvonal("generalas-es-kuldes"), torzs(), "Sikertelen küldés")) === null) return;
      bezar();
      router.refresh();
    } finally {
      setMunka(null);
    }
  }

  async function kihagyas(indok: string) {
    setKihagyasNyitva(false);
    setMunka("kihagyas");
    try {
      if ((await hivas(utvonal("kihagyas"), { kihagyas_oka: indok }, "Sikertelen kihagyás")) === null) return;
      bezar();
      router.refresh();
    } finally {
      setMunka(null);
    }
  }

  async function alairtFeltoltes(papirId: number, file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await authFetch(`/api/v1/megrendeloi-papirok/${fajta}/${papirId}/alairt-fajl`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen feltöltés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      toast(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    }
  }

  /** A papír teljes törlése. A KIKÜLDÖTTNÉL is engedjük, de akkor kimondjuk,
   * hogy a dokumentum már a megrendelőnél van - a törlés csak a nyilvántartást
   * viszi, a kiküldött papírt nem hozza vissza. */
  async function torles(p: MegrendeloiPapir) {
    const kikuldve = p.allapot === "Kiküldve";
    const figyelmeztetes = kikuldve
      ? ` Ez a ${cimke} MÁR KIMENT – a törlés csak a nyilvántartásból veszi ki, a megrendelőnél lévő példányt nem vonja vissza.`
      : "";
    if (!(await confirm(`Biztosan törlöd ezt a(z) ${cimke}-t?${figyelmeztetes}`))) return;
    try {
      const res = await authFetch(`/api/v1/megrendeloi-papirok/${fajta}/${p.id}`, { method: "DELETE" });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen törlés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      toast(`A(z) ${cimke} törölve – tiszta lappal újrakezdhető.`);
      router.refresh();
    } catch (err) {
      toast(`Sikertelen törlés (hálózati hiba): ${err}`);
    }
  }

  return (
    <div className="space-y-3 text-[13px]">
      {!kellPapir && (
        <p className="text-text-muted">
          {nincsPapirOka ??
            "Ehhez a projektkódhoz a kapcsolói szerint nem kell papír – itt csak akkor van teendő, ha ez mégis változik."}
        </p>
      )}

      {papirok.length === 0 ? (
        <p className="text-text-secondary">Még nincs {cimke} ehhez a projektkódhoz.</p>
      ) : (
        <ul className="space-y-2">
          {papirok.map((p) => (
            <li key={p.id} className="rounded-[var(--radius)] border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-text-primary">{p.ceg_neve ?? "Nincs megadva cég"}</span>
                {allapotJelzo(p)}
              </div>
              {p.netto_osszeg != null && (
                <p className="mt-1 text-text-secondary">
                  {penzzel(p.netto_osszeg, penznem)}
                  {p.plusz_afa ? " + ÁFA" : ""}
                </p>
              )}
              {p.kihagyas_oka && <p className="mt-1 text-[12px] text-text-muted">{p.kihagyas_oka}</p>}
              <div className="mt-2 flex flex-wrap items-center gap-3">
                {p.file_url && (
                  <a href={p.file_url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                    Papír megnyitása
                  </a>
                )}
                {p.alairt_file_url ? (
                  <a
                    href={p.alairt_file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-accent hover:underline"
                  >
                    Aláírt példány
                  </a>
                ) : (
                  canEdit && (
                    <label className="cursor-pointer text-text-secondary hover:underline">
                      + Aláírt példány feltöltése
                      <input
                        type="file"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) alairtFeltoltes(p.id, file);
                          e.target.value = "";
                        }}
                      />
                    </label>
                  )
                )}
                {canEdit && (
                  <button
                    type="button"
                    onClick={() => meglevoSzerkesztese(p)}
                    className="text-text-secondary hover:underline"
                  >
                    Szerkesztés
                  </button>
                )}
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => torles(p)}
                    className="text-text-danger hover:underline"
                  >
                    Törlés
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {canEdit && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={ujPapir}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90"
          >
            + Új {cimke}
          </button>
          {/* KIHAGYÁS EGY KATTINTÁSSAL. Eddig ez csak a szerkesztő-űrlapon
              belül volt elérhető: aki tudta, hogy erre a munkára nem lesz
              papír, annak előbb meg kellett nyitnia egy teljes űrlapot
              (cégadatokkal, összeggel), hogy aztán ne töltse ki. A "nem lesz
              papír" nem szerkesztés, hanem döntés - ide való. */}
          <button
            type="button"
            onClick={() => setKihagyasNyitva(true)}
            disabled={dolgozik}
            className="text-[12.5px] text-text-muted hover:text-text-primary disabled:opacity-50"
          >
            {munka === "kihagyas" ? "Kihagyás…" : "Nem lesz ilyen papír (kihagyás)"}
          </button>
        </div>
      )}

      {nyitva && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6"
          onClick={dolgozik ? undefined : bezar}
        >
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">
              {szerkesztett ? `${cimke} szerkesztése` : `Új ${cimke}`}
            </h3>
            <p className="mb-4 text-[12px] text-text-muted">
              {toltodik
                ? "Szerződő fél adatainak betöltése…"
                : "A papírra az kerül, ami itt látszik – minden mező szerkeszthető."}
            </p>

            <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {/* A szerződő felet a MEGRENDELŐK közül választjuk. Korábban a
                  keretszerződések listája volt itt, ami két okból is rossz
                  kérdés: az esetek nagy részében nincs is keret (akkor a mező
                  üres, és nincs miből választani), a keret pedig épp azt
                  jelenti, hogy eseti szerződés NEM kell. Ha a választott
                  ügyféllel mégis van élő keret, azt a szerver az előtöltéssel
                  adja vissza, és lentebb ki is írjuk. */}
              <Mezo label="Megrendelő (szerződő fél)">
                <KeresosSelect
                  value={urlap.client_id != null ? String(urlap.client_id) : null}
                  // Az üres opció azért kell, mert a KeresosSelect
                  // értékkészlete zárt: nélküle egy tévesen választott felet
                  // már nem lehetne levenni a papírról.
                  options={[
                    { value: "", label: "— nincs megrendelő —" },
                    ...ugyfelek.map((u) => ({ value: String(u.id), label: u.nev })),
                  ]}
                  onChange={(v) => felValtas("client_id", v ? Number(v) : null)}
                  placeholder="Válassz megrendelőt"
                  disabled={dolgozik || toltodik}
                />
              </Mezo>
              <Mezo label="Kapcsolattartó (neki megy az e-mail)">
                <KeresosSelect
                  value={urlap.contact_id != null ? String(urlap.contact_id) : null}
                  // A választott megrendelő kontaktjaira szűkítünk: egy másik
                  // cég emberének kiküldeni ezt a papírt hiba lenne. Amíg
                  // nincs megrendelő választva, mindenki látszik.
                  options={[
                    { value: "", label: "— nincs kapcsolattartó —" },
                    ...kontaktok
                      .filter((k) => urlap.client_id == null || k.client_id === urlap.client_id)
                      .map((k) => ({
                        value: String(k.id),
                        label: k.full_name,
                        sublabel: [k.client_nev, k.email].filter(Boolean).join(" · "),
                      })),
                  ]}
                  onChange={(v) => felValtas("contact_id", v ? Number(v) : null)}
                  placeholder="Nincs kiválasztva"
                  disabled={dolgozik || toltodik}
                />
              </Mezo>
            </div>

            {eloKeret && fajta === "szerzodes" && (
              <p className="mb-4 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[12.5px] text-text-secondary">
                Ezzel a megrendelővel <b>él keretszerződés</b> – eseti szerződés emiatt nem kötelező. A teljesítési
                igazolás viszont ettől függetlenül kell.
              </p>
            )}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Mezo label="Cég neve">
                <input value={urlap.ceg_neve} onChange={(e) => frissit("ceg_neve", e.target.value)} disabled={dolgozik} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Székhely">
                <input value={urlap.szekhely} onChange={(e) => frissit("szekhely", e.target.value)} disabled={dolgozik} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Adószám">
                <input value={urlap.adoszam} onChange={(e) => frissit("adoszam", e.target.value)} disabled={dolgozik} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Képviselő">
                <input value={urlap.kepviselo} onChange={(e) => frissit("kepviselo", e.target.value)} disabled={dolgozik} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Nyilvántartási szám">
                <input
                  value={urlap.nyilvantartasi_szam}
                  onChange={(e) => frissit("nyilvantartasi_szam", e.target.value)}
                  disabled={dolgozik}
                  className={mezoOsztaly}
                />
              </Mezo>
              <Mezo label="E-mail cím (ide megy a papír)">
                <input value={urlap.email} onChange={(e) => frissit("email", e.target.value)} disabled={dolgozik} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Megbízás tárgya">
                <input
                  value={urlap.megbizas_targya}
                  onChange={(e) => frissit("megbizas_targya", e.target.value)}
                  disabled={dolgozik}
                  className={mezoOsztaly}
                />
              </Mezo>
              {fajta === "szerzodes" && (
                <Mezo label="Projekt neve">
                  <input
                    value={urlap.projekt_nev}
                    onChange={(e) => frissit("projekt_nev", e.target.value)}
                    disabled={dolgozik}
                    className={mezoOsztaly}
                  />
                </Mezo>
              )}
              {/* Szabad szöveg, nem dátum: a papírra nem mindig egy naptári
                  intervallum kerül ("2026. július", felsorolás, stb.). */}
              <Mezo label="Teljesítés ideje">
                <input
                  value={urlap.teljesites_szoveg}
                  onChange={(e) => frissit("teljesites_szoveg", e.target.value)}
                  disabled={dolgozik}
                  placeholder="Pl. 2026.07.06. – 2026.07.08. vagy 2026. július"
                  className={mezoOsztaly}
                />
              </Mezo>
              <Mezo label={`Nettó összeg (${valutaKod}) *`}>
                <input
                  type="number"
                  value={urlap.netto_osszeg}
                  onChange={(e) => frissit("netto_osszeg", e.target.value)}
                  disabled={dolgozik}
                  className={mezoOsztaly}
                />
              </Mezo>
              <Mezo label="PLUSZ áfa">
                <label className="flex items-center gap-2 py-1.5 text-text-primary">
                  <input
                    type="checkbox"
                    checked={urlap.plusz_afa}
                    onChange={(e) => frissit("plusz_afa", e.target.checked)}
                    disabled={dolgozik}
                  />
                  {urlap.plusz_afa ? "Igen" : "Nem"}
                </label>
              </Mezo>
              <Mezo label={`Bruttó összeg (${valutaKod})`}>
                <p className="py-1.5 text-text-secondary">{bruttoOsszeg != null ? penzzel(bruttoOsszeg, penznem) : "–"}</p>
              </Mezo>
              <Mezo label="Keltezés dátuma">
                <input
                  type="date"
                  value={urlap.keltezes}
                  onChange={(e) => frissit("keltezes", e.target.value)}
                  disabled={dolgozik}
                  className={mezoOsztaly}
                />
              </Mezo>
              <Mezo label="Megjegyzés">
                <input
                  value={urlap.megjegyzes}
                  onChange={(e) => frissit("megjegyzes", e.target.value)}
                  disabled={dolgozik}
                  className={mezoOsztaly}
                />
              </Mezo>
            </div>

            <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={bezar}
                disabled={dolgozik}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Bezárás
              </button>
              <button
                type="button"
                onClick={() => setKihagyasNyitva(true)}
                disabled={dolgozik}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {munka === "kihagyas" ? "Kihagyás…" : "Kihagyás (papír nélkül)"}
              </button>
              <button
                type="button"
                onClick={mentesGomb}
                disabled={dolgozik}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {munka === "mentes" ? "Mentés…" : "Mentés"}
              </button>
              {/* A generálás kihagyása: kész papír feltöltése - van, amit a
                  megrendelő ad a saját sablonjával. */}
              <SajatPapirFeltoltes
                cimke="Saját papír feltöltése"
                // Függvény, nem kész szöveg: az útvonalnak a MENTÉS UTÁN kell
                // eldőlnie, mert csak akkor derül ki az új papír azonosítója.
                feltoltesPath={() => utvonal("sajat-papir")}
                elokeszit={mentes}
                disabled={dolgozik}
                onKesz={() => {
                  bezar();
                  router.refresh();
                }}
              />
              <button
                type="button"
                onClick={kuldesInditasa}
                disabled={dolgozik}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {munka === "kuldes" ? "Küldés…" : "Generálás és küldés"}
              </button>
            </div>
          </div>
        </div>
      )}

      {kuldesNyitva && (
        <KuldesEllenorzo
          cim={`${cimke.charAt(0).toUpperCase()}${cimke.slice(1)} kiküldése`}
          bevezeto="A dokumentum ezekkel az adatokkal generálódik, és azonnal ki is megy e-mailben."
          cimzett={urlap.email || null}
          sorok={ellenorzoSorok()}
          gombCimke="Generálás és küldés"
          onMegse={() => setKuldesNyitva(false)}
          onKuld={kuldes}
        />
      )}

      {kihagyasNyitva && (
        <IndoklasDialog
          cim={`${cimke} kihagyása`}
          leiras="A projektkód e nélkül a papír nélkül zárul. Írd le, miért – egy hiányzó papírról később ebből derül ki, hogy szándékos volt."
          onMegse={() => setKihagyasNyitva(false)}
          mezoCimke="A kihagyás oka"
          placeholder="Pl. a megrendelő a saját szerződését használja, azt ő küldi"
          gombCimke="Kihagyás"
          onKesz={kihagyas}
        />
      )}
    </div>
  );
}

const mezoOsztaly =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

function Mezo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] text-text-muted">{label}</label>
      {children}
    </div>
  );
}
