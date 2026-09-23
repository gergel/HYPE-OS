"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { GyorsitasAllapot } from "@/lib/api";
import { MEGFIGYELT_FORRAS_CIMKE, TIPUS_CIMKE } from "@/components/admin-agent/allapotok";

/** Lara — GYORSÍTOTT TANULÁS (kliens).
 *
 * Ami gyorsítja, hogy az összegyűjtött tudásból használt tudás legyen:
 * - a valóság által igazolt példák automatikus jóváhagyása (szabály soha),
 * - szabályjavaslat a jóváhagyott, egybehangzó esetekből (ember élesíti),
 * - jelentés szerinti keresés (a hasonló tudás más partnernévnél is előjön),
 * - a legértékesebb várakozó jelöltek elöl (a napi összesítő is ezt küldi).
 * Lásd backend admin_agent/megerosites.py, embedding.py, osszesito.py. */
export function LaraGyorsitas({ kezdo, canRun }: { kezdo: GyorsitasAllapot | null; canRun: boolean }) {
  const router = useRouter();
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState<"megerosites" | "beagyazas" | null>(null);

  if (!kezdo) return <p className="text-[13px] text-text-secondary">Az állapot nem tölthető be.</p>;
  const b = kezdo.beallitasok;
  const m = kezdo.megerosites;
  const lefedett = kezdo.beagyazas.osszes ? Math.round((kezdo.beagyazas.beagyazva / kezdo.beagyazas.osszes) * 100) : 0;

  async function futtat(mit: "megerosites" | "beagyazas") {
    setUzenet(null);
    setHiba(null);
    setFut(mit);
    try {
      const res = await authFetch(
        `/api/v1/admin-agent/learning-boost/${mit === "megerosites" ? "confirm" : "embed"}`,
        { method: "POST" },
      );
      const d = (await res.json().catch(() => ({}))) as Record<string, unknown> & { detail?: unknown };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A futtatás nem sikerült.");
        return;
      }
      if (mit === "megerosites") {
        setUzenet(
          `Kész: ${d.auto_jovahagyott ?? 0} példát hagytam jóvá magam (a valóság igazolta), ` +
            `${d.uj_szabalyjavaslat ?? 0} új szabályjavaslat vár rád a Tudástárban.`,
        );
      } else {
        setUzenet(
          d.hiba
            ? `Részben kész (${d.beagyazva ?? 0} darab) — a beágyazó hibát jelzett: ${String(d.hiba)}`
            : `Kész: ${d.beagyazva ?? 0} tudás-darab lett kereshető jelentés szerint.`,
        );
      }
      router.refresh();
    } finally {
      setFut(null);
    }
  }

  return (
    <div>
      <p className="mb-3 text-[12px] text-text-muted">
        Ha ugyanannál a partnernél legalább {m.min_eset}-szor egybehangzóan ugyanúgy döntöttetek, Lara ezeket a példákat
        magától jóváhagyja: a valóság már igazolta őket. Szabályt sosem élesít magától, csak javasol. A jóváhagyott tudást a
        jelentése alapján is megtalálja, nem csak ha a partner neve egyezik. Minden automatikus jóváhagyás egy kattintással
        visszavehető a{" "}
        <Link href="/admin-agent/tudastar" className="text-text-accent hover:underline">
          Tudástárban
        </Link>
        .
      </p>
      {uzenet && <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>}
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Szam
          cimke="Magától jóváhagyva"
          ertek={m.auto_jovahagyott}
          al={b.auto_jovahagyas ? (m.auto_elvetve ? `${m.auto_elvetve} visszavéve` : "a valóság igazolta") : "kikapcsolva"}
        />
        <Szam cimke="Szabályjavaslat" ertek={m.szabalyjavaslat} al="élesítésre vár" />
        <Szam cimke="Jóváhagyásra vár" ertek={kezdo.varakozo} al={b.napi_osszesito ? "reggel összesítőt kapsz" : undefined} />
        <Szam
          cimke="Jelentés szerint kereshető"
          ertek={kezdo.beagyazas.beagyazva}
          al={
            !b.szemantikus_kereses
              ? "kikapcsolva"
              : kezdo.beagyazas.elerheto
                ? `${lefedett}% a ${kezdo.beagyazas.osszes} darabból`
                : "Beállítás szükséges: Gemini-kulcs"
          }
        />
      </div>

      {canRun && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={fut !== null || !b.auto_jovahagyas}
            onClick={() => futtat("megerosites")}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            {fut === "megerosites" ? "Megerősítés…" : "Megerősítés most"}
          </button>
          <button
            type="button"
            disabled={fut !== null || !b.szemantikus_kereses || !kezdo.beagyazas.elerheto}
            onClick={() => futtat("beagyazas")}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-4 disabled:opacity-50"
          >
            {fut === "beagyazas" ? "Beágyazás…" : "Kereshetővé tétel most"}
          </button>
        </div>
      )}

      {kezdo.legertekesebb.length > 0 && (
        <div>
          <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-[12px] text-text-muted">Ezeket érdemes elsőként jóváhagyni</p>
            <Link href="/admin-agent/tudastar?rendezes=ertek" className="text-[12px] text-text-accent hover:underline">
              Mind érték szerint a Tudástárban →
            </Link>
          </div>
          <ul className="flex flex-col gap-1.5">
            {kezdo.legertekesebb.slice(0, 5).map((p) => (
              <li key={p.id} className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2">
                <div className="mb-0.5 flex flex-wrap items-center gap-1.5">
                  <span className="rounded-[var(--radius)] bg-surface-2 px-2 py-0.5 text-[11px] text-text-secondary">
                    {forrasCimke(p.forras, p.hatokor)}
                  </span>
                  {(p.ertek_okok ?? []).map((o) => (
                    <span key={o} className="text-[11px] text-text-muted">
                      · {o}
                    </span>
                  ))}
                </div>
                <p className="line-clamp-2 text-[13px] text-text-primary">{p.tartalom}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function forrasCimke(forras: string | null, hatokor: string): string {
  if (forras?.startsWith("levelezes:")) return "Levelezés";
  if (forras?.startsWith("asszisztens:")) return "AI asszisztens";
  if (forras?.startsWith("visszajatszas:")) return "Rögzített számla";
  if (forras?.startsWith("megfigyeles:")) {
    const kulcs = forras.split(":")[1];
    if (kulcs && MEGFIGYELT_FORRAS_CIMKE[kulcs]) return MEGFIGYELT_FORRAS_CIMKE[kulcs];
  }
  return TIPUS_CIMKE[hatokor] ?? hatokor;
}

function Szam({ cimke, ertek, al }: { cimke: string; ertek: number; al?: string }) {
  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
      <p className="text-[11.5px] text-text-muted">{cimke}</p>
      <p className="text-[20px] font-medium tabular-nums text-text-primary">{ertek}</p>
      {al && <p className="text-[11.5px] text-text-muted">{al}</p>}
    </div>
  );
}
