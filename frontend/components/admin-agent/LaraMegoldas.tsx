"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { LaraLepes, LaraMegoldas as Megoldas } from "@/lib/api";

/** Lara MEGOLDÁSI JAVASLATA egy feladathoz (kliens).
 *
 * Az alap-lépések a kérdés adataiból azonnal megvannak (javítási feladatnál);
 * Lara saját javaslata utánanéz a rendszerben az AI asszisztens csak-olvasó
 * eszközeivel, és konkrét lépéseket ad. Lara itt semmit nem módosít. */
export function LaraMegoldas({
  taskId,
  kezdo,
  canEdit,
}: {
  taskId: number;
  kezdo: Megoldas | null | undefined;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [m, setM] = useState<Megoldas | null>(kezdo ?? null);
  const [fut, setFut] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function kerj() {
    setHiba(null);
    setFut(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/solution`, { method: "POST" });
      const d = (await res.json().catch(() => ({}))) as { detail?: unknown; lara_megoldas?: Megoldas | null };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A megoldási javaslat nem készült el.");
        return;
      }
      setM(d.lara_megoldas ?? null);
      router.refresh();
    } finally {
      setFut(false);
    }
  }

  const ai = m?.ai;
  return (
    <div className="flex flex-col gap-3">
      {hiba && <div className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}

      {ai && (
        <div className="rounded-[var(--radius)] border border-text-accent/40 bg-surface-3 px-3.5 py-3">
          <p className="mb-1.5 flex flex-wrap items-center gap-x-2 text-[11.5px] uppercase tracking-[0.08em] text-text-muted">
            Lara javaslata
            <span className="normal-case tracking-normal">
              · {new Date(ai.ido).toLocaleString("hu-HU", { dateStyle: "short", timeStyle: "short" })}
              {ai.lepesek.length > 0 ? ` · ${Math.round(ai.biztossag * 100)}% biztos` : ""}
            </span>
          </p>
          {ai.osszefoglalo ? (
            <p className="text-[13.5px] leading-snug text-text-primary">{ai.osszefoglalo}</p>
          ) : (
            <p className="text-[13px] text-text-secondary">
              {ai.allapot === "hiba"
                ? "A javaslat most nem készült el (a modell nem volt elérhető)."
                : "Nem talált a rendszerben elég adatot konkrét javaslathoz."}
            </p>
          )}
          <Lepesek lepesek={ai.lepesek} />
          {ai.figyelmeztetesek.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1">
              {ai.figyelmeztetesek.map((f, i) => (
                <li key={i} className="text-[12.5px] text-text-warning">
                  ! {f}
                </li>
              ))}
            </ul>
          )}
          {ai.vizsgalt.length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[12px] text-text-muted">
                Hol nézett utána ({ai.vizsgalt.length} lépés)
              </summary>
              <ul className="mt-1.5 flex flex-col gap-0.5">
                {ai.vizsgalt.map((l, i) => (
                  <li key={i} className={`font-mono text-[11.5px] ${l.ok ? "text-text-secondary" : "text-text-danger"}`}>
                    {l.cel}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {m?.alap && m.alap.length > 0 && (
        <div>
          <p className="mb-1 text-[12px] text-text-muted">
            {ai ? "Az általános lépések (a kérdés adataiból)" : "Mit kell tenni (a kérdés adataiból)"}
          </p>
          <Lepesek lepesek={m.alap} />
        </div>
      )}

      {!m && <p className="text-[13px] text-text-secondary">Ehhez a feladathoz még nincs megoldási javaslat.</p>}

      {canEdit && (
        <div>
          <button
            type="button"
            disabled={fut}
            onClick={kerj}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            {fut ? "Lara utánanéz és javaslatot ír… (akár egy perc)" : ai ? "Új javaslatot kérek" : "Javasolj megoldást"}
          </button>
          <p className="mt-1.5 text-[11.5px] text-text-muted">
            Lara az AI asszisztens csak-olvasó eszközeivel és a Geminivel utánanéz az érintett rekordoknak, és konkrét
            lépéseket javasol. Semmit nem módosít — a javítást te végzed.
          </p>
        </div>
      )}
    </div>
  );
}

function Lepesek({ lepesek }: { lepesek: LaraLepes[] }) {
  if (lepesek.length === 0) return null;
  return (
    <ol className="mt-2 flex list-decimal flex-col gap-1 pl-5">
      {lepesek.map((l, i) => (
        <li key={i} className="text-[13px] text-text-primary">
          {l.link ? (
            <Link href={l.link} className="hover:text-text-accent hover:underline">
              {l.leiras}
            </Link>
          ) : (
            l.leiras
          )}
        </li>
      ))}
    </ol>
  );
}
