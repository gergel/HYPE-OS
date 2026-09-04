"use client";

import { Fragment, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronDown, ChevronRight, Send, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { huDatum } from "@/lib/huDate";
import { SelectDropdown } from "@/components/SelectDropdown";
import {
  allapotCimke,
  allapotErtek,
  allapotJelzo,
  VISSZAJELZES_ALLAPOTOK,
} from "@/lib/visszajelzesAllapot";
import type { VagoiVisszajelzes } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

const ALLAPOT_CIMKEK = VISSZAJELZES_ALLAPOTOK.map((a) => a.cimke);

function pont(ertek: number | null): string {
  return ertek == null ? "–" : `${ertek}/10`;
}

/** A vágói visszajelzések gyűjtő nézete.
 *
 * Minden sor megmondja, KI írta, MELYIK anyagról, hol a kész anyag, és ha volt
 * hozzá forgatás, akkor melyik és kik voltak ott - a lenyitott részben. Innen
 * lehet egy gombbal kiküldeni a forgatás diszpó-levelére válaszként. */
export function VisszajelzesLista({
  visszajelzesek,
  canSend,
  canDelete = false,
  /** Az ANYAG lapján az anyag és a forgatás oszlop csak ismételné, ami a lap
   * tetején úgyis ott van - ott ezért kompakt alakban jelenik meg. */
  kompakt = false,
}: {
  visszajelzesek: VagoiVisszajelzes[];
  canSend: boolean;
  canDelete?: boolean;
  kompakt?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitott, setNyitott] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [kereses, setKereses] = useState("");
  const [allapotSzuro, setAllapotSzuro] = useState("");
  // Helyben szerkesztett visszajelzés (a felhasználó kérése): a három
  // pontszám és a szöveg átírható - a mentés a generikus /feedback PATCH.
  const [szerkesztettId, setSzerkesztettId] = useState<number | null>(null);
  const [piszkozat, setPiszkozat] = useState({ megjegyzes: "", nyersanyag: "", technika: "", kreativ: "" });

  const szurt = useMemo(() => {
    const q = kereses.trim().toLowerCase();
    return visszajelzesek
      .filter((v) => (allapotSzuro ? v.allapot === allapotSzuro : true))
      .filter((v) =>
        !q
          ? true
          : [v.visszajelzo_nev, v.deliverable_nev, v.project_nev, v.megjegyzes].some((m) =>
              (m ?? "").toLowerCase().includes(q),
            ),
      );
  }, [visszajelzesek, kereses, allapotSzuro]);

  async function torol(v: VagoiVisszajelzes) {
    if (!(await confirm(`Törlöd ezt a visszajelzést (${v.visszajelzo_nev ?? "ismeretlen"})?`))) return;
    setBusyId(v.id);
    try {
      // FIGYELEM: a generikus végpont "/feedback" (egyes szám, lásd backend
      // postproduction.feedback_router) - a korábbi "/feedbacks" 404 volt.
      const res = await authFetch(`/api/v1/feedback/${v.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusyId(null);
    }
  }

  async function allapotValtas(v: VagoiVisszajelzes, allapot: string) {
    setBusyId(v.id);
    try {
      const res = await authFetch(`/api/v1/vagoi-visszajelzesek/${v.id}/allapot`, {
        method: "PUT",
        body: JSON.stringify({ allapot }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusyId(null);
    }
  }

  function szerkesztesInditasa(v: VagoiVisszajelzes) {
    setSzerkesztettId(v.id);
    setPiszkozat({
      megjegyzes: v.megjegyzes ?? "",
      nyersanyag: v.nyersanyag_felhasznalhatosaga?.toString() ?? "",
      technika: v.technikai_helyesseg?.toString() ?? "",
      kreativ: v.kreativ_kepivilag?.toString() ?? "",
    });
  }

  async function szerkesztesMentese(v: VagoiVisszajelzes) {
    const szam = (s: string) => (s.trim() === "" ? null : Number(s.replace(",", ".")));
    setBusyId(v.id);
    try {
      // A mezőnevek a Feedback OSZLOPAI (a megjegyzés a visszajelzes_szoveg) -
      // a generikus PATCH nyers oszlopneveket vár (lásd backend crud_router).
      const res = await authFetch(`/api/v1/feedback/${v.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          visszajelzes_szoveg: piszkozat.megjegyzes || null,
          nyersanyag_felhasznalhatosaga: szam(piszkozat.nyersanyag),
          technikai_helyesseg: szam(piszkozat.technika),
          kreativ_kepivilag: szam(piszkozat.kreativ),
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setSzerkesztettId(null);
      router.refresh();
    } finally {
      setBusyId(null);
    }
  }

  async function kikuld(v: VagoiVisszajelzes) {
    const cimzettek = v.resztvevok.filter((r) => r.email).length;
    const kerdes = v.diszpora_kikuldve
      ? `Ez a visszajelzés már ki lett küldve. Újra elküldöd a forgatás diszpó-szálába (${cimzettek} címzett)?`
      : `Kiküldöd a visszajelzést a(z) "${v.project_nev ?? "forgatás"}" diszpó-levelére válaszként? Csak a megjegyzés és a kész anyag linkje megy ki.`;
    if (!(await confirm(kerdes))) return;
    setBusyId(v.id);
    try {
      const res = await authFetch(`/api/v1/vagoi-visszajelzesek/${v.id}/diszpo-valasz`, { method: "POST" });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        alert(`Sikertelen kiküldés: ${adat?.detail ?? res.status}`);
        return;
      }
      alert(adat?.message ?? "Kiküldve.");
      router.refresh();
    } catch (err) {
      alert(`Sikertelen kiküldés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className={`mb-4 flex-wrap items-center gap-2 ${kompakt ? "hidden" : "flex"}`}>
        <input
          value={kereses}
          onChange={(e) => setKereses(e.target.value)}
          placeholder="Keresés vágó, anyag, forgatás, szöveg szerint…"
          className="w-full max-w-[340px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
        />
        <KeresosSelect
          value={allapotSzuro}
          options={[
            { value: "", label: "Összes állapot" },
            ...VISSZAJELZES_ALLAPOTOK.map((a) => ({ value: a.ertek, label: a.cimke })),
          ]}
          onChange={setAllapotSzuro}
          className="w-[200px]"
        />
        <span className="text-[12px] text-text-muted">
          {szurt.length === visszajelzesek.length
            ? `${visszajelzesek.length} visszajelzés`
            : `${szurt.length} / ${visszajelzesek.length} visszajelzés`}
        </span>
      </div>

      {szurt.length === 0 ? (
        <p className="text-[13px] text-text-muted">
          {visszajelzesek.length === 0
            ? "Még nincs vágói visszajelzés. Az anyag oldalán a „Visszajelzés” gombbal lehet írni."
            : "Nincs találat."}
        </p>
      ) : (
        <div className="overflow-x-auto">
        <table className="os-table min-w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Mikor / ki</th>
              {!kompakt && (
                <>
                  <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Anyag</th>
                  <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Forgatás</th>
                </>
              )}
              <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Nyersanyag</th>
              <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Technika</th>
              <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Kreatív</th>
              <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Átlag</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Állapot</th>
              <th className="py-1.5 text-right font-medium text-text-secondary">Kiküldés</th>
            </tr>
          </thead>
          <tbody>
            {szurt.map((v) => {
              const nyitva = nyitott === v.id;
              return (
                <Fragment key={v.id}>
                  <tr className="border-b border-border align-top">
                    <td className="py-2.5 pr-4">
                      <button
                        type="button"
                        onClick={() => setNyitott(nyitva ? null : v.id)}
                        className="flex items-start gap-1.5 text-left text-text-primary hover:text-text-accent"
                      >
                        {nyitva ? (
                          <ChevronDown size={14} className="mt-0.5 shrink-0 text-text-muted" />
                        ) : (
                          <ChevronRight size={14} className="mt-0.5 shrink-0 text-text-muted" />
                        )}
                        <span>
                          {huDatum(v.letrehozva)}
                          <span className="block text-[11.5px] text-text-muted">
                            {v.visszajelzo_nev ?? "ismeretlen"}
                          </span>
                          {/* KIHAGYOTT visszajelzés: az űrlapot indoklással
                              átugorták - a szöveg maga az indok. */}
                          {v.kihagyva && (
                            <span className="mt-0.5 inline-block rounded bg-bg-warning px-1.5 py-0.5 text-[10.5px] font-medium text-text-warning">
                              Kihagyva
                            </span>
                          )}
                        </span>
                      </button>
                    </td>
                    {!kompakt && (
                      <>
                    <td className="py-2.5 pr-4">
                      <Link href={`/utomunka/${v.deliverable_id}`} className="text-text-accent hover:underline">
                        {v.deliverable_nev ?? `#${v.deliverable_id}`}
                      </Link>
                      {v.kesz_anyag_url && (
                        <a
                          href={v.kesz_anyag_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-[11.5px] text-text-accent hover:underline"
                        >
                          Kész anyag
                        </a>
                      )}
                    </td>
                    <td className="py-2.5 pr-4 text-text-secondary">
                      {v.project_id ? (
                        <>
                          <Link href={`/projektek/${v.project_id}`} className="text-text-accent hover:underline">
                            {v.project_nev ?? `#${v.project_id}`}
                          </Link>
                          <span className="block text-[11.5px] text-text-muted">
                            {v.forgatas_datuma ? huDatum(v.forgatas_datuma) : "nincs dátum"} ·{" "}
                            {v.resztvevok.length} résztvevő
                          </span>
                        </>
                      ) : (
                        <span className="text-text-muted">nincs forgatás</span>
                      )}
                    </td>
                      </>
                    )}
                    <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                      {pont(v.nyersanyag_felhasznalhatosaga)}
                    </td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                      {pont(v.technikai_helyesseg)}
                    </td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                      {pont(v.kreativ_kepivilag)}
                    </td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-text-primary">{pont(v.atlag)}</td>
                    {/* Az állapot magára a jelzőre kattintva szerkeszthető -
                        ugyanaz a legördülő, mint az app többi állapot-mezőjén
                        (SelectDropdown). Akinek nincs joga állítani, az a
                        sima jelzőt látja. */}
                    <td className="py-2.5 pr-4 whitespace-nowrap">
                      {canSend ? (
                        <SelectDropdown
                          value={allapotCimke(v.allapot)}
                          options={ALLAPOT_CIMKEK}
                          onChange={(cimke) => allapotValtas(v, allapotErtek(cimke))}
                          disabled={busyId === v.id}
                        />
                      ) : (
                        <StatusBadge {...allapotJelzo(v.allapot)} />
                      )}
                    </td>
                    <td className="py-2.5 text-right whitespace-nowrap">
                      {/* Amiről eldöntöttük, hogy nem küldjük ki, ott a gomb
                          nem letiltva áll, hanem EL IS TŰNIK - ne is kelljen
                          rágondolni. */}
                      {canSend && v.allapot !== "nem_kuldjuk" && (
                        <button
                          type="button"
                          onClick={() => kikuld(v)}
                          disabled={!v.kikuldheto || busyId === v.id}
                          title={v.kikuldes_akadalya ?? "Válaszlevél a forgatás diszpó-szálába"}
                          className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
                        >
                          <Send size={12} />
                          {busyId === v.id ? "Küldés…" : v.diszpora_kikuldve ? "Újraküldés" : "Diszpóra"}
                        </button>
                      )}
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => torol(v)}
                          disabled={busyId === v.id}
                          title="Visszajelzés törlése"
                          className="ml-1 rounded-[var(--radius)] p-1 align-middle text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </td>
                  </tr>

                  {nyitva && (
                    <tr className="border-b border-border bg-surface-2">
                      <td colSpan={kompakt ? 7 : 9} className="px-3 py-4">
                        {szerkesztettId === v.id ? (
                          /* SZERKESZTÉS (a felhasználó kérése): a pontszámok és
                             a szöveg átírhatók - pl. elgépelt pont, pontosított
                             megfogalmazás. */
                          <div className="mb-4 space-y-3">
                            <div className="flex flex-wrap gap-3">
                              {(
                                [
                                  ["Nyersanyag (1-10)", "nyersanyag"],
                                  ["Technika (1-10)", "technika"],
                                  ["Kreatív (1-10)", "kreativ"],
                                ] as const
                              ).map(([cimke, kulcs]) => (
                                <label key={kulcs} className="flex flex-col gap-1 text-[11.5px] text-text-muted">
                                  {cimke}
                                  <input
                                    type="number"
                                    min={1}
                                    max={10}
                                    step={0.5}
                                    value={piszkozat[kulcs]}
                                    onChange={(e) => setPiszkozat((p) => ({ ...p, [kulcs]: e.target.value }))}
                                    className="w-28 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
                                  />
                                </label>
                              ))}
                            </div>
                            <label className="flex flex-col gap-1 text-[11.5px] text-text-muted">
                              Megjegyzés
                              <textarea
                                rows={4}
                                value={piszkozat.megjegyzes}
                                onChange={(e) => setPiszkozat((p) => ({ ...p, megjegyzes: e.target.value }))}
                                className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] leading-relaxed text-text-primary focus:outline-none"
                              />
                            </label>
                            <div className="flex gap-2">
                              <button
                                type="button"
                                disabled={busyId === v.id}
                                onClick={() => szerkesztesMentese(v)}
                                className="btn btn-primary !text-[12.5px]"
                              >
                                {busyId === v.id ? "Mentés…" : "Mentés"}
                              </button>
                              <button
                                type="button"
                                onClick={() => setSzerkesztettId(null)}
                                className="btn btn-ghost !text-[12.5px]"
                              >
                                Mégse
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="mb-1.5 flex items-center gap-3">
                              <p className="t-label">Megjegyzés</p>
                              {canSend && (
                                <button
                                  type="button"
                                  onClick={() => szerkesztesInditasa(v)}
                                  className="text-[12px] text-text-accent hover:underline"
                                >
                                  Szerkesztés
                                </button>
                              )}
                            </div>
                            <p className="mb-4 whitespace-pre-line text-[13px] text-text-secondary">
                              {v.megjegyzes || "Nincs szöveges megjegyzés."}
                            </p>
                          </>
                        )}

                        {/* Kik voltak a forgatáson: nekik szól a visszajelzés,
                            és ők kapják a diszpóra küldött levelet. */}
                        <p className="t-label mb-1.5">A forgatás résztvevői</p>
                        {v.resztvevok.length === 0 ? (
                          <p className="text-[12.5px] text-text-muted">
                            {v.project_id
                              ? "Ehhez a forgatáshoz nincs stáb felvéve."
                              : "Ehhez az anyaghoz nem tartozik forgatás."}
                          </p>
                        ) : (
                          <ul className="flex flex-wrap gap-2">
                            {v.resztvevok.map((r) => (
                              <li
                                key={r.id}
                                className="rounded-[var(--radius)] bg-surface-3 px-2.5 py-1 text-[12.5px] text-text-secondary"
                              >
                                {r.full_name}
                                {r.email ? (
                                  <span className="ml-1 text-text-muted">({r.email})</span>
                                ) : (
                                  <span className="ml-1 text-text-warning">nincs email</span>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}

                        {v.kikuldes_akadalya && (
                          <p className="mt-3 text-[12px] text-text-warning">
                            Nem küldhető ki: {v.kikuldes_akadalya}
                          </p>
                        )}
                        {v.diszpora_kikuldve && (
                          <p className="mt-3 text-[12px] text-text-muted">
                            Kiküldve a diszpó-szálba: {huDatum(v.diszpora_kikuldve)}
                          </p>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        </div>
      )}
    </div>
  );
}
