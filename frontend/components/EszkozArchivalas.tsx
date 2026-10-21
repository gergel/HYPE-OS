"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";

type JovobeliFoglalas = { project_id: number; nev: string; datum: string | null };

/** Egy eszköz ARCHIVÁLÁSA / VISSZAÁLLÍTÁSA az adatlapon (a felhasználó kérése,
 * 2026-10). Az archivált eszköz eltűnik a Felszerelés listáról, nem foglalható
 * forgatásra és nem írható ki - a múltbeli forgatásainál megmarad. Archiváláskor
 * kiírjuk, melyik még előttünk álló forgatásra van foglalva: azokról le kell
 * venni (a „Technika ready” ellenőrzés is jelzi). */
export function EszkozArchivalas({
  equipmentId,
  archivalvaAt,
  archivalasOka,
  canEdit,
}: {
  equipmentId: number;
  archivalvaAt: string | null;
  archivalasOka: string | null;
  canEdit: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitott, setNyitott] = useState(false);
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [jovobeli, setJovobeli] = useState<JovobeliFoglalas[]>([]);

  async function archival() {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/equipment/${equipmentId}/archivalas`, {
        method: "POST",
        body: JSON.stringify({ ok: ok.trim() || null }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : `Az archiválás nem sikerült (${res.status}).`);
        return;
      }
      setJovobeli(d.jovobeli_foglalasok ?? []);
      setNyitott(false);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function visszaallit() {
    if (!(await confirm("Visszaállítod az eszközt? Újra látszik a listán, foglalható és kiírható lesz."))) return;
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/equipment/${equipmentId}/visszaallitas`, { method: "POST" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setHiba(typeof d.detail === "string" ? d.detail : `A visszaállítás nem sikerült (${res.status}).`);
        return;
      }
      setJovobeli([]);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  if (archivalvaAt) {
    const mikor = new Date(archivalvaAt).toLocaleDateString("hu-HU", { timeZone: "Europe/Budapest" });
    return (
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3 rounded-[var(--radius-lg)] border border-border bg-bg-warning px-4 py-3 text-[13px] text-text-warning">
          <span className="font-medium">Archivált eszköz ({mikor})</span>
          {archivalasOka && <span className="text-text-secondary">· {archivalasOka}</span>}
          <span className="text-text-secondary">
            Nem foglalható forgatásra és nem írható ki - a múltbeli forgatásainál megmarad.
          </span>
          {canEdit && (
            <button
              type="button"
              disabled={busy}
              onClick={visszaallit}
              className="ml-auto rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-1.5 text-text-primary hover:bg-surface-3 disabled:opacity-50"
            >
              Visszaállítás
            </button>
          )}
        </div>
        {jovobeli.length > 0 && (
          <div className="rounded-[var(--radius-lg)] border border-border bg-bg-danger px-4 py-3 text-[13px] text-text-danger">
            <p className="font-medium">Ez az eszköz még ki van írva ezekre a jövőbeli forgatásokra - vedd le róluk:</p>
            <ul className="mt-1 list-disc pl-5">
              {jovobeli.map((f) => (
                <li key={f.project_id}>
                  <a href={`/projektek/${f.project_id}`} className="underline">
                    {f.nev}
                  </a>
                  {f.datum ? ` (${f.datum})` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
        {hiba && <p className="text-[13px] text-text-danger">{hiba}</p>}
      </div>
    );
  }

  if (!canEdit) return null;
  return (
    <div className="space-y-2">
      {!nyitott ? (
        <button
          type="button"
          onClick={() => setNyitott(true)}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
        >
          Archiválás
        </button>
      ) : (
        <div className="flex flex-col gap-2 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3 text-[13px]">
          <p className="text-text-primary">
            Archiválás után az eszköz eltűnik a Felszerelés listáról, nem foglalható forgatásra és nem írható ki. A múltbeli
            forgatásainál megmarad, és bármikor visszaállítható.
          </p>
          <input
            value={ok}
            onChange={(e) => setOk(e.target.value)}
            placeholder="Miért? (nem kötelező - pl. eladva, selejtezve, elveszett)"
            maxLength={300}
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-text-primary focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={archival}
              className="rounded-[var(--radius)] bg-bg-warning px-3 py-1.5 font-medium text-text-warning disabled:opacity-50"
            >
              {busy ? "Archiválás…" : "Archiválás"}
            </button>
            <button
              type="button"
              onClick={() => setNyitott(false)}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3"
            >
              Mégsem
            </button>
          </div>
        </div>
      )}
      {hiba && <p className="text-[13px] text-text-danger">{hiba}</p>}
    </div>
  );
}
