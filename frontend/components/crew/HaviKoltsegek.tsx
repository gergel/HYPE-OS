"use client";

import { useMemo, useState } from "react";
import { Check, ChevronDown, ChevronRight, ExternalLink, Pencil, Plus, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useConfirm } from "@/components/ConfirmProvider";
import { SearchableIdPicker } from "@/components/SearchableIdPicker";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { HONAP_NEVEK } from "@/lib/ido";
import { formatHuf } from "@/lib/penz";
import type { EvesKoltseg, HaviKoltseg, HaviTetel } from "@/lib/api";

type TetelTipus = "alapber" | "extra" | "levonando";

/** A tétel-típusok. A "levonando" összegét POZITÍVAN visszük fel, az előjelet
 * a típus adja - így a felületen nem kell mínusszal bajlódni, és nem fordulhat
 * elő, hogy egy elfelejtett mínusz miatt egy levonás hozzáadódik. */
const TIPUS_NEVEK: Record<string, string> = {
  alapber: "Alapbér",
  extra: "Extra",
  levonando: "Levonandó",
};

/** Az összeg megjelenítése előjelesen: a levonandó mínusszal. */
function elojelesOsszeg(tipus: string, osszeg: number): string {
  return tipus === "levonando" ? `− ${formatHuf(osszeg)}` : formatHuf(osszeg);
}

/** A választható projektkódok - a kereshető listát ebből építjük
 * (SearchableIdPicker), mert több száz projektkódnál egy sima legördülő
 * használhatatlan lenne. */
export type ProjektkodOpcio = { id: number; projektkod: string };


/** Egy tétel sora. Kattintásra HELYBEN szerkeszthető (megnevezés, összeg,
 * dátum, projektkód, típus) - nem külön űrlapon, mert egy elgépelt összeg
 * javítása a leggyakoribb művelet, és nem érdemes hozzá oldalt váltani. */
function TetelSor({
  tetel,
  projektkodok,
  szerkeszthet,
  torolhet,
  onTorol,
}: {
  tetel: HaviTetel;
  projektkodok: ProjektkodOpcio[];
  szerkeszthet: boolean;
  torolhet: boolean;
  onTorol: () => void;
}) {
  const router = useRouter();
  const [szerkeszt, setSzerkeszt] = useState(false);
  const [busy, setBusy] = useState(false);
  const [tipus, setTipus] = useState<TetelTipus>(tetel.tipus);
  const [megnevezes, setMegnevezes] = useState(tetel.megnevezes);
  const [osszeg, setOsszeg] = useState(String(tetel.osszeg));
  const [datum, setDatum] = useState(tetel.datum ?? "");
  const [projectCodeId, setProjectCodeId] = useState<number | null>(tetel.project_code_id);

  function megsem() {
    setTipus(tetel.tipus);
    setMegnevezes(tetel.megnevezes);
    setOsszeg(String(tetel.osszeg));
    setDatum(tetel.datum ?? "");
    setProjectCodeId(tetel.project_code_id);
    setSzerkeszt(false);
  }

  async function ment() {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/tetelek/${tetel.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tipus,
          megnevezes: megnevezes.trim() || tetel.megnevezes,
          osszeg: Number(osszeg) || 0,
          project_code_id: projectCodeId,
          datum: datum || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setSzerkeszt(false);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  if (szerkeszt) {
    return (
      <li className="fade-in py-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="t-label">Típus</span>
            <select value={tipus} onChange={(e) => setTipus(e.target.value as TetelTipus)} className="field">
              <option value="extra">Extra (hozzáadódik)</option>
              <option value="levonando">Levonandó (levonódik)</option>
              <option value="alapber">Alapbér</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="t-label">Megnevezés</span>
            <input
              type="text"
              value={megnevezes}
              onChange={(e) => setMegnevezes(e.target.value)}
              className="field w-[180px]"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="t-label">Összeg</span>
            <input
              type="number"
              value={osszeg}
              onChange={(e) => setOsszeg(e.target.value)}
              className="field w-[130px]"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="t-label">Pontos dátum</span>
            <input type="date" value={datum} onChange={(e) => setDatum(e.target.value)} className="field w-[160px]" />
          </label>
          <div className="flex flex-col gap-1.5">
            <span className="t-label">Projektkód</span>
            <SearchableIdPicker
              value={projectCodeId}
              options={projektkodok.map((p) => ({ id: p.id, label: p.projektkod }))}
              onChange={setProjectCodeId}
              placeholder="Nincs projektkódhoz kötve"
              disabled={busy}
              className="w-[210px]"
            />
          </div>
          <button type="button" onClick={ment} disabled={busy} className="btn btn-primary">
            <Check size={13} /> {busy ? "Mentés…" : "Mentés"}
          </button>
          <button type="button" onClick={megsem} disabled={busy} className="btn btn-ghost">
            <X size={13} /> Mégse
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2">
      <span className="min-w-0 flex-1">
        <span className="text-[13px] text-text-primary">{tetel.megnevezes}</span>
        {tetel.tipus !== "extra" && (
          <span className="ml-2 align-middle">
            <StatusBadge
              label={TIPUS_NEVEK[tetel.tipus] ?? tetel.tipus}
              tone={tetel.tipus === "levonando" ? "danger" : "neutral"}
            />
          </span>
        )}
        {(tetel.projektkod || tetel.datum) && (
          <span className="mt-0.5 block text-[12px] text-text-muted">
            {[tetel.projektkod, tetel.datum].filter(Boolean).join(" · ")}
          </span>
        )}
      </span>
      <span
        className={`shrink-0 text-[13px] tabular-nums ${
          tetel.tipus === "levonando" ? "text-text-danger" : "text-text-primary"
        }`}
      >
        {elojelesOsszeg(tetel.tipus, tetel.osszeg)}
      </span>
      {szerkeszthet && (
        <button
          type="button"
          onClick={() => setSzerkeszt(true)}
          title="Tétel szerkesztése"
          className="rounded-[var(--radius)] p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-primary"
        >
          <Pencil size={13} />
        </button>
      )}
      {torolhet && (
        <button
          type="button"
          onClick={onTorol}
          title="Tétel törlése"
          className="rounded-[var(--radius)] p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-danger"
        >
          <Trash2 size={13} />
        </button>
      )}
    </li>
  );
}

/** Egy hónap tételei: az alapbér és a hozzáadódó extrák.
 *
 * Ez a blokk a havi összeg FORRÁSA: amit ide felviszünk, az azonnal
 * beleszámít a hónap Belsős TIG-jébe (a backend újraszámolja) - így aki a
 * TIG-et készíti, már a kész összeget látja, nem neki kell összeadnia a
 * hónap közben felmerült túlórákat, benzint, étkezést.
 *
 * Az alapbér is tétel, nem a munkatárs törzsadata: hónapról hónapra
 * változhat, és utólag is vissza kell tudni nézni, akkor mennyi volt. */
function TetelSzerkeszto({
  employeeId,
  ev,
  honap,
  tetelek,
  projektkodok,
  szerkeszthet,
  torolhet,
  zarolt,
  alapbolNyitva = false,
}: {
  employeeId: number;
  ev: number;
  honap: number;
  tetelek: HaviTetel[];
  projektkodok: ProjektkodOpcio[];
  szerkeszthet: boolean;
  torolhet: boolean;
  zarolt: boolean;
  /** Az űrlap azonnal nyitva induljon. Ott kell, ahol a felhasználó már
   * kimondta a szándékát ("tétel felvitele egy hónaphoz") - ilyenkor egy
   * második "Tétel hozzáadása" kattintás fölösleges lépés lenne. */
  alapbolNyitva?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitva, setNyitva] = useState(alapbolNyitva);
  const [busy, setBusy] = useState(false);
  const [tipus, setTipus] = useState<TetelTipus>("extra");
  const [megnevezes, setMegnevezes] = useState("");
  const [osszeg, setOsszeg] = useState("");
  const [projectCodeId, setProjectCodeId] = useState<number | null>(null);
  const [datum, setDatum] = useState("");

  const vanAlapber = tetelek.some((t) => t.tipus === "alapber");

  async function hozzaad() {
    if (!megnevezes.trim() || !osszeg.trim()) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${employeeId}/${ev}/${honap}/tetelek`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tipus,
          megnevezes: megnevezes.trim(),
          osszeg: Number(osszeg) || 0,
          project_code_id: projectCodeId,
          datum: datum || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setMegnevezes("");
      setOsszeg("");
      setProjectCodeId(null);
      setDatum("");
      setNyitva(false);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function torol(tetel: HaviTetel) {
    if (!(await confirm(`Törlöd ezt a tételt: "${tetel.megnevezes}"?`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/tetelek/${tetel.id}`, { method: "DELETE" });
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
    <div className="space-y-3">
      {tetelek.length > 0 && (
        <ul className="divide-y divide-border">
          {tetelek.map((t) => (
            <TetelSor
              key={t.id}
              tetel={t}
              projektkodok={projektkodok}
              szerkeszthet={szerkeszthet && !zarolt}
              torolhet={torolhet && !zarolt}
              onTorol={() => torol(t)}
            />
          ))}
        </ul>
      )}

      {zarolt ? (
        <p className="text-[12px] text-text-muted">
          A hónap TIG-je már véglegesítve van - ide már nem vehető fel új tétel.
        </p>
      ) : (
        szerkeszthet &&
        (nyitva ? (
          <div className="fade-in flex flex-wrap items-end gap-3 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
            <label className="flex flex-col gap-1.5">
              <span className="t-label">Típus</span>
              <select value={tipus} onChange={(e) => setTipus(e.target.value as TetelTipus)} className="field">
                <option value="extra">Extra (hozzáadódik)</option>
                <option value="levonando">Levonandó (levonódik)</option>
                <option value="alapber" disabled={vanAlapber}>
                  Alapbér{vanAlapber ? " (már van)" : ""}
                </option>
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="t-label">Megnevezés</span>
              <input
                type="text"
                value={megnevezes}
                onChange={(e) => setMegnevezes(e.target.value)}
                placeholder="pl. Túlóra, Benzin, Étkezés"
                className="field w-[190px]"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="t-label">Összeg</span>
              <input
                type="number"
                value={osszeg}
                onChange={(e) => setOsszeg(e.target.value)}
                className="field w-[130px]"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="t-label">Pontos dátum</span>
              <input type="date" value={datum} onChange={(e) => setDatum(e.target.value)} className="field w-[160px]" />
            </label>
            <div className="flex flex-col gap-1.5">
              <span className="t-label">Projektkód</span>
              {/* Kereshető lista: a projektkódok száma évek alatt több százra
                  nő, egy sima legördülőben nem lehetne megtalálni egyet. */}
              <SearchableIdPicker
                value={projectCodeId}
                options={projektkodok.map((p) => ({ id: p.id, label: p.projektkod }))}
                onChange={setProjectCodeId}
                placeholder="Nincs projektkódhoz kötve"
                disabled={busy}
                className="w-[210px]"
              />
            </div>
            <button type="button" onClick={hozzaad} disabled={busy} className="btn btn-primary">
              {busy ? "Mentés…" : "Hozzáadás"}
            </button>
            <button type="button" onClick={() => setNyitva(false)} className="btn btn-ghost">
              Mégse
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setNyitva(true)} className="btn btn-ghost">
            <Plus size={13} /> Tétel hozzáadása
          </button>
        ))
      )}
    </div>
  );
}

function HonapSor({
  employeeId,
  honap,
  projektkodok,
  szerkeszthet,
  torolhet,
}: {
  employeeId: number;
  honap: HaviKoltseg;
  projektkodok: ProjektkodOpcio[];
  szerkeszthet: boolean;
  torolhet: boolean;
}) {
  const [nyitva, setNyitva] = useState(false);
  const zarolt = ["Kész", "Kiküldve", "Kihagyva"].includes(honap.allapot ?? "");

  return (
    <div className="border-b border-border last:border-0">
      <button
        type="button"
        onClick={() => setNyitva((v) => !v)}
        className="flex w-full items-center gap-3 py-3 text-left transition-colors duration-200 hover:bg-surface-3"
      >
        {nyitva ? (
          <ChevronDown size={14} className="shrink-0 text-text-muted" />
        ) : (
          <ChevronRight size={14} className="shrink-0 text-text-muted" />
        )}
        <span className="min-w-0 flex-1 text-[13.5px] text-text-primary">{honap.honap_nev}</span>
        {honap.allapot && <StatusBadge label={honap.allapot} tone={zarolt ? "success" : "warning"} />}
        <span className="shrink-0 text-[13.5px] text-text-primary tabular-nums">
          {honap.netto_osszeg === null ? "–" : formatHuf(honap.netto_osszeg)}
        </span>
        {/* A hónap saját, megnyitható oldala: ott van egyben az alapbér, az
            extrák és a szumma - megosztható linkkel. A sor kinyitása helyben
            szerkeszt, ez a link "megnyitja" a hónapot. */}
        <Link
          href={`/belsos-tig/${employeeId}/${honap.ev}/${honap.honap}`}
          onClick={(e) => e.stopPropagation()}
          title="Hónap megnyitása külön oldalon"
          className="shrink-0 rounded-[var(--radius)] p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-primary"
        >
          <ExternalLink size={13} />
        </Link>
      </button>

      {nyitva && (
        <div className="fade-in pb-4 pl-7">
          {/* Az alapbér és az extrák külön összege - ebből látszik, mennyi
              volt a fix rész, és mennyi jött hozzá a hónap közben. */}
          {(honap.alapber > 0 || honap.extra > 0 || honap.levonas > 0) && (
            <p className="mb-3 text-[12px] text-text-muted">
              Alapbér: <span className="text-text-secondary">{formatHuf(honap.alapber)}</span> · Extrák:{" "}
              <span className="text-text-secondary">{formatHuf(honap.extra)}</span>
              {honap.levonas > 0 && (
                <>
                  {" · "}Levonások: <span className="text-text-danger">− {formatHuf(honap.levonas)}</span>
                </>
              )}
              {/* Bejelentett alkalmazottnál a fenti számok azt mutatják, mit
                  kap az ember - a munkáltatói terhekkel együtt ennyibe kerül. */}
              {honap.szuperbrutto != null && (
                <>
                  {" · "}Szuperbruttó: <span className="text-text-secondary">{formatHuf(honap.szuperbrutto)}</span>
                </>
              )}
            </p>
          )}
          <TetelSzerkeszto
            employeeId={employeeId}
            ev={honap.ev}
            honap={honap.honap}
            tetelek={honap.tetelek}
            projektkodok={projektkodok}
            szerkeszthet={szerkeszthet}
            torolhet={torolhet}
            zarolt={zarolt}
          />
        </div>
      )}
    </div>
  );
}

/** "Mibe került nekünk ez az ember" - a havi Belsős TIG összegek évekre
 * csoportosítva és évente összesítve, hónaponként lenyitva a tételekkel.
 *
 * Ugyanitt lehet a következő hónapokhoz tételt felvenni: az összeg a
 * tételekből áll össze, és a hónap TIG-jén már készen jelenik meg. */
export function HaviKoltsegek({
  employeeId,
  evek,
  projektkodok,
  szerkeszthet,
  torolhet,
}: {
  employeeId: number;
  evek: EvesKoltseg[];
  projektkodok: ProjektkodOpcio[];
  szerkeszthet: boolean;
  torolhet: boolean;
}) {
  const most = new Date();
  const [ujHonap, setUjHonap] = useState(`${most.getFullYear()}-${most.getMonth() + 1}`);
  const [ujNyitva, setUjNyitva] = useState(false);

  // A meglévő évek + az idei, hogy egy üres előéletű munkatársnál is legyen
  // hova felvinni az első hónapot.
  const evekLista = useMemo(() => [...evek].sort((a, b) => b.ev - a.ev), [evek]);
  const megvanHonap = useMemo(
    () => new Set(evek.flatMap((e) => e.honapok.map((h) => `${h.ev}-${h.honap}`))),
    [evek],
  );

  const [ujEv, ujHonapSzam] = ujHonap.split("-").map(Number);

  return (
    <div className="space-y-6">
      {evekLista.length === 0 && (
        <p className="text-[13px] text-text-muted">Ennek a munkatársnak még nincs havi költsége rögzítve.</p>
      )}

      {evekLista.map((ev) => (
        <div key={ev.ev}>
          <div className="mb-1 flex items-baseline justify-between gap-3 border-b border-border-strong pb-2">
            <span className="text-[15px] font-semibold tracking-[-0.01em] text-text-primary">{ev.ev}</span>
            <span className="text-[13px] text-text-secondary tabular-nums">
              Összesen: <span className="text-text-primary">{formatHuf(ev.osszesen)}</span>
            </span>
          </div>
          {ev.honapok.map((h) => (
            <HonapSor
              key={`${h.ev}-${h.honap}`}
              employeeId={employeeId}
              honap={h}
              projektkodok={projektkodok}
              szerkeszthet={szerkeszthet}
              torolhet={torolhet}
            />
          ))}
        </div>
      ))}

      {szerkeszthet &&
        (ujNyitva ? (
          <div className="fade-in space-y-3 rounded-[var(--radius)] border border-border bg-surface-3 p-4">
            <label className="flex flex-col gap-1.5">
              <span className="t-label">Melyik hónaphoz</span>
              <select value={ujHonap} onChange={(e) => setUjHonap(e.target.value)} className="field w-[220px]">
                {/* Az idei és a tavalyi év hónapjai - ennél régebbi hónapra
                    visszamenőleg tételt felvinni már nem életszerű. */}
                {[most.getFullYear(), most.getFullYear() - 1].flatMap((ev) =>
                  HONAP_NEVEK.map((nev, i) => (
                    <option key={`${ev}-${i + 1}`} value={`${ev}-${i + 1}`}>
                      {ev}. {nev}
                      {megvanHonap.has(`${ev}-${i + 1}`) ? " (már van)" : ""}
                    </option>
                  )),
                )}
              </select>
              <span className="mt-1 text-[12px] text-text-muted">
                A tételhez megadható pontos dátum is - az elszámolás hónapját attól függetlenül mindig ez a
                választás dönti el.
              </span>
            </label>
            <TetelSzerkeszto
              key={ujHonap}
              employeeId={employeeId}
              ev={ujEv}
              honap={ujHonapSzam}
              tetelek={[]}
              projektkodok={projektkodok}
              szerkeszthet={szerkeszthet}
              torolhet={torolhet}
              zarolt={false}
              alapbolNyitva
            />
            <button type="button" onClick={() => setUjNyitva(false)} className="btn btn-ghost">
              Bezárás
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setUjNyitva(true)} className="btn btn-primary">
            <Plus size={13} /> Tétel felvitele egy hónaphoz
          </button>
        ))}
    </div>
  );
}
