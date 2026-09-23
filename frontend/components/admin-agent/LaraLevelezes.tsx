"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { LevelezesAllapot, LevelezesFutas } from "@/lib/api";

/** Lara LEVELEZÉS-OLVASÁSA (kliens) — a szamla@ postafiók.
 *
 * Lara a tanulás kezdete óta a postafiókba érkezett és onnan küldött összes
 * levelet szálanként végigolvassa (bejövő szöveg, a mi válaszaink,
 * csatolmányok szövege), és mindegyik szálból tudás-jelöltet készít. Jóváhagyás
 * a Tudástárban. Félóránként magától folytatja (lásd backend
 * admin_agent/levelezes.py). */
export function LaraLevelezes({ kezdo, canRun }: { kezdo: LevelezesAllapot | null; canRun: boolean }) {
  const router = useRouter();
  const [futasok, setFutasok] = useState<LevelezesFutas[]>(kezdo?.futasok ?? []);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState(false);

  if (!kezdo) return <p className="text-[13px] text-text-secondary">Az állapot nem tölthető be.</p>;

  async function futtat() {
    setUzenet(null);
    setHiba(null);
    setFut(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/mail-learning/run", { method: "POST" });
      const d = (await res.json().catch(() => ({}))) as LevelezesFutas & { detail?: unknown };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A levelezés feldolgozása nem sikerült.");
        return;
      }
      if (d.allapot === "beallitas_szukseges") {
        setHiba(`A Gmail-hozzáférés nincs beállítva a szerveren. ${d.uzenet ?? ""}`);
        return;
      }
      setFutasok((p) => [{ ...d, id: Date.now(), trigger: "levelezes:kezi", veg_at: new Date().toISOString() }, ...p]);
      setUzenet(
        `Kész: ${d.talalt_szal ?? 0} szál a postafiókban, ebből ${d.uj ?? 0} új és ${d.frissitett ?? 0} frissült tudás-jelölt` +
          (d.automatikus ? `, ${d.automatikus} gépi (no-reply) szál kihagyva` : "") +
          (d.hatravan ? `. Még ${d.hatravan} szál van hátra — a következő futás folytatja.` : "."),
      );
      router.refresh();
    } finally {
      setFut(false);
    }
  }

  return (
    <div>
      <p className="mb-3 text-[12px] text-text-muted">
        Lara a <span className="text-text-secondary">{kezdo.postafiok}</span> postafiók {kezdo.kezdet.replaceAll("-", ". ")}.
        óta érkezett és onnan küldött összes levelét szálanként végigolvassa: a bejövő levelek szövegét, a ti
        válaszaitokat és a csatolmányok szövegét (PDF, e-számla XML, Excel). Minden szálból tudás-jelölt lesz, ami a{" "}
        <Link href="/admin-agent/tudastar" className="text-text-accent hover:underline">
          Tudástárban
        </Link>{" "}
        jóváhagyás után kerül a tudásába — onnan dolgozik az e-mail-válaszoknál és a számlák elemzésénél. A postafiókot
        csak olvassa: nem jelöl olvasottnak, nem mozgat, nem válaszol. Félóránként magától folytatja.
      </p>

      {!kezdo.gmail_konfiguralt && (
        <div className="mb-3 rounded-[var(--radius)] bg-bg-warning px-3 py-2 text-[13px] text-text-warning">
          Beállítás szükséges: a szerveren nincs Gmail-hozzáférés beállítva. Amíg nincs, Lara nem tudja olvasni a
          postafiókot (lásd docs/admin-agent/operations.md).
        </div>
      )}
      {!kezdo.engedelyezve && (
        <div className="mb-3 rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[13px] text-text-secondary">
          A levelezés olvasása ki van kapcsolva —{" "}
          <Link href="/admin-agent/beallitasok" className="text-text-accent hover:underline">
            Beállítások
          </Link>
          .
        </div>
      )}
      {uzenet && <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>}
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}

      {canRun && (
        <button
          type="button"
          disabled={fut || !kezdo.engedelyezve || kezdo.leallitva}
          onClick={futtat}
          className="mb-4 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
        >
          {fut ? "Levelezés feldolgozása…" : "Levelezés feldolgozása most"}
        </button>
      )}

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Szam cimke="Feldolgozott levélszál" ertek={kezdo.feldolgozott_szalak} />
        <Szam cimke="Jóváhagyásra vár" ertek={kezdo.jelolt} al="tudás-jelölt a Tudástárban" />
        <Szam cimke="Lara tudásában" ertek={kezdo.jovahagyott} al="jóváhagyott levelezés" />
      </div>

      {futasok.length > 0 && (
        <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                <th className="px-3 py-2 font-medium">Mikor</th>
                <th className="px-3 py-2 font-medium">Szál a postafiókban</th>
                <th className="px-3 py-2 font-medium">Új jelölt</th>
                <th className="px-3 py-2 font-medium">Frissült</th>
                <th className="px-3 py-2 font-medium">Gépi, kihagyva</th>
                <th className="px-3 py-2 font-medium">Hátravan</th>
              </tr>
            </thead>
            <tbody>
              {futasok.slice(0, 10).map((f) => (
                <tr key={f.id} className="border-b border-border last:border-0">
                  <td className="px-3 py-2 text-text-secondary">
                    {f.veg_at ? new Date(f.veg_at).toLocaleString("hu-HU") : "—"}
                    <span className="ml-1 text-[11px] text-text-muted">
                      {f.trigger.endsWith("kezi") ? "kézi" : "ütemezett"}
                      {f.allapot === "leallitva" ? " · vészleállítás miatt megállt" : ""}
                    </span>
                  </td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.talalt_szal ?? 0}</td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.uj ?? 0}</td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.frissitett ?? 0}</td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.automatikus ?? 0}</td>
                  <td className="px-3 py-2 tabular-nums text-text-primary">{f.hatravan ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
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
