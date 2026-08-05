"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { formatHuf } from "@/lib/penz";
import type { EvesKoltseg, HaviKoltseg, HaviTetel } from "@/lib/api";

type ProjektOpcio = { id: number; nev: string };

const HONAP_NEVEK = [
  "január", "február", "március", "április", "május", "június",
  "július", "augusztus", "szeptember", "október", "november", "december",
];

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
  projektek,
  szerkeszthet,
  torolhet,
  zarolt,
  alapbolNyitva = false,
}: {
  employeeId: number;
  ev: number;
  honap: number;
  tetelek: HaviTetel[];
  projektek: ProjektOpcio[];
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
  const [tipus, setTipus] = useState<"alapber" | "extra">("extra");
  const [megnevezes, setMegnevezes] = useState("");
  const [osszeg, setOsszeg] = useState("");
  const [projectId, setProjectId] = useState("");

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
          project_id: projectId ? Number(projectId) : null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setMegnevezes("");
      setOsszeg("");
      setProjectId("");
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
            <li key={t.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2">
              <span className="min-w-0 flex-1">
                <span className="text-[13px] text-text-primary">{t.megnevezes}</span>
                {t.tipus === "alapber" && (
                  <span className="ml-2 align-middle">
                    <StatusBadge label="Alapbér" tone="neutral" />
                  </span>
                )}
                {t.project_nev && <span className="mt-0.5 block text-[12px] text-text-muted">{t.project_nev}</span>}
              </span>
              <span className="shrink-0 text-[13px] text-text-primary tabular-nums">{formatHuf(t.osszeg)}</span>
              {torolhet && !zarolt && (
                <button
                  type="button"
                  onClick={() => torol(t)}
                  disabled={busy}
                  title="Tétel törlése"
                  className="rounded-[var(--radius)] p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                >
                  <Trash2 size={13} />
                </button>
              )}
            </li>
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
              <select
                value={tipus}
                onChange={(e) => setTipus(e.target.value as "alapber" | "extra")}
                className="field"
              >
                <option value="extra">Extra</option>
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
              <span className="t-label">Projekt</span>
              <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="field w-[190px]">
                <option value="">Nincs projekthez kötve</option>
                {projektek.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nev}
                  </option>
                ))}
              </select>
            </label>
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
  projektek,
  szerkeszthet,
  torolhet,
}: {
  employeeId: number;
  honap: HaviKoltseg;
  projektek: ProjektOpcio[];
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
      </button>

      {nyitva && (
        <div className="fade-in pb-4 pl-7">
          {/* Az alapbér és az extrák külön összege - ebből látszik, mennyi
              volt a fix rész, és mennyi jött hozzá a hónap közben. */}
          {(honap.alapber > 0 || honap.extra > 0) && (
            <p className="mb-3 text-[12px] text-text-muted">
              Alapbér: <span className="text-text-secondary">{formatHuf(honap.alapber)}</span> · Extrák:{" "}
              <span className="text-text-secondary">{formatHuf(honap.extra)}</span>
            </p>
          )}
          <TetelSzerkeszto
            employeeId={employeeId}
            ev={honap.ev}
            honap={honap.honap}
            tetelek={honap.tetelek}
            projektek={projektek}
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
  projektek,
  szerkeszthet,
  torolhet,
}: {
  employeeId: number;
  evek: EvesKoltseg[];
  projektek: ProjektOpcio[];
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
              projektek={projektek}
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
            </label>
            <TetelSzerkeszto
              key={ujHonap}
              employeeId={employeeId}
              ev={ujEv}
              honap={ujHonapSzam}
              tetelek={[]}
              projektek={projektek}
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
