"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AdminAgentSettings } from "@/lib/api";

/** HYRON — BEÁLLÍTÁSOK (kliens).
 *
 * A biztonságos alapállás kapcsolói. A modul és a mellékhatások KÜLÖN
 * engedélyezendők (a modul bekapcsolása önmagában még nem enged külső hatást),
 * és a vészleállítás azonnal letiltja HYRON minden mellékhatásos lépését.
 * A tényleges kikényszerítés a szerver-oldali policy engine dolga — ez a
 * felület csak beállítja a kapcsolókat. */
export function AdminBeallitasok({
  kezdo,
  canManage,
}: {
  kezdo: AdminAgentSettings;
  canManage: boolean;
}) {
  const router = useRouter();
  const [b, setB] = useState<AdminAgentSettings>(kezdo);
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);
  const [leallitasIndok, setLeallitasIndok] = useState("");
  const [kezdet, setKezdet] = useState(kezdo.tanulas_kezdete ?? "2026-09-01");
  const [kezdetUzenet, setKezdetUzenet] = useState<string | null>(null);

  const megfigyelesBe = Boolean((b.engedett_forrasok as Record<string, unknown> | null)?.megfigyeles);

  async function mentSettings(valtozas: {
    module_enabled?: boolean;
    side_effects_enabled?: boolean;
    engedett_forrasok?: Record<string, unknown>;
    tanulas_kezdete?: string;
  }) {
    if (!canManage) return;
    setHiba(null);
    setKezdetUzenet(null);
    setFolyamatban(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/settings", {
        method: "PATCH",
        body: JSON.stringify(valtozas),
      });
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A módosítás nem sikerült."));
        return;
      }
      const uj = (await res.json()) as AdminAgentSettings & {
        korszak?: { felreteve: number; visszahozva: number; regi_jovahagyott: number } | null;
      };
      setB(uj);
      if (uj.korszak) {
        setKezdetUzenet(
          `Mentve. ${uj.korszak.felreteve} régi jelölt félretéve, ${uj.korszak.visszahozva} visszahozva; ${uj.korszak.regi_jovahagyott} jóváhagyott régi példát HYRON kisebb súllyal használ.`,
        );
      }
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  async function veszleallitas(be: boolean) {
    if (!canManage) return;
    setHiba(null);
    setFolyamatban(true);
    try {
      const res = be
        ? await authFetch("/api/v1/admin-agent/pause", {
            method: "POST",
            body: JSON.stringify({ indok: leallitasIndok.trim() || null }),
          })
        : await authFetch("/api/v1/admin-agent/resume", { method: "POST" });
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A művelet nem sikerült."));
        return;
      }
      const eredmeny = (await res.json()) as { kill_switch: boolean; indok?: string | null };
      setB((elozo) => ({
        ...elozo,
        kill_switch: eredmeny.kill_switch,
        kill_switch_indok: eredmeny.indok ?? null,
      }));
      if (!be) setLeallitasIndok("");
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {hiba && (
        <div className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>
      )}
      {!canManage && (
        <div className="rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[13px] text-text-secondary">
          Csak megtekintés — a kapcsolók módosításához külön jogosultság szükséges.
        </div>
      )}

      <Kapcsolo
        cim="Tanulás és megfigyelés (L0)"
        leiras="Bekapcsolva HYRON félóránként megnézi a projektkódokon és az utókövetésben történt szerződés-, TIG- és számla/kiadás-lépéseket, és éjszakánként tanul a javításokból. Csak olvas és jelölteket készít — üzleti rekordot nem módosít, ezért a modul kikapcsolt állapotában is biztonságos."
        aktiv={megfigyelesBe}
        tiltva={!canManage || folyamatban}
        onValt={(v) =>
          mentSettings({
            engedett_forrasok: { ...((b.engedett_forrasok as Record<string, unknown>) ?? {}), megfigyeles: v },
          })
        }
      />

      <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-4 py-3.5">
        <p className="text-[13px] font-medium text-text-primary">Tanulás kezdete</p>
        <p className="mt-0.5 text-[12px] text-text-muted">
          HYRON csak az ettől a naptól a HYPE OS-ben keletkezett munkából készít példa-jelöltet (a Notion-korszak
          és a Notionből hozott rekordok kimaradnak). A régebbi, már jóváhagyott példákat csak az újak után, kisebb
          súllyal használja; a régi, el nem bírált jelöltek félre lesznek téve (nem törlődnek).
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={kezdet}
            max={new Date().toISOString().slice(0, 10)}
            disabled={!canManage || folyamatban}
            onChange={(e) => setKezdet(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary disabled:opacity-50"
          />
          <button
            type="button"
            disabled={!canManage || folyamatban || !kezdet || kezdet === b.tanulas_kezdete}
            onClick={() => mentSettings({ tanulas_kezdete: kezdet })}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            Mentés
          </button>
        </div>
        {kezdetUzenet && <p className="mt-2 text-[12px] text-text-success">{kezdetUzenet}</p>}
      </div>

      <Kapcsolo
        cim="Modul engedélyezése"
        leiras="Bekapcsolva HYRON elemez és javaslatokat készít. A mellékhatások (rekordírás, e-mail) ettől még külön engedély nélkül tiltottak maradnak."
        aktiv={b.module_enabled}
        tiltva={!canManage || folyamatban || b.kill_switch}
        onValt={(v) => mentSettings({ module_enabled: v })}
      />

      <Kapcsolo
        cim="Mellékhatások engedélyezése"
        leiras="A jóváhagyott műveletek tényleges végrehajtása (üzleti rekord írása, e-mail). Csak akkor van értelme, ha a modul is be van kapcsolva. Az R3 kockázatú lépések ekkor is tiltottak."
        aktiv={b.side_effects_enabled}
        tiltva={!canManage || folyamatban || b.kill_switch}
        onValt={(v) => mentSettings({ side_effects_enabled: v })}
      />

      <div
        className={`rounded-[var(--radius)] border px-4 py-3.5 ${
          b.kill_switch ? "border-transparent bg-bg-danger" : "border-border bg-surface-3"
        }`}
      >
        <p className={`text-[13px] font-medium ${b.kill_switch ? "text-text-danger" : "text-text-primary"}`}>
          Vészleállítás
        </p>
        <p className={`mt-0.5 text-[12px] ${b.kill_switch ? "text-text-danger/80" : "text-text-muted"}`}>
          Azonnal letiltja HYRON minden mellékhatásos lépését. A már elindult, nem megszakítható külső műveleteket
          nem vonja vissza.
        </p>
        {b.kill_switch ? (
          <div className="mt-3">
            {b.kill_switch_indok && (
              <p className="mb-2 text-[12px] text-text-danger/80">Indok: {b.kill_switch_indok}</p>
            )}
            <button
              type="button"
              disabled={!canManage || folyamatban}
              onClick={() => veszleallitas(false)}
              className="rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-4 disabled:opacity-50"
            >
              Feloldás
            </button>
          </div>
        ) : (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <input
              value={leallitasIndok}
              onChange={(e) => setLeallitasIndok(e.target.value)}
              placeholder="Indok (opcionális)"
              disabled={!canManage || folyamatban}
              className="min-w-[180px] flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted disabled:opacity-50"
            />
            <button
              type="button"
              disabled={!canManage || folyamatban}
              onClick={() => veszleallitas(true)}
              className="rounded-[var(--radius)] bg-bg-danger px-3 py-1.5 text-[13px] font-medium text-text-danger disabled:opacity-50"
            >
              Vészleállítás
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Kapcsolo({
  cim,
  leiras,
  aktiv,
  tiltva,
  onValt,
}: {
  cim: string;
  leiras: string;
  aktiv: boolean;
  tiltva: boolean;
  onValt: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-[var(--radius)] border border-border bg-surface-3 px-4 py-3.5">
      <div>
        <p className="text-[13px] font-medium text-text-primary">{cim}</p>
        <p className="mt-0.5 text-[12px] text-text-muted">{leiras}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={aktiv}
        disabled={tiltva}
        onClick={() => onValt(!aktiv)}
        className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
          aktiv ? "bg-bg-success" : "bg-surface-4"
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-text-primary transition-transform ${
            aktiv ? "left-0.5 translate-x-5" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}

async function hibaSzoveg(res: Response, alap: string): Promise<string> {
  try {
    const adat = (await res.json()) as { detail?: unknown };
    if (typeof adat.detail === "string") return adat.detail;
  } catch {
    // nem JSON
  }
  return alap;
}
