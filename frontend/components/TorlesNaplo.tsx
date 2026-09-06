"use client";

import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";

type TorlesSor = {
  id: number;
  tabla: string;
  rekord_id: number;
  megnevezes: string | null;
  torolte: string | null;
  mikor: string;
  visszaallitva: boolean;
};

/** A táblanevek emberi (magyar) címkéi a naplóhoz - amire nincs bejegyzés,
 * az a nyers táblanévvel jelenik meg. */
const TABLA_CIMKEK: Record<string, string> = {
  projects: "Projekt",
  deliverables: "Utómunka anyag",
  tasks: "Feladat",
  project_codes: "Projektkód",
  employees: "Munkatárs",
  contracts: "Szerződés",
  expenses: "Kiadás",
  timesheets: "Munkaidő-elszámolás",
  feedbacks: "Vágói visszajelzés",
  campaigns: "Kampány",
  clients: "Ügyfél",
  contacts: "Megrendelői kontakt",
  equipment: "Eszköz",
  hype_todo_items: "HYPE To-Do",
  autok: "Autó",
  arajanlatok: "Árajánlat",
};

function idopont(iso: string): string {
  return new Date(iso).toLocaleString("hu-HU", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** TÖRLÉSI NAPLÓ (a felhasználó kérése): az admin lássa, ki mit törölt
 * bárhonnan a rendszerben, és vissza tudja állítani. A pillanatképeket a
 * rendszer 30 napig őrzi (lásd backend services/visszavonas) - a
 * visszaállítás az eredeti azonosítóval hozza vissza a sort, a kaszkáddal
 * törölt kapcsolt rekordok nélkül. */
export function TorlesNaplo() {
  const confirm = useConfirm();
  const [sorok, setSorok] = useState<TorlesSor[] | null>(null);
  const [kereses, setKereses] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    authFetch("/api/v1/visszavonas/torlesek")
      .then((res) => (res.ok ? res.json() : []))
      .then((adat: TorlesSor[]) => setSorok(adat))
      .catch(() => setSorok([]));
  }, []);

  async function visszaallit(sor: TorlesSor) {
    const nev = sor.megnevezes ?? `#${sor.rekord_id}`;
    if (!(await confirm(`Visszaállítod: ${TABLA_CIMKEK[sor.tabla] ?? sor.tabla} – "${nev}"?`))) return;
    setBusyId(sor.id);
    try {
      const res = await authFetch(`/api/v1/visszavonas/torles/${sor.id}`, { method: "POST" });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        alert(`Sikertelen visszaállítás: ${adat?.detail ?? res.status}`);
        return;
      }
      setSorok((elozo) => (elozo ?? []).map((s) => (s.id === sor.id ? { ...s, visszaallitva: true } : s)));
    } catch (err) {
      alert(`Sikertelen visszaállítás (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  if (sorok === null) return <p className="text-[13px] text-text-muted">Betöltés…</p>;
  if (sorok.length === 0) {
    return <p className="text-[13px] text-text-muted">Az elmúlt 30 napban nem volt visszaállítható törlés.</p>;
  }

  const kifejezés = kereses.trim().toLocaleLowerCase("hu-HU");
  const szurt = kifejezés
    ? sorok.filter((s) =>
        [s.megnevezes, s.torolte, TABLA_CIMKEK[s.tabla] ?? s.tabla]
          .filter(Boolean)
          .some((mezo) => String(mezo).toLocaleLowerCase("hu-HU").includes(kifejezés)),
      )
    : sorok;

  return (
    <div>
      <input
        type="search"
        value={kereses}
        onChange={(e) => setKereses(e.target.value)}
        placeholder="Keresés (mit töröltek, ki törölte, típus)…"
        className="mb-3 w-80 max-w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
      />
      <div className="max-h-[480px] overflow-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border text-left text-text-secondary">
              <th className="py-1.5 pr-4 font-medium">Mikor</th>
              <th className="py-1.5 pr-4 font-medium">Mit</th>
              <th className="py-1.5 pr-4 font-medium">Ki törölte</th>
              <th className="py-1.5 text-right font-medium">Visszaállítás</th>
            </tr>
          </thead>
          <tbody>
            {szurt.map((s) => (
              <tr key={s.id} className="border-b border-border/60 align-top">
                <td className="whitespace-nowrap py-2 pr-4 text-text-secondary">{idopont(s.mikor)}</td>
                <td className="py-2 pr-4">
                  <span className="text-text-primary [overflow-wrap:anywhere]">
                    {s.megnevezes ?? `#${s.rekord_id}`}
                  </span>
                  <span className="ml-2 rounded bg-surface-3 px-1.5 py-0.5 text-[11px] text-text-secondary">
                    {TABLA_CIMKEK[s.tabla] ?? s.tabla}
                  </span>
                </td>
                <td className="whitespace-nowrap py-2 pr-4 text-text-secondary">{s.torolte ?? "ismeretlen"}</td>
                <td className="py-2 text-right">
                  {s.visszaallitva ? (
                    <span className="rounded bg-bg-success px-1.5 py-0.5 text-[11.5px] font-medium text-text-success">
                      Visszaállítva
                    </span>
                  ) : (
                    <button
                      type="button"
                      disabled={busyId === s.id}
                      onClick={() => void visszaallit(s)}
                      className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                    >
                      <RotateCcw size={13} />
                      {busyId === s.id ? "Visszaállítás…" : "Visszaállítás"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {szurt.length === 0 && (
              <tr>
                <td colSpan={4} className="py-4 text-center text-text-muted">
                  Nincs találat erre: „{kereses.trim()}”.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
