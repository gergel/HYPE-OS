"use client";

import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { KeresosSelect, type KeresosOpcio } from "@/components/KeresosSelect";
import { UjAlvallalkozoDialog, type UjAlvallalkozoElotoltes } from "@/components/UjAlvallalkozoDialog";
import { UjFajlValaszto } from "@/components/UjFajlValaszto";
import { toltsdFelAFajlokat } from "@/lib/csatolmany";

/** Szám-mező GÉPELÉS KÖZBENI ezres tagolása (a felhasználó kérése - pl. a
 * projekt kiadás nettó összegénél az 500000 "500 000"-ként látsszon már
 * beíráskor is). A values-ban a NYERS számszöveg él (azt kapja a Number() a
 * mentésnél), csak a megjelenítés tagolt; a tizedes vesszővel írható. */
function szamMegjelenites(nyers: string): string {
  if (!nyers) return "";
  const [egesz = "", tizedes] = nyers.split(".");
  const elojel = egesz.startsWith("-") ? "-" : "";
  const tagolt = egesz.replace(/\D/g, "").replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return elojel + tagolt + (tizedes !== undefined ? `,${tizedes}` : "");
}

function szamNyersre(beirt: string): string {
  // Szóközök (a saját tagolásunk is) ki, tizedes vessző -> pont, minden más
  // nem-szám karakter eldobva - így a "másolt" összegek (pl. "1 234 567 Ft")
  // is beilleszthetők.
  return beirt
    .replace(/[\s  ]/g, "")
    .replace(/,/g, ".")
    .replace(/[^0-9.-]/g, "");
}

type FieldSpec = {
  name: string;
  label: string;
  type?: "text" | "date" | "number" | "password" | "select";
  required?: boolean;
  /** "select" típusnál a legördülő opciói - pl. egy foreign key mezőhöz
   * (ügyfél/project code kiválasztása név szerint, ID begépelés helyett). */
  options?: { value: number | string; label: string }[];
  /** Előre beírt kezdőérték (pl. a projektkód "HYPE26-" előtagja) - a mező
   * ettől még szabadon átírható. Az űrlap minden megnyitásakor visszaáll rá. */
  defaultValue?: string;
  placeholder?: string;
  /** Csak akkor jelenjen meg, ha egy MÁSIK mező értéke ilyen - pl. az
   * árfolyamot csak devizás pénznemnél kérdezzük. Egy mindig ott álló,
   * legtöbbször üresen hagyott mező zajt visz az űrlapra, és azt sugallja,
   * hogy kellene kitölteni.
   *
   * SZÁNDÉKOSAN adat, nem függvény: az űrlapot szerver-komponensek állítják
   * össze (lásd penzugyek/page.tsx), egy függvényt pedig nem lehet átadni
   * kliens-komponensnek ("Functions cannot be passed directly to Client
   * Components"). */
  showIf?: { field: string; oneOf?: string[]; noneOf?: string[] };
  /** Csak akkor KÖTELEZŐ, ha egy másik mező értéke ilyen (ugyanaz a
   * feltétel-alak, mint a showIf) - pl. a kiadás dátuma külsős besorolásnál
   * nem kötelező, mert ott a szerződés/TIG készül, és a dátum majd a
   * kifizetésnél derül ki. A `required`-del együtt nem használatos: vagy
   * mindig kötelező (required), vagy feltételesen (requiredIf). */
  requiredIf?: { field: string; oneOf?: string[]; noneOf?: string[] };
  /** Gépelhető mező LEGÖRDÜLŐ javaslatokkal (datalist) - pl. az eszköz
   * kategóriája: a meglévő kategóriák közül választható, de új is beírható. */
  suggestions?: string[];
  /** Ha EBBEN a mezőben nem üres értéket választanak, egy MÁSIK mező
   * automatikusan a megadott értékre áll - pl. alvállalkozó kiválasztásakor a
   * besorolás "kulsos"-ra vált, mert enélkül a szerződés/TIG-igény csendben
   * elveszne (lásd backend models/finance.Expense.alvallalkozoi_papirt_igenyel).
   * A másik mező utána is szabadon átírható - ez csak az alapértelmezést
   * igazítja. Adat, nem függvény - ugyanazért, amiért a showIf. */
  autoSet?: { field: string; value: string };
  /** ÚJ ALVÁLLALKOZÓ felvétele a keresőből (a felhasználó kérése): a select
   * keresőjébe beírt név a lista alján "hozzáadása újként" sorral vehető
   * fel - felugró ablak nyílik minden adatával (lásd UjAlvallalkozoDialog),
   * mentés után pedig az új ember rögtön ki is választódik ebben a mezőben.
   * Adat-jelző, nem függvény - ugyanazért, amiért a showIf. */
  ujAlvallalkozo?: boolean;
};

/** Teljesül-e a mező-feltétel a mostani beírások mellett (showIf/requiredIf). */
function feltetelTeljesul(
  feltetel: { field: string; oneOf?: string[]; noneOf?: string[] },
  values: Record<string, string>,
): boolean {
  const ertek = values[feltetel.field] ?? "";
  if (feltetel.oneOf && !feltetel.oneOf.includes(ertek)) return false;
  if (feltetel.noneOf && feltetel.noneOf.includes(ertek)) return false;
  return true;
}

/** Látszik-e ez a mező a mostani beírások mellett (lásd FieldSpec.showIf)? */
function lathato(f: FieldSpec, values: Record<string, string>): boolean {
  return !f.showIf || feltetelTeljesul(f.showIf, values);
}

/** Kötelező-e ez a mező MOST (lásd FieldSpec.required és requiredIf)? */
function kotelezo(f: FieldSpec, values: Record<string, string>): boolean {
  if (f.requiredIf) return feltetelTeljesul(f.requiredIf, values);
  return Boolean(f.required);
}

/** A mezők kezdőértékei - az űrlap minden megnyitásakor ezzel indul. */
function kezdoErtekek(fields: FieldSpec[]): Record<string, string> {
  return Object.fromEntries(
    fields.filter((f) => f.defaultValue !== undefined).map((f) => [f.name, f.defaultValue as string]),
  );
}

/** Kis inline form egy új, kapcsolódó rekord létrehozásához (pl. egy projekthez új
 * utómunka), a szükséges foreign key-ket előre kitöltve (`presetFields`) küldi -
 * a felhasználó csak a néhány releváns mezőt látja, nem a teljes ~140 mezős sémát. */
export function QuickCreateForm({
  postPath,
  fields,
  presetFields = {},
  addLabel = "+ Új hozzáadása",
  submitLabel = "Hozzáadás",
  fajlFeltoltes,
  aiKitoltes,
}: {
  postPath: string;
  fields: FieldSpec[];
  presetFields?: Record<string, unknown>;
  addLabel?: string;
  submitLabel?: string;
  /** Ha meg van adva, az űrlapon fájl is választható, és a MENTÉS UTÁN a
   * létrejött rekordhoz töltődik fel (a csatolmány-végpontnak kell az id,
   * lásd lib/csatolmany.toltsdFelAFajlokat). Pl. kiadás-felvitelnél a
   * számla/blokk - akkor van kéznél, amikor a tételt felvezetik. */
  fajlFeltoltes?: {
    entityType: string;
    kategoria?: string;
    cimke?: string;
    sugo?: string;
    /** "NINCS SZÁMLA" kapcsoló (a felhasználó kérése): bejelölve a fájl-
     * választó eltűnik, és a mentés a megadott nevű logikai mezőt küldi
     * igazra (pl. Expense.nincs_szamla) - a listák így nem hiányzó
     * számlaként mutatják a tételt. */
    nincsKapcsolo?: { name: string; cimke?: string };
  };
  /** AI-s KITÖLTÉS dokumentumból (a felhasználó kérése): a feltöltött
   * szerződést/számlát a szerver kiolvassa (lásd backend
   * services/kiadas_kiolvasas.py), és a visszaadott mezőkkel előtölti az
   * űrlapot - az értékek szabadon javíthatók, a mentés a megszokott.
   * A dokumentum a csatolmányok közé is bekerül (fajlFeltoltes esetén). */
  aiKitoltes?: { endpoint: string; cimke?: string };
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>(() => kezdoErtekek(fields));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fajlok, setFajlok] = useState<File[]>([]);
  // A "nincs számla" kapcsoló állása (lásd fajlFeltoltes.nincsKapcsolo).
  const [nincsFajl, setNincsFajl] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiUzenet, setAiUzenet] = useState<string | null>(null);
  // A router.refresh() átmenetben fut, hogy TUDJUK, mikor ért végig: az űrlap
  // addig nyitva marad "a lista frissül" jelzéssel, és csak akkor záródik be,
  // amikor az új sor már tényleg ott van a listában. Enélkül (pl. a nehéz
  // projektkód-listánál) másodpercekig úgy nézett ki, mintha a mentés nem
  // csinált volna semmit, és kézzel kellett frissíteni az oldalt.
  const [frissites, startFrissites] = useTransition();
  const [zarasFuggoben, setZarasFuggoben] = useState(false);
  // ÚJ ALVÁLLALKOZÓ felvétele a keresőből (lásd FieldSpec.ujAlvallalkozo):
  // melyik mezőből nyílt az ablak, milyen névvel - és az AI-s kitöltésnél a
  // szerződésből kiolvasott előtöltő adatokkal (a felhasználó kérése).
  const [ujAlvMezo, setUjAlvMezo] = useState<{
    mezoNev: string;
    nev: string;
    kezdoAdatok?: UjAlvallalkozoElotoltes;
  } | null>(null);
  // A most felvett emberek opciói mezőnként: a szerver-oldali lista csak a
  // router.refresh() után frissül, addig ebből tudja a select a nevet kiírni.
  const [ujOpciok, setUjOpciok] = useState<Record<string, KeresosOpcio[]>>({});
  // SZÁRMAZTATOTT nyitottság (nem effect): amint a frissítés-átmenet véget
  // ért, az űrlap zárva renderelődik - a zarasFuggoben jelzőt a következő
  // megnyitás nullázza.
  const nyitva = open && !(zarasFuggoben && !frissites);

  // A rejtett mezők nem is léteznek: se validálni, se elküldeni nem kell őket.
  const lathatoMezok = fields.filter((f) => lathato(f, values));

  /** Egy mező új értéke - az autoSet-tel összekapcsolt mezővel együtt
   * (lásd FieldSpec.autoSet). */
  function mezoValtozas(f: FieldSpec, ertek: string) {
    setValues((v) => {
      const kovetkezo = { ...v, [f.name]: ertek };
      if (f.autoSet && ertek) kovetkezo[f.autoSet.field] = f.autoSet.value;
      return kovetkezo;
    });
  }

  /** A feltöltött dokumentum kiolvastatása és az űrlap előtöltése (lásd az
   * aiKitoltes propot). Csak a ténylegesen kiolvasott (nem null/üres) és az
   * űrlapon LÉTEZŐ mezőket írjuk be - a többi marad, ahogy volt. */
  async function aiKitolt(fajl: File) {
    if (!aiKitoltes) return;
    setAiBusy(true);
    setAiUzenet(null);
    try {
      const fd = new FormData();
      fd.append("file", fajl);
      const res = await authFetch(aiKitoltes.endpoint, { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setAiUzenet(`Nem sikerült kiolvasni: ${detail?.detail ?? res.status}`);
        return;
      }
      const adatok = (await res.json()) as Record<string, unknown> & {
        alvallalkozo?: { id: number; full_name: string } | null;
        alvallalkozo_adatok?: (UjAlvallalkozoElotoltes & { full_name?: string }) | null;
      };
      const mezoNevek = new Set(fields.map((f) => f.name));
      const mezoSzerint = new Map(fields.map((f) => [f.name, f]));
      let beirt = 0;
      setValues((elozo) => {
        const kovetkezo = { ...elozo };
        for (const [nev, ertek] of Object.entries(adatok)) {
          if (!mezoNevek.has(nev)) continue;
          if (ertek === null || ertek === undefined || ertek === "" || typeof ertek === "object") continue;
          kovetkezo[nev] = String(ertek);
          beirt++;
          // Az autoSet lánc itt is fusson le (pl. alvállalkozó kiválasztása
          // -> a besorolás külsősre vált), mint a kézi kiválasztásnál.
          const spec = mezoSzerint.get(nev);
          if (spec?.autoSet) kovetkezo[spec.autoSet.field] = spec.autoSet.value;
        }
        return kovetkezo;
      });
      // A dokumentum a csatolmányok közé is bekerül (pl. számla/blokk) -
      // mentéskor a létrejött tételhez töltődik fel, nem kell kétszer
      // kiválasztani ugyanazt a fájlt.
      if (fajlFeltoltes) setFajlok((elozo) => (elozo.some((f) => f === fajl) ? elozo : [...elozo, fajl]));
      // ALVÁLLALKOZÓ (a felhasználó kérése): ha a kiolvasott partner megvan a
      // meglévők közt, ki is választjuk (a neve a helyi opciók közé kerül,
      // amíg a szerver-lista frissül); ha nincs, az "Új alvállalkozó" ablak
      // nyílik a kiolvasott adatokkal előtöltve - csak a hiányzót kell pótolni.
      const alvMezo = fields.find((f) => f.ujAlvallalkozo);
      if (alvMezo && adatok.alvallalkozo) {
        const { id, full_name } = adatok.alvallalkozo;
        setUjOpciok((o) => ({
          ...o,
          [alvMezo.name]: (o[alvMezo.name] ?? []).some((opc) => opc.value === String(id))
            ? (o[alvMezo.name] ?? [])
            : [...(o[alvMezo.name] ?? []), { value: String(id), label: full_name }],
        }));
        setAiUzenet(`Kiolvasva (${beirt} mező) – alvállalkozó: ${full_name}. Ellenőrizd az értékeket.`);
      } else if (alvMezo && adatok.alvallalkozo_adatok) {
        const eloToltes = adatok.alvallalkozo_adatok;
        setUjAlvMezo({
          mezoNev: alvMezo.name,
          nev: eloToltes.full_name || "",
          kezdoAdatok: eloToltes,
        });
        setAiUzenet(
          `Kiolvasva (${beirt} mező). Az alvállalkozó még nincs a rendszerben – az adatai előtöltve, pótold a hiányzókat.`,
        );
      } else {
        setAiUzenet(
          beirt > 0
            ? `Kiolvasva (${beirt} mező kitöltve) – ellenőrizd az értékeket mentés előtt.`
            : "A dokumentumból nem sikerült mezőt kiolvasni.",
        );
      }
    } catch (err) {
      setAiUzenet(`Nem sikerült kiolvasni (hálózati hiba): ${err}`);
    } finally {
      setAiBusy(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    // Ne csak a böngésző natív "required" tooltipjére hagyatkozzunk - az
    // könnyen észrevétlen marad (pl. ha a mező máshova görgetve van), és
    // ilyenkor a kattintás úgy nézett ki, mintha semmi nem történt volna
    // (nem ment ki kérés a szerver felé). Explicit, jól látható hibaüzenetet
    // adunk ilyenkor is.
    const missing = lathatoMezok.filter((f) => kotelezo(f, values) && !values[f.name]?.trim());
    if (missing.length > 0) {
      setError(`Kötelező mező hiányzik: ${missing.map((f) => f.label).join(", ")}`);
      return;
    }
    setBusy(true);
    try {
      const body: Record<string, unknown> = { ...presetFields };
      if (fajlFeltoltes?.nincsKapcsolo && nincsFajl) body[fajlFeltoltes.nincsKapcsolo.name] = true;
      for (const f of lathatoMezok) {
        if (!values[f.name]) continue;
        const isNumericSelect = f.type === "select" && typeof f.options?.[0]?.value === "number";
        body[f.name] = f.type === "number" || isNumericSelect ? Number(values[f.name]) : values[f.name];
      }
      const res = await authFetch(postPath, { method: "POST", body: JSON.stringify(body) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      // A kiválasztott fájlok a MOST létrejött rekordhoz töltődnek fel. Ha a
      // feltöltés elhasal, a rekord attól még megvan - ezt mondjuk is, és az
      // űrlap nyitva marad, hogy a hibaüzenet ne tűnjön el.
      if (fajlFeltoltes && fajlok.length > 0) {
        const letrejott = (await res.json().catch(() => null)) as { id?: number } | null;
        if (letrejott?.id) {
          const hiba = await toltsdFelAFajlokat(
            fajlFeltoltes.entityType,
            letrejott.id,
            fajlok,
            fajlFeltoltes.kategoria ?? "szamla",
          );
          if (hiba) {
            setError(hiba);
            setFajlok([]);
            router.refresh();
            return;
          }
        }
      }
      setValues(kezdoErtekek(fields));
      setFajlok([]);
      setNincsFajl(false);
      startFrissites(() => router.refresh());
      setZarasFuggoben(true);
    } catch (err) {
      setError(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!nyitva) {
    return (
      <button
        type="button"
        // Nyitáskor is visszaállunk a kezdőértékekre: egy félbehagyott,
        // "Mégse"-vel bezárt űrlap után ne a régi gépelés fogadjon.
        onClick={() => {
          setValues(kezdoErtekek(fields));
          setFajlok([]);
          setNincsFajl(false);
          setError(null);
          setZarasFuggoben(false);
          setOpen(true);
        }}
        className="mb-2 text-[13px] text-text-accent hover:underline"
      >
        {addLabel}
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="fade-in mb-4 flex flex-wrap items-end gap-4 rounded-[var(--radius-lg)] border border-border bg-surface-3 p-4"
    >
      {/* AI-s kitöltés dokumentumból (a felhasználó kérése): a szerződés/
          számla feltöltése után a mezők maguktól kitöltődnek - és a fájl a
          csatolmányok közé is bekerül. Az értékek mentés előtt javíthatók. */}
      {aiKitoltes && (
        <div className="flex w-full flex-wrap items-center gap-2">
          <label
            className={`inline-flex cursor-pointer items-center gap-1.5 rounded-[var(--radius)] border border-dashed border-border px-3 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-2 ${
              aiBusy ? "pointer-events-none opacity-60" : ""
            }`}
          >
            {aiBusy ? "Kiolvasás…" : (aiKitoltes.cimke ?? "Kitöltés szerződésből / számlából (AI)")}
            <input
              type="file"
              accept="application/pdf,image/*"
              className="hidden"
              disabled={aiBusy || busy}
              onChange={(e) => {
                const fajl = e.target.files?.[0];
                // Ugyanaz a fájl újra kiválasztható legyen (pl. újrapróbálás).
                e.target.value = "";
                if (fajl) void aiKitolt(fajl);
              }}
            />
          </label>
          {aiUzenet && <span className="text-[12px] text-text-accent">{aiUzenet}</span>}
        </div>
      )}
      {lathatoMezok.map((f) => (
        <div key={f.name} className="flex flex-col gap-1">
          <label className="t-label">
            {f.label}
            {kotelezo(f, values) && " *"}
          </label>
          {f.type === "select" ? (
            <KeresosSelect
              value={values[f.name] || null}
              options={[
                ...(f.options ?? []).map((opt) => ({ value: String(opt.value), label: opt.label })),
                // A most felvett emberek: a szerver-lista frissüléséig innen
                // jön a nevük (lásd ujOpciok).
                ...(ujOpciok[f.name] ?? []),
              ]}
              onChange={(ertek) => mezoValtozas(f, ertek)}
              placeholder="Válassz…"
              className="min-w-[200px]"
              onUjFelvetel={f.ujAlvallalkozo ? (nev) => setUjAlvMezo({ mezoNev: f.name, nev }) : undefined}
            />
          ) : (
            <>
              <input
                // Szám-mezőnél szöveg-input tagolt megjelenítéssel (a natív
                // type="number" nem enged szóközöket) - a values-ban a nyers
                // szám marad, csak a kijelzés ezres tagolású.
                type={f.type === "number" ? "text" : (f.type ?? "text")}
                inputMode={f.type === "number" ? "decimal" : undefined}
                required={kotelezo(f, values)}
                placeholder={f.placeholder}
                value={f.type === "number" ? szamMegjelenites(values[f.name] ?? "") : (values[f.name] ?? "")}
                onChange={(e) =>
                  mezoValtozas(f, f.type === "number" ? szamNyersre(e.target.value) : e.target.value)
                }
                list={f.suggestions ? `qcf-${f.name}-javaslatok` : undefined}
                className="field"
              />
              {f.suggestions && (
                <datalist id={`qcf-${f.name}-javaslatok`}>
                  {f.suggestions.map((j) => (
                    <option key={j} value={j} />
                  ))}
                </datalist>
              )}
            </>
          )}
        </div>
      ))}
      {fajlFeltoltes && (
        <div className="flex flex-col gap-1.5">
          {/* Bejelölt "nincs számla" mellett a fájl-választó el is tűnik -
              nincs értelme fájlt kérni ahhoz, amihez nem lesz. */}
          {!(fajlFeltoltes.nincsKapcsolo && nincsFajl) && (
            <UjFajlValaszto
              fajlok={fajlok}
              onValtozas={setFajlok}
              disabled={busy || zarasFuggoben}
              cimke={fajlFeltoltes.cimke ?? "Számla / blokk"}
              sugo={fajlFeltoltes.sugo ?? "Nem kötelező – utólag is feltölthető a listában."}
            />
          )}
          {fajlFeltoltes.nincsKapcsolo && (
            <label className="flex cursor-pointer items-center gap-1.5 text-[12.5px] text-text-secondary">
              <input
                type="checkbox"
                checked={nincsFajl}
                disabled={busy || zarasFuggoben}
                onChange={(e) => {
                  setNincsFajl(e.target.checked);
                  if (e.target.checked) setFajlok([]);
                }}
                className="cursor-pointer"
              />
              {fajlFeltoltes.nincsKapcsolo.cimke ?? "Nincs számla (nem is lesz)"}
            </label>
          )}
        </div>
      )}
      <button
        type="submit"
        disabled={busy || zarasFuggoben}
        className="btn btn-primary"
      >
        {zarasFuggoben ? "Mentve – a lista frissül…" : busy ? "Mentés…" : submitLabel}
      </button>
      <button type="button" onClick={() => { setZarasFuggoben(false); setOpen(false); }} className="text-[13px] text-text-muted hover:text-text-primary">
        Mégse
      </button>
      {error && <p className="w-full text-[12px] text-text-danger">{error}</p>}
      {/* Új alvállalkozó felvétele a kereső "hozzáadása újként" sorából -
          mentés után az új ember rögtön ki is választódik a mezőben (az
          autoSet lánccal együtt, tehát pl. a besorolás is külsősre vált). */}
      {ujAlvMezo && (
        <UjAlvallalkozoDialog
          kezdoNev={ujAlvMezo.nev}
          kezdoAdatok={ujAlvMezo.kezdoAdatok}
          onMegse={() => setUjAlvMezo(null)}
          onKesz={(id, nev) => {
            const mezoSpec = fields.find((f) => f.name === ujAlvMezo.mezoNev);
            setUjOpciok((o) => ({
              ...o,
              [ujAlvMezo.mezoNev]: [...(o[ujAlvMezo.mezoNev] ?? []), { value: String(id), label: nev }],
            }));
            if (mezoSpec) mezoValtozas(mezoSpec, String(id));
            setUjAlvMezo(null);
            // A szerver-oldali munkatárs-lista is tudjon róla - a nyitott
            // űrlap beírt értékei kliens-állapotban vannak, megmaradnak.
            router.refresh();
          }}
        />
      )}
    </form>
  );
}
