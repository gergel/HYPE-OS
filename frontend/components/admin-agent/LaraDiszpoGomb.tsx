"use client";

import { useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";

type Tetel = {
  equipment_id: number;
  nev: string;
  kategoria: string | null;
  qty: number;
  track_mode: string;
  forras: string;
  gyakorisag: string | null;
  helyettesiti?: { nev: string } | null;
};

type Tapasztalat = {
  hasonlo_forgatasok: { id: number; nev: string; datum: string; okok: string[] }[];
  technika: { tetelek: Tetel[]; figyelmeztetesek: string[]; tapasztalat_forgatasok: number };
  visszatero_instrukciok: string[];
};

function hibaSzoveg(status: number, d: { detail?: unknown }): string {
  if (status === 423) return "Lara most le van állítva (vészleállítás).";
  if (status === 403) return "Ehhez Lara-jogosultság kell.";
  return typeof d.detail === "string" ? d.detail : `Sikertelen (${status}).`;
}

/** A projekt Eszközök kártyáján: Lara a korábbi hasonló forgatások
 * tapasztalatából megírja a briefet és összeállítja a technikát. A javaslat
 * jóváhagyásra kerül; jóváhagyás után Lara az eszközöket ténylegesen hozzá is
 * rendeli a projekthez (ugyanazon az úton, mint a „hozzáadás”), és lefuttatja a
 * „Technika ready” ellenőrzést. A diszpót nem küldi ki. */
export function LaraDiszpoGomb({ projectId }: { projectId: number }) {
  const [brief, setBrief] = useState(true);
  const [technika, setTechnika] = useState(true);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [kesz, setKesz] = useState<{ taskId: number; szoveg: string } | null>(null);
  const [tap, setTap] = useState<Tapasztalat | null>(null);

  async function tervezet() {
    setBusy(true);
    setHiba(null);
    setKesz(null);
    try {
      const res = await authFetch(`/api/v1/admin-agent/diszpo/${projectId}/tervezet`, {
        method: "POST",
        body: JSON.stringify({ brief, technika }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(hibaSzoveg(res.status, d));
        return;
      }
      const szoveg =
        d.decision === "needs_approval"
          ? "Elkészült, jóváhagyásra vár."
          : d.decision === "blocked"
            ? "Elkészült árnyék-javaslatként (Lara bizalmi szintje / kapcsolói miatt most nem hajtható végre - a Beállításokban emelhető)."
            : "Elkészült.";
      setKesz({ taskId: d.task?.id, szoveg });
    } finally {
      setBusy(false);
    }
  }

  async function elonezet() {
    if (tap) {
      setTap(null);
      return;
    }
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/admin-agent/diszpo/${projectId}/tapasztalat`);
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(hibaSzoveg(res.status, d));
        return;
      }
      setTap(d as Tapasztalat);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 text-[13px]">
      <p className="text-text-secondary">
        <strong className="text-text-primary">Lara:</strong> brief és technikai lista a korábbi hasonló forgatások alapján
        (az eszközöket jóváhagyás után hozzá is rendeli).
      </p>
      <div className="flex flex-wrap items-center gap-3 text-text-secondary">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={brief} onChange={(e) => setBrief(e.target.checked)} /> brief
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={technika} onChange={(e) => setTechnika(e.target.checked)} /> technika
        </label>
        <button
          type="button"
          disabled={busy || (!brief && !technika)}
          onClick={tervezet}
          className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 font-medium text-text-accent disabled:opacity-50"
        >
          {busy ? "Dolgozom…" : "Kérem Larától"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={elonezet}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {tap ? "Előnézet elrejtése" : "Mit tanult Lara ehhez?"}
        </button>
      </div>
      {hiba && <p className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-text-danger">{hiba}</p>}
      {kesz && (
        <p className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-text-success">
          {kesz.szoveg}{" "}
          {kesz.taskId && (
            <Link href={`/admin-agent/munkasor/${kesz.taskId}`} className="underline">
              Megnyitás →
            </Link>
          )}
        </p>
      )}
      {tap && (
        <div className="flex flex-col gap-2 rounded-[var(--radius)] border border-border p-3">
          <div>
            <p className="font-medium text-text-primary">Hasonló korábbi forgatások ({tap.hasonlo_forgatasok.length})</p>
            {tap.hasonlo_forgatasok.length === 0 ? (
              <p className="text-text-muted">Nincs még hasonló forgatás a rendszerben.</p>
            ) : (
              <ul className="list-disc pl-5 text-text-secondary">
                {tap.hasonlo_forgatasok.slice(0, 6).map((h) => (
                  <li key={h.id}>
                    {h.nev} ({h.datum}) — {h.okok.join(", ")}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p className="font-medium text-text-primary">
              Szokásos technika ({tap.technika.tapasztalat_forgatasok} forgatás eszközei alapján)
            </p>
            {tap.technika.tetelek.length === 0 ? (
              <p className="text-text-muted">Nincs elég tapasztalat a technikai csomaghoz.</p>
            ) : (
              <ul className="list-disc pl-5 text-text-secondary">
                {tap.technika.tetelek.map((t) => (
                  <li key={t.equipment_id}>
                    {t.track_mode === "stock" ? `${t.qty} db ` : ""}
                    {t.nev}
                    {t.kategoria ? ` (${t.kategoria})` : ""}
                    {t.helyettesiti ? ` — ${t.helyettesiti.nev} helyett, mert az foglalt` : ""}
                    {t.gyakorisag ? ` · ${t.gyakorisag}` : ""}
                  </li>
                ))}
              </ul>
            )}
            {tap.technika.figyelmeztetesek.map((f, i) => (
              <p key={i} className="text-text-warning">
                {f}
              </p>
            ))}
          </div>
          {tap.visszatero_instrukciok.length > 0 && (
            <div>
              <p className="font-medium text-text-primary">Visszatérő brief-instrukciók</p>
              <ul className="list-disc pl-5 text-text-secondary">
                {tap.visszatero_instrukciok.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
