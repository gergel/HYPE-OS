"use client";

import { Fragment, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronDown, ChevronRight, Send, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { huDatum } from "@/lib/huDate";
import { allapotJelzo, VISSZAJELZES_ALLAPOTOK } from "@/lib/visszajelzesAllapot";
import type { VagoiVisszajelzes } from "@/lib/api";

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
      const res = await authFetch(`/api/v1/feedbacks/${v.id}`, { method: "DELETE" });
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
        <select
          value={allapotSzuro}
          onChange={(e) => setAllapotSzuro(e.target.value)}
          aria-label="Szűrés állapotra"
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
        >
          <option value="">Összes állapot</option>
          {VISSZAJELZES_ALLAPOTOK.map((a) => (
            <option key={a.ertek} value={a.ertek}>
              {a.cimke}
            </option>
          ))}
        </select>
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
        <table className="w-full border-collapse text-[13px]">
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
                    <td className="py-2.5 pr-4 whitespace-nowrap">
                      <StatusBadge {...allapotJelzo(v.allapot)} />
                      {canSend && (
                        <select
                          value={v.allapot}
                          onChange={(e) => allapotValtas(v, e.target.value)}
                          disabled={busyId === v.id}
                          aria-label="Állapot átállítása"
                          title="Állapot átállítása"
                          className="mt-1 block w-full rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-0.5 text-[11.5px] text-text-secondary focus:outline-none disabled:opacity-50"
                        >
                          {VISSZAJELZES_ALLAPOTOK.map((a) => (
                            <option key={a.ertek} value={a.ertek}>
                              {a.cimke}
                            </option>
                          ))}
                        </select>
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
                        <p className="t-label mb-1.5">Megjegyzés</p>
                        <p className="mb-4 whitespace-pre-line text-[13px] text-text-secondary">
                          {v.megjegyzes || "Nincs szöveges megjegyzés."}
                        </p>

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
      )}
    </div>
  );
}
