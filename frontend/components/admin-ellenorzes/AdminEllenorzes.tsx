"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";
import { formatIdopont } from "@/lib/ido";
import { formatHuf } from "@/lib/penz";
import { StatusBadge } from "@/components/StatusBadge";
import { KeresosSelect } from "@/components/KeresosSelect";

const API = "/api/v1/admin-ellenorzes";

type Ful = "lara" | "naplo" | "kivetelek" | "lejart" | "osszesito" | "beallitasok";
const FULEK: { kulcs: Ful; cim: string }[] = [
  { kulcs: "lara", cim: "Lara jelzései" },
  { kulcs: "naplo", cim: "Napló" },
  { kulcs: "kivetelek", cim: "Kivételek" },
  { kulcs: "lejart", cim: "Lejárt hiányok" },
  { kulcs: "osszesito", cim: "Heti összesítő" },
  { kulcs: "beallitasok", cim: "Beállítások" },
];

type Jelzes = {
  id: number;
  szabaly: string;
  szint: string;
  cim: string;
  leiras: string | null;
  link: string | null;
  letrejott_at: string;
  lezarva_at: string | null;
};
type NaploSor = {
  id: number;
  letrejott_at: string;
  employee_id: number | null;
  ki: string;
  leiras: string;
  kivetel: boolean;
  adat: Record<string, unknown>;
  link: string | null;
};
type Kivetel = {
  kulcs: string;
  tipus: string;
  fel: string;
  projekt: string;
  projektek_db: number;
  indok: string | null;
  figyelmeztetes: string | null;
  osszeg: number | null;
  link: string | null;
  ki: string | null;
  mikor: string | null;
  modositva_at: string | null;
  dontes: "rendben" | "visszadobva" | null;
  dontes_megjegyzes: string | null;
};
type Lejart = {
  kulcs: string;
  projekt: string;
  forgatas_datuma: string | null;
  fel: string;
  dokumentum: string;
  allapot: string;
  eltelt_nap: number;
  hatarido_nap: number;
  keses_nap: number;
  link: string;
};
type Osszesito = {
  hetek: Record<string, number | string>[];
  csoportok: Record<string, string>;
  szamok: { atnezetlen_kivetel: number; lejart_hiany: number; nyitott_jelzes: number };
};
type Beallitas = {
  figyelt_employee_id: number | null;
  figyelt_nev: string | null;
  lara_figyeles: boolean;
  hataridok: Record<string, number>;
  utolso_futas_at: string | null;
};

const HATARIDO_CIMKEK: Record<string, string> = {
  szerzodes: "Szerződés (a forgatás után, nap)",
  tig: "TIG kiküldése (a forgatás után, nap)",
  szamla: "Számla (a forgatás után, nap)",
  alairas: "Aláírt szerződés vissza (a kiküldés után, nap)",
};

async function getJson<T>(url: string): Promise<T> {
  const res = await authFetch(url);
  if (!res.ok) {
    const d = await res.json().catch(() => null);
    throw new Error(typeof d?.detail === "string" ? d.detail : `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

const gomb =
  "rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50";
const gombFo =
  "rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50";

/** ADMINISZTRÁCIÓ ELLENŐRZÉSE - a tulajdonos felülete (lásd backend
 * routes/admin_ellenorzes.py). Lara jelzései, a tevékenységnapló, a
 * kivételek (kihagyások és társai) tulajdonosi döntéssel, a határidőn túli
 * hiányok, a heti összesítő és a beállítások. */
export function AdminEllenorzes({ emberek }: { emberek: { id: number; full_name: string }[] }) {
  // A fül az URL-ben is (Lara jelzései oda linkelnek, pl. ?ful=kivetelek).
  const kereso = useSearchParams();
  const [ful, setFul] = useState<Ful>(() => {
    const k = kereso.get("ful");
    return FULEK.some((f) => f.kulcs === k) ? (k as Ful) : "lara";
  });
  const [tiltva, setTiltva] = useState<string | null>(null);
  const [beallitas, setBeallitas] = useState<Beallitas | null>(null);
  const [osszesito, setOsszesito] = useState<Osszesito | null>(null);
  const [frissites, setFrissites] = useState(0);

  function fulValtas(k: Ful) {
    setFul(k);
    const url = new URL(window.location.href);
    url.searchParams.set("ful", k);
    window.history.replaceState(null, "", url.toString());
  }

  const frissit = useCallback(() => setFrissites((n) => n + 1), []);

  useEffect(() => {
    let ervenyes = true;
    Promise.all([getJson<Beallitas>(`${API}/beallitasok`), getJson<Osszesito>(`${API}/osszesito`)])
      .then(([b, o]) => {
        if (!ervenyes) return;
        setBeallitas(b);
        setOsszesito(o);
      })
      .catch((err) => ervenyes && setTiltva(err instanceof Error ? err.message : String(err)));
    return () => {
      ervenyes = false;
    };
  }, [frissites]);

  if (tiltva) {
    return (
      <div className="mx-auto max-w-xl rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6 text-[13.5px] text-text-secondary">
        {tiltva}
      </div>
    );
  }

  const szamok = osszesito?.szamok;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-semibold text-text-primary">Adminisztráció ellenőrzése</h1>
          <p className="mt-0.5 text-[13px] text-text-muted">
            Mikor mi készült el, mindenhez van-e papír, és nincs-e csendben kihagyva semmi.{" "}
            {beallitas?.figyelt_nev ? (
              <>
                Figyelt kolléga: <span className="text-text-secondary">{beallitas.figyelt_nev}</span>
                {beallitas.lara_figyeles ? " · Lara figyeli" : " · Lara figyelése ki van kapcsolva"}
              </>
            ) : (
              "Még nincs kiválasztva figyelt kolléga (Beállítások fül)."
            )}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          { cim: "Nyitott Lara-jelzés", ertek: szamok?.nyitott_jelzes, ful: "lara" as Ful },
          { cim: "Át nem nézett kivétel (90 nap)", ertek: szamok?.atnezetlen_kivetel, ful: "kivetelek" as Ful },
          { cim: "Határidőn túli hiány", ertek: szamok?.lejart_hiany, ful: "lejart" as Ful },
        ].map((t) => (
          <button
            key={t.cim}
            type="button"
            onClick={() => fulValtas(t.ful)}
            className="rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3 text-left hover:border-text-accent/40"
          >
            <p className="text-[12px] text-text-muted">{t.cim}</p>
            <p className={`mt-1 text-[24px] font-semibold tabular-nums ${t.ertek ? "text-text-warning" : "text-text-primary"}`}>
              {t.ertek ?? "…"}
            </p>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-1 border-b border-border">
        {FULEK.map((f) => (
          <button
            key={f.kulcs}
            type="button"
            onClick={() => fulValtas(f.kulcs)}
            className={`-mb-px border-b-2 px-3 py-2 text-[13px] ${
              ful === f.kulcs ? "border-text-accent text-text-primary" : "border-transparent text-text-muted hover:text-text-secondary"
            }`}
          >
            {f.cim}
          </button>
        ))}
      </div>

      {ful === "lara" && <LaraJelzesek beallitas={beallitas} onValtozas={frissit} onBeallitasok={() => fulValtas("beallitasok")} />}
      {ful === "naplo" && <Naplo figyeltId={beallitas?.figyelt_employee_id ?? null} />}
      {ful === "kivetelek" && <Kivetelek figyeltNev={beallitas?.figyelt_nev ?? null} onValtozas={frissit} />}
      {ful === "lejart" && <LejartHianyok />}
      {ful === "osszesito" && osszesito && <HetiOsszesito adat={osszesito} figyeltNev={beallitas?.figyelt_nev ?? null} />}
      {ful === "beallitasok" && beallitas && (
        <Beallitasok beallitas={beallitas} emberek={emberek} onMentve={(b) => { setBeallitas(b); frissit(); }} />
      )}
    </div>
  );
}

// ── Lara jelzései ───────────────────────────────────────────────────────────

function LaraJelzesek({
  beallitas,
  onValtozas,
  onBeallitasok,
}: {
  beallitas: Beallitas | null;
  onValtozas: () => void;
  onBeallitasok: () => void;
}) {
  const [lista, setLista] = useState<Jelzes[] | null>(null);
  const [lezartak, setLezartak] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [kor, setKor] = useState(0);

  useEffect(() => {
    let ervenyes = true;
    getJson<Jelzes[]>(`${API}/lara/jelzesek?nyitott=${!lezartak}`)
      .then((l) => ervenyes && setLista(l))
      .catch((e) => ervenyes && setUzenet(String(e)));
    return () => {
      ervenyes = false;
    };
  }, [lezartak, kor]);

  async function futtat() {
    setBusy(true);
    setUzenet(null);
    try {
      const res = await authFetch(`${API}/lara/futtatas`, { method: "POST" });
      const d = await res.json().catch(() => null);
      if (!res.ok) throw new Error(d?.detail ?? res.status);
      setUzenet(
        d.allapot === "nincs_figyelt"
          ? "Előbb válaszd ki a figyelt kollégát a Beállítások fülön."
          : d.allapot === "veszleallitas"
            ? "Lara le van állítva (vészleállítás) - most nem figyel."
            : `Lara végignézte: ${d.uj_jelzes} új jelzés.`,
      );
      setKor((n) => n + 1);
      onValtozas();
    } catch (err) {
      setUzenet(`Nem sikerült: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function lezar(j: Jelzes) {
    setBusy(true);
    try {
      await authFetch(`${API}/lara/jelzesek/${j.id}/lezaras`, { method: "POST" });
      setKor((n) => n + 1);
      onValtozas();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {beallitas && !beallitas.lara_figyeles && (
        <p className="rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[13px] text-text-secondary">
          Lara folyamatos figyelése ki van kapcsolva.{" "}
          <button type="button" onClick={onBeallitasok} className="text-text-accent hover:underline">
            Bekapcsolás a Beállítások fülön
          </button>
          . Kézzel most is lefuttathatod.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={futtat} disabled={busy} className={gombFo}>
          {busy ? "Lara nézi…" : "Lara nézze át most"}
        </button>
        <label className="flex items-center gap-1.5 text-[12.5px] text-text-secondary">
          <input type="checkbox" checked={lezartak} onChange={(e) => setLezartak(e.target.checked)} />
          lezártak is
        </label>
        {beallitas?.utolso_futas_at && (
          <span className="text-[12px] text-text-muted">Utolsó kör: {formatIdopont(beallitas.utolso_futas_at)}</span>
        )}
        {uzenet && <span className="text-[12.5px] text-text-secondary">{uzenet}</span>}
      </div>
      {!lista ? (
        <p className="text-[13px] text-text-muted">Betöltés…</p>
      ) : lista.length === 0 ? (
        <p className="rounded-[var(--radius)] border border-border bg-surface-2 px-4 py-6 text-center text-[13px] text-text-muted">
          Nincs {lezartak ? "" : "nyitott "}jelzés – Lara nem látott szokatlant.
        </p>
      ) : (
        <ul className="space-y-2">
          {lista.map((j) => (
            <li key={j.id} className="rounded-[var(--radius)] border border-border bg-surface-2 px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 text-[13.5px] font-medium text-text-primary">
                    <StatusBadge label={j.szint === "info" ? "Nézd meg" : "Figyelem"} tone={j.szint === "info" ? "neutral" : "warning"} />
                    {j.cim}
                  </p>
                  {j.leiras && <p className="mt-1 text-[12.5px] text-text-secondary">{j.leiras}</p>}
                  <p className="mt-1 text-[11.5px] text-text-muted">
                    Lara jelezte: {formatIdopont(j.letrejott_at)}
                    {j.lezarva_at && ` · lezárva: ${formatIdopont(j.lezarva_at)}`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {j.link && (
                    <Link href={j.link} className="text-[12.5px] text-text-accent hover:underline">
                      Megnyitás
                    </Link>
                  )}
                  {!j.lezarva_at && (
                    <button type="button" disabled={busy} onClick={() => lezar(j)} className={gomb}>
                      Láttam, lezárom
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Napló ──────────────────────────────────────────────────────────────────

function adatKivonat(adat: Record<string, unknown>): string {
  const r: string[] = [];
  const indok = adat.kihagyas_oka ?? adat.szamla_kihagyas_oka;
  if (indok) r.push(`indok: „${String(indok)}”`);
  if (adat.allapot) r.push(`állapot: ${String(adat.allapot)}`);
  if (adat.nincs_szamla === true) r.push("sosem lesz számlája");
  if (adat.kesz === true) r.push("kifizetve");
  const osszeg = adat.netto_osszeg ?? adat.brutto ?? adat.netto;
  if (typeof osszeg === "number") r.push(formatHuf(osszeg));
  if (typeof adat.projektek_db === "number" && adat.projektek_db > 1) r.push(`${adat.projektek_db} projekt`);
  return r.join(" · ");
}

function Naplo({ figyeltId }: { figyeltId: number | null }) {
  const [napok, setNapok] = useState(14);
  const [csakFigyelt, setCsakFigyelt] = useState(false);
  const [csakKivetel, setCsakKivetel] = useState(false);
  const [lista, setLista] = useState<NaploSor[] | null>(null);

  useEffect(() => {
    let ervenyes = true;
    const q = new URLSearchParams({ napok: String(napok), csak_kivetel: String(csakKivetel) });
    if (csakFigyelt && figyeltId) q.set("employee_id", String(figyeltId));
    getJson<NaploSor[]>(`${API}/naplo?${q}`)
      .then((l) => ervenyes && setLista(l))
      .catch(() => ervenyes && setLista([]));
    return () => {
      ervenyes = false;
    };
  }, [napok, csakFigyelt, csakKivetel, figyeltId]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-[12.5px] text-text-secondary">
        <select value={napok} onChange={(e) => setNapok(Number(e.target.value))} aria-label="Időszak" className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1">
          {[7, 14, 30, 90, 365].map((n) => (
            <option key={n} value={n}>
              utolsó {n} nap
            </option>
          ))}
        </select>
        {figyeltId && (
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={csakFigyelt} onChange={(e) => setCsakFigyelt(e.target.checked)} />
            csak a figyelt kolléga
          </label>
        )}
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={csakKivetel} onChange={(e) => setCsakKivetel(e.target.checked)} />
          csak kivételek (kihagyás, törlés, kézi állapot)
        </label>
        <span className="text-text-muted">A napló a bevezetése óta rögzít - a korábbi lépések nem látszanak itt.</span>
      </div>
      {!lista ? (
        <p className="text-[13px] text-text-muted">Betöltés…</p>
      ) : lista.length === 0 ? (
        <p className="text-[13px] text-text-muted">Ebben az időszakban nincs rögzített lépés.</p>
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="min-w-full text-[13px]">
            <thead className="bg-surface-2 text-left text-[11.5px] uppercase tracking-wide text-text-muted">
              <tr>
                <th className="px-3 py-2">Mikor</th>
                <th className="px-3 py-2">Ki</th>
                <th className="px-3 py-2">Mit</th>
                <th className="px-3 py-2">Részlet</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {lista.map((s) => (
                <tr key={s.id} className={s.kivetel ? "bg-bg-warning/30" : ""}>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums text-text-secondary">{formatIdopont(s.letrejott_at)}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-text-secondary">{s.ki}</td>
                  <td className="px-3 py-2 text-text-primary">{s.leiras}</td>
                  <td className="px-3 py-2 text-[12px] text-text-muted">{adatKivonat(s.adat)}</td>
                  <td className="px-3 py-2 text-right">
                    {s.link && (
                      <Link href={s.link} className="text-[12.5px] text-text-accent hover:underline">
                        Megnyitás
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Kivételek ──────────────────────────────────────────────────────────────

function Kivetelek({ figyeltNev, onValtozas }: { figyeltNev: string | null; onValtozas: () => void }) {
  const [csakNyitott, setCsakNyitott] = useState(true);
  const [napok, setNapok] = useState<number | null>(90);
  const [lista, setLista] = useState<Kivetel[] | null>(null);
  const [kor, setKor] = useState(0);
  const [visszadobas, setVisszadobas] = useState<Kivetel | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let ervenyes = true;
    const q = new URLSearchParams({ csak_nyitott: String(csakNyitott) });
    if (napok) q.set("napok", String(napok));
    else q.set("napok", "3650");
    getJson<Kivetel[]>(`${API}/kivetelek?${q}`)
      .then((l) => ervenyes && setLista(l))
      .catch(() => ervenyes && setLista([]));
    return () => {
      ervenyes = false;
    };
  }, [csakNyitott, napok, kor]);

  async function dont(k: Kivetel, dontes: "rendben" | "visszadobva", megjegyzes?: string, feladat?: boolean) {
    setBusy(true);
    try {
      const res = await authFetch(`${API}/kivetelek/jeloles`, {
        method: "POST",
        body: JSON.stringify({ kulcs: k.kulcs, dontes, megjegyzes, feladat, cim: `${k.tipus} – ${k.projekt}`, link: k.link }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        alert(`Nem sikerült: ${d?.detail ?? res.status}`);
        return;
      }
      setVisszadobas(null);
      setKor((n) => n + 1);
      onValtozas();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-[12.5px] text-text-secondary">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={csakNyitott} onChange={(e) => setCsakNyitott(e.target.checked)} />
          csak az át nem nézettek
        </label>
        <select
          value={napok ?? 0}
          onChange={(e) => setNapok(Number(e.target.value) || null)}
          aria-label="Időszak"
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1"
        >
          <option value={30}>utolsó 30 nap</option>
          <option value={90}>utolsó 90 nap</option>
          <option value={365}>utolsó év</option>
          <option value={0}>összes</option>
        </select>
        <span className="text-text-muted">
          Kihagyások, „van már szerződése” jelölések, számla-kihagyások, törlések és kézi állapot-átállítások – egy helyen.
        </span>
      </div>
      {!lista ? (
        <p className="text-[13px] text-text-muted">Betöltés…</p>
      ) : lista.length === 0 ? (
        <p className="rounded-[var(--radius)] border border-border bg-surface-2 px-4 py-6 text-center text-[13px] text-text-muted">
          Nincs {csakNyitott ? "át nem nézett " : ""}kivétel ebben az időszakban.
        </p>
      ) : (
        <ul className="space-y-2">
          {lista.map((k) => (
            <li key={k.kulcs} className="rounded-[var(--radius)] border border-border bg-surface-2 px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-0.5">
                  <p className="flex flex-wrap items-center gap-2 text-[13.5px] font-medium text-text-primary">
                    {k.tipus}
                    {k.dontes === "rendben" && <StatusBadge label="Rendben" tone="success" />}
                    {k.dontes === "visszadobva" && <StatusBadge label="Visszadobva" tone="danger" />}
                  </p>
                  <p className="text-[12.5px] text-text-secondary">
                    {k.fel} · {k.projekt}
                    {k.projektek_db > 1 && ` (+${k.projektek_db - 1} projekt)`}
                    {k.osszeg ? ` · ${formatHuf(k.osszeg)}` : ""}
                  </p>
                  <p className="text-[12.5px] text-text-secondary">
                    Indok: {k.indok ? <span className="text-text-primary">„{k.indok}”</span> : <span className="text-text-warning">nincs megadva</span>}
                  </p>
                  {k.figyelmeztetes && <p className="text-[12.5px] text-text-warning">{k.figyelmeztetes}</p>}
                  <p className="text-[11.5px] text-text-muted">
                    {k.ki ? `${k.ki} · ${formatIdopont(k.mikor)}` : `A napló bevezetése előtt (utoljára módosítva: ${formatIdopont(k.modositva_at)})`}
                    {k.dontes_megjegyzes && ` · a megjegyzésed: „${k.dontes_megjegyzes}”`}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {k.link && (
                    <Link href={k.link} className="text-[12.5px] text-text-accent hover:underline">
                      Megnyitás
                    </Link>
                  )}
                  {k.dontes !== "rendben" && (
                    <button type="button" disabled={busy} onClick={() => dont(k, "rendben")} className={gomb}>
                      Rendben
                    </button>
                  )}
                  {k.dontes !== "visszadobva" && (
                    <button type="button" disabled={busy} onClick={() => setVisszadobas(k)} className={gomb}>
                      Visszadobom
                    </button>
                  )}
                </div>
              </div>
              {visszadobas?.kulcs === k.kulcs && (
                <VisszadobasUrlap
                  figyeltNev={figyeltNev}
                  busy={busy}
                  onMegse={() => setVisszadobas(null)}
                  onKuld={(megjegyzes, feladat) => dont(k, "visszadobva", megjegyzes, feladat)}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function VisszadobasUrlap({
  figyeltNev,
  busy,
  onMegse,
  onKuld,
}: {
  figyeltNev: string | null;
  busy: boolean;
  onMegse: () => void;
  onKuld: (megjegyzes: string, feladat: boolean) => void;
}) {
  const [megjegyzes, setMegjegyzes] = useState("");
  const [feladat, setFeladat] = useState(Boolean(figyeltNev));
  return (
    <div className="mt-3 space-y-2 border-t border-border pt-3">
      <textarea
        value={megjegyzes}
        onChange={(e) => setMegjegyzes(e.target.value)}
        rows={2}
        placeholder="Mi a gond vele? (a kolléga ezt látja a feladatban)"
        aria-label="Megjegyzés a visszadobáshoz"
        className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
      />
      <div className="flex flex-wrap items-center gap-3">
        <label className={`flex items-center gap-1.5 text-[12.5px] ${figyeltNev ? "text-text-secondary" : "text-text-muted"}`}>
          <input type="checkbox" checked={feladat} disabled={!figyeltNev} onChange={(e) => setFeladat(e.target.checked)} />
          {figyeltNev ? `Feladat ${figyeltNev} részére (2 napos határidővel)` : "Feladatot csak beállított figyelt kollégának lehet adni"}
        </label>
        <div className="ml-auto flex gap-2">
          <button type="button" onClick={onMegse} disabled={busy} className={gomb}>
            Mégse
          </button>
          <button type="button" onClick={() => onKuld(megjegyzes, feladat)} disabled={busy} className={gombFo}>
            Visszadobom
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Lejárt hiányok ─────────────────────────────────────────────────────────

function LejartHianyok() {
  const [lista, setLista] = useState<Lejart[] | null>(null);
  useEffect(() => {
    let ervenyes = true;
    getJson<Lejart[]>(`${API}/lejart`)
      .then((l) => ervenyes && setLista(l))
      .catch(() => ervenyes && setLista([]));
    return () => {
      ervenyes = false;
    };
  }, []);
  if (!lista) return <p className="text-[13px] text-text-muted">Betöltés…</p>;
  if (lista.length === 0)
    return (
      <p className="rounded-[var(--radius)] border border-border bg-surface-2 px-4 py-6 text-center text-[13px] text-text-muted">
        Nincs határidőn túli hiány.
      </p>
    );
  return (
    <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
      <table className="min-w-full text-[13px]">
        <thead className="bg-surface-2 text-left text-[11.5px] uppercase tracking-wide text-text-muted">
          <tr>
            <th className="px-3 py-2">Késés</th>
            <th className="px-3 py-2">Mi hiányzik</th>
            <th className="px-3 py-2">Projekt</th>
            <th className="px-3 py-2">Kitől</th>
            <th className="px-3 py-2">Állapot</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {lista.map((h) => (
            <tr key={h.kulcs}>
              <td className={`whitespace-nowrap px-3 py-2 tabular-nums ${h.keses_nap >= 7 ? "text-text-danger" : "text-text-warning"}`}>
                {h.keses_nap} nap
                <span className="block text-[11px] text-text-muted">
                  {h.eltelt_nap} / {h.hatarido_nap} nap
                </span>
              </td>
              <td className="px-3 py-2 text-text-primary">{h.dokumentum}</td>
              <td className="px-3 py-2 text-text-secondary">
                {h.projekt}
                {h.forgatas_datuma && <span className="block text-[11.5px] text-text-muted">{h.forgatas_datuma}</span>}
              </td>
              <td className="px-3 py-2 text-text-secondary">{h.fel}</td>
              <td className="px-3 py-2 text-[12px] text-text-muted">{h.allapot}</td>
              <td className="px-3 py-2 text-right">
                <Link href={h.link} className="text-[12.5px] text-text-accent hover:underline">
                  Megnyitás
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Heti összesítő ─────────────────────────────────────────────────────────

function HetiOsszesito({ adat, figyeltNev }: { adat: Osszesito; figyeltNev: string | null }) {
  const oszlopok = Object.entries(adat.csoportok);
  return (
    <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
      <table className="min-w-full text-[13px]">
        <thead className="bg-surface-2 text-left text-[11.5px] uppercase tracking-wide text-text-muted">
          <tr>
            <th className="px-3 py-2">Hét</th>
            <th className="px-3 py-2 text-right">Összes lépés</th>
            {figyeltNev && <th className="px-3 py-2 text-right">ebből {figyeltNev}</th>}
            {oszlopok.map(([k, cim]) => (
              <th key={k} className="px-3 py-2 text-right">
                {cim}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {adat.hetek.map((h) => (
            <tr key={String(h.het_kezdete)}>
              <td className="whitespace-nowrap px-3 py-2 text-text-secondary">{String(h.het_kezdete).replaceAll("-", ".")}. -tól</td>
              <td className="px-3 py-2 text-right tabular-nums text-text-primary">{h.osszes}</td>
              {figyeltNev && <td className="px-3 py-2 text-right tabular-nums text-text-secondary">{h.figyelt}</td>}
              {oszlopok.map(([k]) => (
                <td
                  key={k}
                  className={`px-3 py-2 text-right tabular-nums ${
                    (k === "kivetel" || k === "torles") && Number(h[k]) > 0 ? "text-text-warning" : "text-text-secondary"
                  }`}
                >
                  {h[k] || "–"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Beállítások ────────────────────────────────────────────────────────────

function Beallitasok({
  beallitas,
  emberek,
  onMentve,
}: {
  beallitas: Beallitas;
  emberek: { id: number; full_name: string }[];
  onMentve: (b: Beallitas) => void;
}) {
  const [figyelt, setFigyelt] = useState<string>(beallitas.figyelt_employee_id ? String(beallitas.figyelt_employee_id) : "");
  const [lara, setLara] = useState(beallitas.lara_figyeles);
  const [hataridok, setHataridok] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(beallitas.hataridok).map(([k, v]) => [k, String(v)])),
  );
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);

  async function ment() {
    setBusy(true);
    setUzenet(null);
    try {
      const res = await authFetch(`${API}/beallitasok`, {
        method: "PUT",
        body: JSON.stringify({
          figyelt_employee_id: figyelt ? Number(figyelt) : null,
          figyelt_torles: !figyelt,
          lara_figyeles: lara,
          hataridok: Object.fromEntries(Object.entries(hataridok).map(([k, v]) => [k, Number(v) || 0])),
        }),
      });
      const d = await res.json().catch(() => null);
      if (!res.ok) throw new Error(d?.detail ?? res.status);
      onMentve(d as Beallitas);
      setUzenet("Elmentve.");
    } catch (err) {
      setUzenet(`Nem sikerült: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-5">
      <section className="space-y-2 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
        <p className="text-[14px] font-medium text-text-primary">Kit figyeljen Lara?</p>
        <p className="text-[12.5px] text-text-muted">
          Az adminisztrációs kolléga, akinek a munkáját ellenőrzöd. Ő ezt az oldalt soha nem látja, és Lara jelzései sem
          jutnak el hozzá – csak a visszadobott tételekből kap feladatot, ha te úgy döntesz.
        </p>
        <KeresosSelect
          value={figyelt || null}
          options={[{ value: "", label: "– nincs kiválasztva –" }, ...emberek.map((e) => ({ value: String(e.id), label: e.full_name }))]}
          onChange={setFigyelt}
          placeholder="Válassz munkatársat…"
          className="min-w-[260px]"
        />
        <label className="mt-2 flex items-start gap-2 text-[13px] text-text-primary">
          <input type="checkbox" checked={lara} onChange={(e) => setLara(e.target.checked)} className="mt-0.5" />
          <span>
            Lara folyamatosan figyelje (óránként átnézi)
            <span className="block text-[12px] text-text-muted">
              Csak olvas és csak itt, neked jelez: kihagyás semmitmondó indokkal, sok kihagyás egy napon, törlés, „van már
              szerződése” jelölés, kézzel „kiküldött”-re állított papír, számla nélkül kifizetett TIG, nagy összegű „sosem lesz
              számlája”, egy héttel a határidőn túl késő papír, napok óta tartó tétlenség. A vészleállítás őt is megállítja.
            </span>
          </span>
        </label>
      </section>

      <section className="space-y-2 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
        <p className="text-[14px] font-medium text-text-primary">Határidők</p>
        <p className="text-[12.5px] text-text-muted">Ennél régebben hiányzó papír kerül a „Lejárt hiányok” közé.</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {Object.keys(HATARIDO_CIMKEK).map((k) => (
            <label key={k} className="flex flex-col gap-1 text-[12px] text-text-muted">
              {HATARIDO_CIMKEK[k]}
              <input
                type="number"
                min={0}
                max={365}
                value={hataridok[k] ?? ""}
                onChange={(e) => setHataridok((h) => ({ ...h, [k]: e.target.value }))}
                className="w-28 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
              />
            </label>
          ))}
        </div>
      </section>

      <div className="flex items-center gap-3">
        <button type="button" onClick={ment} disabled={busy} className={gombFo}>
          {busy ? "Mentés…" : "Mentés"}
        </button>
        {uzenet && <span className="text-[12.5px] text-text-secondary">{uzenet}</span>}
      </div>
    </div>
  );
}
