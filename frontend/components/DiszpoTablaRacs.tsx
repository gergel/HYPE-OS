"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { KeresosSelect } from "@/components/KeresosSelect";
// CSAK TÍPUS a lib/api-ból: az érték szerinti import behúzná a `next/headers`-t
// (a modul szerver oldalon süti-alapú hitelesítéssel hív), ami
// klienskomponensben build-hibát okoz. A színek ezért a kliens-biztos
// lib/diszpoSzin-ből jönnek - ugyanaz a szétválasztás, mint a lib/utokovetes-nél.
import type { DiszpoMunkalap } from "@/lib/api";
import { DISZPO_SZINEK, HONAP_NEVEK, MUNKANAP_SZINEK, SZIN_LEIRAS, type DiszpoSzin } from "@/lib/diszpoSzin";

/** A HYPE 2026 táblázat egy munkalapja - úgy, ahogy a Google Sheetben áll.
 *
 * A CELLA SZÍNE ITT ADAT. Ezért nem "formázás" a színezés, hanem a felület
 * fő művelete: kijelölsz egy cellát, és a paletta egy kattintásával megmondod,
 * mi történt aznap. Ebből jön ki, ki hány napot dolgozott egy hónapban - és
 * ez dönti el, mikor fogy el valakinek a szerződött napszáma (lásd
 * backend services/munkanap_szamlalo.py).
 *
 * MIÉRT HÓNAPONKÉNT? Mert a külsős munkalap 381 sor x 146 oszlop: egyben
 * kirajzolva 55 ezer cella lenne a képernyőn, amitől a böngésző megáll. A
 * táblázat amúgy is hónapokra van tagolva, tehát a hónap a természetes adag. */
export function DiszpoTablaRacs({
  munkalap,
  canEdit = true,
  emberek,
}: {
  munkalap: DiszpoMunkalap;
  canEdit?: boolean;
  /** A munkatársak az oszlop-ember kötéshez. */
  emberek: { id: number; nev: string }[];
}) {
  const router = useRouter();
  const [kijelolt, setKijelolt] = useState<{ sor: number; oszlop: number } | null>(null);
  const [szerkesztett, setSzerkesztett] = useState<{ sor: number; oszlop: number; ertek: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [kotesNyitva, setKotesNyitva] = useState(false);

  // A cellák gyors eléréséhez: "sor:oszlop" -> [érték, szín].
  const cellaTerkep = useMemo(() => {
    const t = new Map<string, { ertek: string | null; szin: string | null }>();
    for (const [sor, oszlop, ertek, szin] of munkalap.cellak) {
      t.set(`${sor}:${oszlop}`, { ertek, szin });
    }
    return t;
  }, [munkalap.cellak]);

  // Milyen hónapok vannak a munkalapon? Ahol nincs dátum (AUTÓK, PROJECT
  // KÓDOK), ott nincs mit hónapozni - az egész látszik.
  const honapok = useMemo(() => {
    const keszlet = new Set<string>();
    for (const s of munkalap.sorok) {
      if (s.datum) keszlet.add(s.datum.slice(0, 7));
    }
    return Array.from(keszlet).sort();
  }, [munkalap.sorok]);

  const [honap, setHonap] = useState<string>(() => {
    const mai = new Date().toISOString().slice(0, 7);
    return honapok.includes(mai) ? mai : (honapok[0] ?? "");
  });

  const lathatoSorok = useMemo(() => {
    const fejlec = munkalap.sorok.filter((s) => s.idx < munkalap.fejlec_sorok);
    if (honapok.length === 0) return munkalap.sorok;
    // A hónap sorai + a hozzá tartozó elválasztó felirat.
    const test = munkalap.sorok.filter((s) => s.datum?.startsWith(honap));
    const elso = test[0]?.idx ?? 0;
    const elvalaszto = munkalap.sorok.filter((s) => s.elvalaszto && s.idx < elso && s.idx > elso - 3);
    return [...fejlec, ...elvalaszto, ...test];
  }, [munkalap.sorok, munkalap.fejlec_sorok, honap, honapok.length]);

  const oszlopok = munkalap.oszlopok;
  const kijeloltOszlop = kijelolt ? oszlopok.find((o) => o.idx === kijelolt.oszlop) : null;

  async function mentesCella(sor: number, oszlop: number, mezok: Record<string, unknown>) {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/diszpo-tabla/${munkalap.id}/cella`, {
        method: "PUT",
        body: JSON.stringify({ sor_idx: sor, oszlop_idx: oszlop, ...mezok }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function kotesMentes(oszlopIdx: number, employeeId: number | null) {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/diszpo-tabla/${munkalap.id}/oszlop/${oszlopIdx}`, {
        method: "PUT",
        body: JSON.stringify({ employee_id: employeeId }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setKotesNyitva(false);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  function cellaStilus(szin: string | null): React.CSSProperties {
    if (!szin || !(szin in SZIN_LEIRAS)) return {};
    const s = SZIN_LEIRAS[szin as DiszpoSzin];
    return { backgroundColor: s.hatter, color: s.szoveg };
  }

  return (
    <div className="space-y-3">
      {/* A PALETTA: a kijelölt cella színezése. Ez a felület fő művelete. */}
      <div className="flex flex-wrap items-center gap-2">
        {honapok.length > 0 && (
          <KeresosSelect
            value={honap}
            options={honapok.map((h) => {
              const [ev, ho] = h.split("-");
              return { value: h, label: `${ev}. ${HONAP_NEVEK[Number(ho) - 1]}` };
            })}
            onChange={(ertek) => setHonap(ertek as string)}
            className="w-[190px]"
          />
        )}
        {canEdit && (
          <div className="flex flex-wrap items-center gap-1.5">
            {DISZPO_SZINEK.map((szin) => (
              <button
                key={szin}
                type="button"
                disabled={!kijelolt || busy}
                title={SZIN_LEIRAS[szin].jelentes}
                onClick={() =>
                  kijelolt && mentesCella(kijelolt.sor, kijelolt.oszlop, { szin, szin_valtozik: true })
                }
                style={{ backgroundColor: SZIN_LEIRAS[szin].hatter, color: SZIN_LEIRAS[szin].szoveg }}
                className="rounded-[var(--radius)] px-2.5 py-1 text-[12px] font-medium disabled:opacity-40"
              >
                {SZIN_LEIRAS[szin].cimke}
              </button>
            ))}
            <button
              type="button"
              disabled={!kijelolt || busy}
              onClick={() => kijelolt && mentesCella(kijelolt.sor, kijelolt.oszlop, { szin: null, szin_valtozik: true })}
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Szín törlése
            </button>
          </div>
        )}
        <span className="text-[12px] text-text-muted">
          {kijelolt
            ? `Kijelölve: ${kijeloltOszlop?.cimke ?? `#${kijelolt.oszlop + 1}`} – ${
                munkalap.sorok.find((s) => s.idx === kijelolt.sor)?.datum ?? `${kijelolt.sor + 1}. sor`
              }`
            : "Kattints egy cellára a színezéshez · dupla kattintás: szöveg"}
        </span>
      </div>

      {/* Az oszlop-ember kötés: enélkül az oszlop színei nem számítanak bele a
          munkanap-számlálásba (lásd backend routes/diszpo_tabla.py). */}
      {canEdit && kijeloltOszlop && munkalap.fejlec_sorok > 1 && (
        <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2">
          <span className="text-[12.5px] text-text-secondary">
            „{kijeloltOszlop.cimke ?? "névtelen oszlop"}” oszlop munkatársa:
          </span>
          <span className="text-[13px] text-text-primary">
            {kijeloltOszlop.employee_nev ?? "nincs hozzákötve"}
          </span>
          {kotesNyitva ? (
            <KeresosSelect
              value={kijeloltOszlop.employee_id != null ? String(kijeloltOszlop.employee_id) : null}
              options={emberek.map((e) => ({ value: String(e.id), label: e.nev }))}
              onChange={(ertek) => kotesMentes(kijeloltOszlop.idx, ertek ? Number(ertek) : null)}
              placeholder="Válassz munkatársat…"
              className="w-[240px]"
            />
          ) : (
            <button
              type="button"
              onClick={() => setKotesNyitva(true)}
              className="text-[12px] text-text-accent hover:underline"
            >
              {kijeloltOszlop.employee_id ? "Módosítás" : "Hozzákötés"}
            </button>
          )}
          {!kijeloltOszlop.employee_id && (
            <span className="text-[11.5px] text-text-warning">
              Kötés nélkül ennek az oszlopnak a napjai nem számítanak bele a munkanap-számlálásba.
            </span>
          )}
        </div>
      )}

      <div className="overflow-auto rounded-[var(--radius)] border border-border" style={{ maxHeight: "70vh" }}>
        <table className="border-collapse text-[12px]">
          <tbody>
            {lathatoSorok.map((sor) => {
              const fejlecSor = sor.idx < munkalap.fejlec_sorok;
              const munkanapok = fejlecSor
                ? 0
                : oszlopok.filter((o) => MUNKANAP_SZINEK.has(cellaTerkep.get(`${sor.idx}:${o.idx}`)?.szin ?? "")).length;
              return (
                <tr key={sor.idx} className={sor.elvalaszto ? "bg-surface-3" : undefined}>
                  {oszlopok.map((oszlop) => {
                    const cella = cellaTerkep.get(`${sor.idx}:${oszlop.idx}`);
                    const kijeloltE = kijelolt?.sor === sor.idx && kijelolt?.oszlop === oszlop.idx;
                    const szerkesztettE =
                      szerkesztett?.sor === sor.idx && szerkesztett?.oszlop === oszlop.idx;
                    return (
                      <td
                        key={oszlop.idx}
                        onClick={() => canEdit && setKijelolt({ sor: sor.idx, oszlop: oszlop.idx })}
                        onDoubleClick={() =>
                          canEdit &&
                          setSzerkesztett({ sor: sor.idx, oszlop: oszlop.idx, ertek: cella?.ertek ?? "" })
                        }
                        style={cellaStilus(cella?.szin ?? null)}
                        className={`min-w-[86px] max-w-[190px] whitespace-pre-line border border-border px-1.5 py-1 align-top ${
                          fejlecSor ? "sticky top-0 z-10 bg-surface-2 font-medium text-text-primary" : ""
                        } ${kijeloltE ? "outline outline-2 -outline-offset-2 outline-text-accent" : ""} ${
                          canEdit ? "cursor-pointer" : ""
                        }`}
                      >
                        {szerkesztettE ? (
                          <input
                            autoFocus
                            value={szerkesztett.ertek}
                            onChange={(e) => setSzerkesztett({ ...szerkesztett, ertek: e.target.value })}
                            onBlur={() => {
                              mentesCella(sor.idx, oszlop.idx, {
                                ertek: szerkesztett.ertek,
                                ertek_valtozik: true,
                              });
                              setSzerkesztett(null);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") e.currentTarget.blur();
                              if (e.key === "Escape") setSzerkesztett(null);
                            }}
                            className="w-full bg-surface-1 px-1 py-0.5 text-[12px] text-text-primary outline-none"
                          />
                        ) : (
                          (cella?.ertek ?? "")
                        )}
                      </td>
                    );
                  })}
                  {/* A sor munkanapjainak száma - ránézésre látszik, hány
                      emberünk dolgozott aznap. */}
                  {!fejlecSor && !sor.elvalaszto && munkalap.fejlec_sorok > 1 && (
                    <td className="whitespace-nowrap border border-border px-2 py-1 text-right text-text-muted">
                      {munkanapok || ""}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-text-muted">
        {DISZPO_SZINEK.map((szin) => (
          <span key={szin} className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: SZIN_LEIRAS[szin].hatter }}
            />
            {SZIN_LEIRAS[szin].jelentes}
          </span>
        ))}
      </div>
    </div>
  );
}
