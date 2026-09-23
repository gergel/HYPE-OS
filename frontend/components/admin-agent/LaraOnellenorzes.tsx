"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";
import type { OnellenorzesFutas } from "@/lib/api";

function szazalek(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`;
}

/** Lara ÖNELLENŐRZÉSE (kliens).
 *
 * Lara a rögzített számlákra „vakon" (az adott számla saját tanulsága nélkül)
 * megmondja, mit javasolt volna a jelenlegi tudásával, és összeveti a
 * valósággal. A futásonkénti találati arány mutatja, hogyan tanul; ahol nem érti
 * az eltérést, kérdez (Kérdések oldal). Kétóránként magától is lefut. */
export function LaraOnellenorzes({ kezdo, canRun }: { kezdo: OnellenorzesFutas[]; canRun: boolean }) {
  const router = useRouter();
  const [futasok, setFutasok] = useState(kezdo);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState(false);
  const utolso = futasok[0];

  async function futtat() {
    setUzenet(null);
    setHiba(null);
    setFut(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/self-check", { method: "POST" });
      if (!res.ok) {
        setHiba("Az önellenőrzés nem sikerült.");
        return;
      }
      const d = (await res.json()) as OnellenorzesFutas;
      setFutasok((p) => [{ ...d, id: Date.now(), trigger: "onellenorzes:kezi", veg_at: new Date().toISOString() }, ...p]);
      setUzenet(
        `Kész: ${d.ellenorzott ?? 0} rögzített számlát ellenőriztem — ${d.egyezik ?? 0} eltaláltam, ${d.elter ?? 0} eltért, ` +
          `${d.nem_tudta ?? 0} esetben nem tudtam javasolni. ${d.uj_kerdes ?? 0} új kérdésem van` +
          (d.bovitett_kerdes ? `, ${d.bovitett_kerdes} meglévő kérdéshez új eset került` : "") +
          ".",
      );
      router.refresh();
    } finally {
      setFut(false);
    }
  }

  return (
    <div>
      <p className="mb-3 text-[12px] text-text-muted">
        Lara a tanulás kezdete óta rögzített számlákra megmondja, mit javasolt volna a mostani tudásával (az adott
        számla saját tanulsága nélkül), és összeveti azzal, amit rögzítettetek. Ahol nem érti az eltérést,{" "}
        <Link href="/admin-agent/kerdesek" className="text-text-accent hover:underline">
          kérdez
        </Link>
        . Kétóránként magától is lefut, ha a „Tanulás és megfigyelés” be van kapcsolva.
      </p>
      {uzenet && (
        <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>
      )}
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      {canRun && (
        <button
          type="button"
          disabled={fut}
          onClick={futtat}
          className="mb-4 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
        >
          {fut ? "Önellenőrzés fut…" : "Önellenőrzés most"}
        </button>
      )}
      {!utolso ? (
        <p className="text-[13px] text-text-secondary">Még nem futott önellenőrzés.</p>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Szam cimke="Lara találati aránya" ertek={szazalek(utolso.talalati_arany)} al="eltalált / összes ellenőrzött" />
            <Szam cimke="Ellenőrzött számla" ertek={String(utolso.ellenorzott ?? 0)} />
            <Szam
              cimke="Nem tudta / eltért"
              ertek={`${utolso.nem_tudta ?? 0} / ${utolso.elter ?? 0}`}
              al={utolso.megmagyarazva ? `${utolso.megmagyarazva} már megmagyarázva` : undefined}
            />
            <Szam cimke="Tudása" ertek={String(utolso.szabalyok ?? 0)} al={`élesített szabály · ${utolso.tanult_partnerek ?? 0} tanult partner`} />
          </div>
          <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                  <th className="px-3 py-2 font-medium">Mikor</th>
                  <th className="px-3 py-2 font-medium">Ellenőrzött</th>
                  <th className="px-3 py-2 font-medium">Eltalálta</th>
                  <th className="px-3 py-2 font-medium">Eltért</th>
                  <th className="px-3 py-2 font-medium">Nem tudta</th>
                  <th className="px-3 py-2 font-medium">Találati arány</th>
                  <th className="px-3 py-2 font-medium">Új kérdés</th>
                </tr>
              </thead>
              <tbody>
                {futasok.slice(0, 20).map((f) => (
                  <tr key={f.id} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 text-text-secondary">
                      {f.veg_at ? new Date(f.veg_at).toLocaleString("hu-HU") : "—"}
                      <span className="ml-1 text-[11px] text-text-muted">
                        {f.trigger.endsWith("kezi") ? "kézi" : f.trigger.endsWith("utemezett") ? "ütemezett" : ""}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.ellenorzott ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.egyezik ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.elter ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.nem_tudta ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{szazalek(f.talalati_arany)}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.uj_kerdes ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Szam({ cimke, ertek, al }: { cimke: string; ertek: string; al?: string }) {
  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
      <p className="text-[11.5px] text-text-muted">{cimke}</p>
      <p className="text-[20px] font-medium tabular-nums text-text-primary">{ertek}</p>
      {al && <p className="text-[11.5px] text-text-muted">{al}</p>}
    </div>
  );
}
