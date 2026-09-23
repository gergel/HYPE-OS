"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AdminReplaySummary } from "@/lib/api";

function szazalek(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`;
}

/** HYRON — Visszajátszás és találati arány (kliens).
 *
 * A tanulás kezdete óta rögzített számláknál összeveti, mit javasolt eredetileg
 * az érkeztető (és ha már elemezte, HYRON), és mit döntött végül az ember.
 * Ebből példa- és szabály-JELÖLTEK születnek (a Tudástárban jóváhagyandók), és
 * ez a mérőszám mutatja hétről hétre, javul-e a találati arány. */
export function AdminVisszajatszas({
  kezdo,
  canRun,
}: {
  kezdo: AdminReplaySummary | null;
  canRun: boolean;
}) {
  const router = useRouter();
  const [o, setO] = useState<AdminReplaySummary | null>(kezdo);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState(false);

  async function futtat() {
    setUzenet(null);
    setHiba(null);
    setFut(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/replays", { method: "POST" });
      if (!res.ok) {
        setHiba("A visszajátszás nem sikerült.");
        return;
      }
      const d = (await res.json()) as {
        uj_szamla: number;
        uj_pelda: number;
        frissitett_pelda: number;
        uj_szabaly_jelolt: number;
        frissitett_szabaly_jelolt: number;
        tanulas_kezdete: string;
        osszesites: AdminReplaySummary;
      };
      setO(d.osszesites);
      setUzenet(
        `Kész: ${d.uj_szamla} új számla visszajátszva (${d.tanulas_kezdete.replaceAll("-", ". ")}. óta), ` +
          `${d.uj_pelda} új példa-jelölt, ${d.uj_szabaly_jelolt} új szabály-jelölt` +
          (d.frissitett_szabaly_jelolt ? `, ${d.frissitett_szabaly_jelolt} frissítve` : "") +
          ". A jelöltek a Tudástárban várnak jóváhagyásra.",
      );
      router.refresh();
    } finally {
      setFut(false);
    }
  }

  return (
    <div>
      <p className="mb-3 text-[12px] text-text-muted">
        A tanulás kezdete óta rögzített számláknál összeveti, mit javasolt az érkeztető, és mit döntött végül az ember.
        Minden számlából példa-jelölt lesz (a helyes besorolással), és ha egy partner számlái legalább kétszer
        egyformán végződtek, szabály-jelölt. Üzleti adatot nem módosít; bármikor újrafuttatható, a már feldolgozott
        számlákat nem duplázza.
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
          {fut ? "Visszajátszás fut…" : "Visszajátszás a rögzített számlákon"}
        </button>
      )}

      {!o || o.szamlak === 0 ? (
        <p className="text-[13px] text-text-secondary">Még nincs visszajátszott számla.</p>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Szam cimke="Visszajátszott számla" ertek={String(o.szamlak)} />
            <Szam
              cimke="Érkeztető találati aránya"
              ertek={szazalek(o.erkezteto_arany)}
              al={`${o.egyezik} egyezett · ${o.elter} eltért`}
            />
            <Szam cimke="Érkeztető nem javasolt" ertek={String(o.nem_javasolt)} al="ember döntött egyedül" />
            <Szam
              cimke="HYRON találati aránya"
              ertek={szazalek(o.ugynok_arany)}
              al={
                o.ugynok_egyezik + o.ugynok_elter
                  ? `${o.ugynok_egyezik} egyezett · ${o.ugynok_elter} eltért`
                  : "még nem elemzett számlát döntés előtt"
              }
            />
          </div>
          <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                  <th className="px-3 py-2 font-medium">Hét</th>
                  <th className="px-3 py-2 font-medium">Számla</th>
                  <th className="px-3 py-2 font-medium">Egyezett</th>
                  <th className="px-3 py-2 font-medium">Eltért</th>
                  <th className="px-3 py-2 font-medium">Nem javasolt</th>
                  <th className="px-3 py-2 font-medium">Találati arány</th>
                </tr>
              </thead>
              <tbody>
                {o.hetente.map((h) => (
                  <tr key={h.het} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 text-text-secondary">{h.het}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{h.szamlak}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{h.egyezik}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{h.elter}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{h.nem_javasolt}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{szazalek(h.arany)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11.5px] text-text-muted">
            Találati arány = egyezett / (egyezett + eltért); ahol az érkeztető nem adott javaslatot, az nem számít bele.
            A „HYRON találati aránya” azokat a számlákat méri, amelyeket HYRON a döntés előtt elemzett.
          </p>
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
