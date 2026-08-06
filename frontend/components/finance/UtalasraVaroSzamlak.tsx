"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Download, RefreshCw } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import type { UtalasraVaroTetel } from "@/lib/api";
import { formatFt } from "@/lib/ido";

/** Utalásra váró számlák: ami már megérkezett hozzánk számlaként, de még nem
 * utaltuk el (kiadások, külsős és belsős TIG-ek egy listában).
 *
 * A lényeg a kijelölés: az utalási körhöz ki lehet pipálni a tételeket, és a
 * hozzájuk tartozó számlák EGYETLEN ZIP-ben letölthetők - így nem kell
 * egyenként végigkattintani három különböző listát. A kijelölt tételek összege
 * is látszik, hogy az utalás előtt legyen mihez hasonlítani. */
export function UtalasraVaroSzamlak({ kezdeti }: { kezdeti: UtalasraVaroTetel[] }) {
  const [tetelek, setTetelek] = useState(kezdeti);
  const [kijelolt, setKijelolt] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => setTetelek(kezdeti), [kezdeti]);

  // Ami közben eltűnt a listáról (mert kifizetettre került), az a kijelölésből
  // is essen ki - különben egy már elutalt tétel is bekerülne a csomagba.
  const letezoKulcsok = useMemo(() => new Set(tetelek.map((t) => t.kulcs)), [tetelek]);
  const aktivKijeloles = useMemo(
    () => [...kijelolt].filter((k) => letezoKulcsok.has(k)),
    [kijelolt, letezoKulcsok],
  );

  const kijeloltOsszeg = tetelek
    .filter((t) => aktivKijeloles.includes(t.kulcs))
    .reduce((sum, t) => sum + (t.osszeg ?? 0), 0);
  const mindKijelolve = tetelek.length > 0 && aktivKijeloles.length === tetelek.length;

  function valt(kulcs: string) {
    setKijelolt((elozo) => {
      const uj = new Set(elozo);
      if (uj.has(kulcs)) uj.delete(kulcs);
      else uj.add(kulcs);
      return uj;
    });
  }

  function mindet() {
    setKijelolt(mindKijelolve ? new Set() : new Set(tetelek.map((t) => t.kulcs)));
  }

  async function frissit() {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch("/api/v1/finance/utalasra-varo");
      if (res.ok) setTetelek(await res.json());
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function letolt() {
    if (aktivKijeloles.length === 0) return;
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch("/api/v1/finance/utalasra-varo/zip", {
        method: "POST",
        body: JSON.stringify({ kulcsok: aktivKijeloles }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen letöltés (HTTP ${res.status})`);
        return;
      }
      // A végpont bejelentkezést igényel, ezért nem lehet sima <a href> - a
      // választ blobként mentjük le (ugyanaz a minta, mint a havi csomagnál).
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ma = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      a.download = `utalasra_varo_szamlak_${ma}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (tetelek.length === 0) {
    return (
      <p className="text-[13px] text-text-muted">
        Nincs utalásra váró számla - minden feltöltött számla ki van fizetve.
      </p>
    );
  }

  const ma = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy || aktivKijeloles.length === 0}
          onClick={letolt}
          className="btn btn-primary inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          <Download size={14} />
          {busy ? "Készül…" : `Kijelöltek számlái ZIP-ben (${aktivKijeloles.length})`}
        </button>
        <span className="text-[13px] text-text-secondary">
          Kijelölve: <span className="font-medium text-text-primary tabular-nums">{formatFt(kijeloltOsszeg)}</span>
        </span>
        <button
          type="button"
          disabled={busy}
          onClick={frissit}
          className="inline-flex items-center gap-1.5 text-[12.5px] text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          <RefreshCw size={13} />
          Frissítés
        </button>
        {hiba && <span className="text-[12.5px] text-text-danger">{hiba}</span>}
      </div>

      <div className="overflow-x-auto">
        <table className="os-table w-full border-collapse text-[13px]">
          <thead>
            <tr>
              <th className="w-8">
                <input
                  type="checkbox"
                  checked={mindKijelolve}
                  onChange={mindet}
                  aria-label="Mindet kijelöl"
                  className="cursor-pointer"
                />
              </th>
              <th className="text-left">Tétel</th>
              <th className="text-left">Kinek</th>
              <th className="text-left">Típus</th>
              <th className="text-left">Fizetési határidő</th>
              <th className="text-right">Számlák</th>
              <th className="text-right">Összeg</th>
            </tr>
          </thead>
          <tbody>
            {tetelek.map((t) => {
              const lejart = t.hatarido !== null && t.hatarido < ma;
              return (
                <tr key={t.kulcs}>
                  <td>
                    <input
                      type="checkbox"
                      checked={aktivKijeloles.includes(t.kulcs)}
                      onChange={() => valt(t.kulcs)}
                      aria-label={`${t.megnevezes} kijelölése`}
                      className="cursor-pointer"
                    />
                  </td>
                  <td>
                    {t.link ? (
                      <Link href={t.link} className="text-text-accent hover:underline">
                        {t.megnevezes}
                      </Link>
                    ) : (
                      t.megnevezes
                    )}
                  </td>
                  <td className="text-text-secondary">{t.kinek ?? "–"}</td>
                  <td className="text-text-secondary">{t.tipus}</td>
                  {/* A lejárt határidő pirosan: ezeket kell először utalni. */}
                  <td className={lejart ? "text-text-danger" : "text-text-secondary"}>{t.hatarido ?? "–"}</td>
                  <td className="text-right tabular-nums text-text-secondary">{t.szamla_db}</td>
                  <td className="text-right tabular-nums">{t.osszeg === null ? "–" : formatFt(t.osszeg)}</td>
                </tr>
              );
            })}
            <tr className="font-medium">
              <td colSpan={6} className="text-text-secondary">
                Összesen ({tetelek.length} tétel)
              </td>
              <td className="text-right tabular-nums text-text-primary">
                {formatFt(tetelek.reduce((sum, t) => sum + (t.osszeg ?? 0), 0))}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
