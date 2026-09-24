"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { LaraGeminiAllapot } from "@/lib/api";

/** Lara GEMINI-KAPCSOLATA és gyorsított tanulása (kliens).
 *
 * Lara ugyanazt a Gemini-kapcsolatot használja, mint az AI asszisztens (egy
 * kulcs, egy modell). Itt látszik, mely funkciói használják, él-e a kapcsolat,
 * és mit tanult a Geminivel (partner-profilok, önreflexió). Minden eredmény
 * jelölt: a Tudástárban hagyod jóvá. */
export function LaraGemini({ kezdo, canRun }: { kezdo: LaraGeminiAllapot | null; canRun: boolean }) {
  const router = useRouter();
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState<"teszt" | "tanulas" | null>(null);

  if (!kezdo) return <p className="text-[13px] text-text-secondary">Az állapot nem tölthető be.</p>;
  const a = kezdo;

  async function teszt() {
    setUzenet(null);
    setHiba(null);
    setFut("teszt");
    try {
      const res = await authFetch("/api/v1/admin-agent/gemini/test", { method: "POST" });
      const d = (await res.json().catch(() => ({}))) as { ok?: boolean; uzenet?: string; ms?: number; detail?: unknown };
      if (res.ok && d.ok) setUzenet(`${d.uzenet ?? "A Gemini-kapcsolat él."}${d.ms ? ` (${d.ms} ms)` : ""}`);
      else setHiba(d.uzenet ?? (typeof d.detail === "string" ? d.detail : "A kapcsolat ellenőrzése nem sikerült."));
    } finally {
      setFut(null);
    }
  }

  async function tanul() {
    setUzenet(null);
    setHiba(null);
    setFut("tanulas");
    try {
      const res = await authFetch("/api/v1/admin-agent/gemini/learn", { method: "POST" });
      const d = (await res.json().catch(() => ({}))) as {
        allapot?: string;
        profil?: Record<string, number>;
        reflexio?: { allapot?: string; uj_tanulsag?: number };
        detail?: unknown;
      };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A Gemini-tanulás nem sikerült.");
        return;
      }
      if (d.allapot === "beallitas_szukseges") setHiba("Beállítás szükséges: a szerveren nincs Gemini-kulcs.");
      else if (d.allapot === "kikapcsolva") setHiba("A Gemini-tanulás ki van kapcsolva a Beállításokban.");
      else {
        const p = d.profil ?? {};
        setUzenet(
          `Kész: ${(p.uj ?? 0) + (p.frissult ?? 0)} partner-profil, ${p.szabalyjavaslat ?? 0} szabályjavaslat, ` +
            `${d.reflexio?.uj_tanulsag ?? 0} új tanulság — jóváhagyásra várnak a Tudástárban.`,
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
        Lara ugyanazt a Gemini-kapcsolatot használja, mint az AI asszisztens — külön kulcs nem kell. Éjszakánként a
        Geminivel <b>partner-profilt</b> ír ott, ahol már legalább 3 jóváhagyott eset van (hogyan dolgozunk az adott
        partnerrel, szabályjavaslattal), és <b>önreflexiót</b> végez: átnézi a kérdéseire adott válaszokat és a javításokat,
        és tanulságokat ír arról, mit csinál ezentúl másképp. Minden eredmény jelölt — a{" "}
        <Link href="/admin-agent/tudastar" className="text-text-accent hover:underline">
          Tudástárban
        </Link>{" "}
        hagyod jóvá; a saját kódját, jogosultságait és korlátait Lara nem írhatja át.
      </p>

      <div
        className={`mb-3 rounded-[var(--radius)] px-3 py-2 text-[13px] ${
          a.kulcs_beallitva ? "bg-bg-success text-text-success" : "bg-bg-warning text-text-warning"
        }`}
      >
        {a.kulcs_beallitva
          ? `Bekötve — modell: ${a.modell}${a.embedding_modell ? `, keresés: ${a.embedding_modell}` : ""} (ugyanaz, mint az AI asszisztensé).`
          : "Beállítás szükséges: a szerveren nincs GEMINI_API_KEY. Ugyanaz a kulcs kell, amit az AI asszisztens használ — ha ott működik, Lara is azonnal megkapja."}
      </div>

      {uzenet && <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>}
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}

      {canRun && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={fut !== null}
            onClick={teszt}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-primary hover:bg-surface-3 disabled:opacity-50"
          >
            {fut === "teszt" ? "Ellenőrzés…" : "Kapcsolat ellenőrzése"}
          </button>
          <button
            type="button"
            disabled={fut !== null || !a.kulcs_beallitva}
            onClick={tanul}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            {fut === "tanulas" ? "Lara tanul a Geminivel… (akár pár perc)" : "Tanulás a Geminivel most"}
          </button>
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Szam cimke="Partner-profil" ertek={a.profilok.osszes} al={`${a.profilok.jovahagyott} jóváhagyva`} />
        <Szam cimke="Tanulság (önreflexió)" ertek={a.tanulsagok.osszes} al={`${a.tanulsagok.jovahagyott} jóváhagyva`} />
        <Szam
          cimke="Utolsó Gemini-tanulás"
          ertek={a.utolso_futas.ido ? new Date(a.utolso_futas.ido).toLocaleDateString("hu-HU") : "—"}
          al="éjszakánként magától"
        />
        <Szam
          cimke="Gemini-funkciók"
          ertek={`${a.funkciok.filter((f) => f.be).length}/${a.funkciok.length}`}
          al="bekapcsolva"
        />
      </div>

      {a.utolso_reflexio.osszefoglalo && (
        <div className="mb-4 rounded-[var(--radius)] border border-border bg-surface-3 px-3.5 py-3">
          <p className="mb-1 text-[11.5px] uppercase tracking-[0.08em] text-text-muted">
            Lara önreflexiója
            {a.utolso_reflexio.ido ? ` · ${new Date(a.utolso_reflexio.ido).toLocaleDateString("hu-HU")}` : ""}
          </p>
          <p className="text-[13px] text-text-primary">{a.utolso_reflexio.osszefoglalo}</p>
          {(a.utolso_reflexio.gyenge_pontok ?? []).length > 0 && (
            <p className="mt-1.5 text-[12.5px] text-text-secondary">
              Gyenge pontjaim: {(a.utolso_reflexio.gyenge_pontok ?? []).join(" · ")}
            </p>
          )}
        </div>
      )}

      <p className="mb-1.5 text-[12px] text-text-muted">Mire használja Lara a Geminit</p>
      <ul className="flex flex-wrap gap-1.5">
        {a.funkciok.map((f) => (
          <li
            key={f.kulcs}
            className={`rounded-full border px-2.5 py-0.5 text-[12.5px] ${
              f.be ? "border-border text-text-secondary" : "border-border text-text-muted line-through"
            }`}
          >
            {f.nev}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Szam({ cimke, ertek, al }: { cimke: string; ertek: number | string; al?: string }) {
  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
      <p className="text-[11.5px] text-text-muted">{cimke}</p>
      <p className="text-[20px] font-medium tabular-nums text-text-primary">{ertek}</p>
      {al && <p className="text-[11.5px] text-text-muted">{al}</p>}
    </div>
  );
}
