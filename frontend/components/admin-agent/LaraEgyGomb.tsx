"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

type TechnikaTetel = {
  equipment_id: number;
  nev: string;
  qty: number;
  indoklas: string | null;
  szerep: string | null;
  helyettesiti: string | null;
};

type Generalas = {
  brief: string | null;
  forras: string | null;
  technika: TechnikaTetel[];
  meglevo_technika: number;
  figyelmeztetesek: string[];
  feladat_ertelmezes: string | null;
  hasonlo_forgatasok: number;
};

type BriefEredmeny = { szoveg: string; elozo: string; forras: string | null; hasonlo: number; visszavonva?: boolean };
type TechnikaEredmeny = {
  hozzaadva: { assignmentId: number; nev: string; qty: number }[];
  sikertelen: string[];
  figyelmeztetesek: string[];
  hasonlo: number;
  visszavonva?: boolean;
};

async function hibaSzoveg(res: Response): Promise<string> {
  const d = await res.json().catch(() => ({}));
  if (res.status === 423) return "Lara most le van állítva (vészleállítás).";
  if (res.status === 403) return "Ehhez Lara-jogosultság kell.";
  return typeof d?.detail === "string" ? d.detail : `Sikertelen (${res.status}).`;
}

/** EGY GOMBNYOMÁS (a felhasználó kérése): Lara a tanultak alapján megírja a
 * kész BRIEFET, ill. összeállítja a TECHNIKÁT ehhez a forgatáshoz.
 *
 * Lara maga csak megírja (a szerver ehhez csak olvas - lásd backend
 * admin_agent.diszpo_generalas); a beírást a gombot nyomó EMBER teszi meg a
 * saját szerkesztési jogával, ugyanúgy, mintha kézzel írná be: a brief a
 * mezőbe kerül (meglévő brief cseréje előtt rákérdezünk), a javasolt eszközök
 * a forgatásra, és lefut a technika-ellenőrzés (ez tölti a diszpó
 * technika-listáját). Mindkettő egy kattintással visszavonható. */
export function LaraEgyGomb({ projectId, brief }: { projectId: number; brief: string }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState<"brief" | "technika" | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [briefKesz, setBriefKesz] = useState<BriefEredmeny | null>(null);
  const [techKesz, setTechKesz] = useState<TechnikaEredmeny | null>(null);

  async function general(resz: "brief" | "technika"): Promise<Generalas | null> {
    const res = await authFetch(`/api/v1/admin-agent/diszpo/${projectId}/generalas`, {
      method: "POST",
      body: JSON.stringify({ resz }),
    });
    if (!res.ok) {
      setHiba(await hibaSzoveg(res));
      return null;
    }
    return (await res.json()) as Generalas;
  }

  async function briefMentes(szoveg: string): Promise<boolean> {
    const res = await authFetch(`/api/v1/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify({ brief: szoveg }),
    });
    if (!res.ok) {
      setHiba(`A brief nem íródott be: ${await hibaSzoveg(res)}`);
      return false;
    }
    return true;
  }

  async function briefMegirasa() {
    setBusy("brief");
    setHiba(null);
    setBriefKesz(null);
    try {
      const g = await general("brief");
      if (!g) return;
      const szoveg = (g.brief ?? "").trim();
      if (!szoveg) {
        setHiba("Lara most nem tudott briefet írni" + (g.figyelmeztetesek[0] ? `: ${g.figyelmeztetesek[0]}` : "."));
        return;
      }
      // Meglévő brief cseréje előtt rákérdezünk - az üreset rögtön kitöltjük.
      if (brief.trim()) {
        const ok = await confirm(`Lara briefje:\n\n${szoveg}`, {
          figyelmeztetes: "Lecseréli a meglévő briefet (visszavonható)",
          megerositoCimke: "Lecserélem",
        });
        if (!ok) return;
      }
      if (!(await briefMentes(szoveg))) return;
      setBriefKesz({ szoveg, elozo: brief, forras: g.forras, hasonlo: g.hasonlo_forgatasok });
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  async function briefVisszavonas() {
    if (!briefKesz) return;
    setBusy("brief");
    try {
      if (await briefMentes(briefKesz.elozo)) {
        setBriefKesz({ ...briefKesz, visszavonva: true });
        router.refresh();
      }
    } finally {
      setBusy(null);
    }
  }

  async function technikaCheck() {
    await authFetch(`/api/v1/projects/${projectId}/technika-check`, { method: "POST" }).catch(() => null);
  }

  async function technikaOsszeallitasa() {
    setBusy("technika");
    setHiba(null);
    setTechKesz(null);
    try {
      const g = await general("technika");
      if (!g) return;
      if (g.technika.length === 0) {
        setHiba(
          (g.meglevo_technika > 0 ? "Lara nem talált a meglévőkön felül hozzáadnivalót." : "Lara most nem tudott technikát összeállítani.") +
            (g.figyelmeztetesek[0] ? ` ${g.figyelmeztetesek[0]}` : ""),
        );
        return;
      }
      const hozzaadva: TechnikaEredmeny["hozzaadva"] = [];
      const sikertelen: string[] = [];
      for (const t of g.technika) {
        const res = await authFetch("/api/v1/assignments", {
          method: "POST",
          body: JSON.stringify({ equipment_id: t.equipment_id, project_id: projectId, qty: t.qty }),
        });
        if (res.ok) {
          const a = (await res.json()) as { id: number };
          hozzaadva.push({ assignmentId: a.id, nev: t.nev, qty: t.qty });
        } else {
          sikertelen.push(`${t.nev}: ${await hibaSzoveg(res)}`);
        }
      }
      // A technika-ellenőrzés tölti ki a diszpóba kerülő technika-listát.
      if (hozzaadva.length > 0) await technikaCheck();
      setTechKesz({ hozzaadva, sikertelen, figyelmeztetesek: g.figyelmeztetesek, hasonlo: g.hasonlo_forgatasok });
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  async function technikaVisszavonas() {
    if (!techKesz) return;
    setBusy("technika");
    try {
      for (const h of techKesz.hozzaadva) {
        await authFetch(`/api/v1/assignments/${h.assignmentId}`, { method: "DELETE" }).catch(() => null);
      }
      await technikaCheck();
      setTechKesz({ ...techKesz, visszavonva: true });
      router.refresh();
    } finally {
      setBusy(null);
    }
  }

  const gomb =
    "inline-flex items-center gap-1.5 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 font-medium text-text-accent disabled:opacity-50";
  return (
    <div className="flex flex-col gap-2 text-[13px]">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" disabled={busy !== null} onClick={briefMegirasa} className={gomb}>
          <Sparkles size={13} />
          {busy === "brief" ? "Lara írja…" : "Brief megírása"}
        </button>
        <button type="button" disabled={busy !== null} onClick={technikaOsszeallitasa} className={gomb}>
          <Sparkles size={13} />
          {busy === "technika" ? "Lara összeállítja…" : "Technika összeállítása"}
        </button>
        <span className="text-[12px] text-text-muted">Lara a korábbi hasonló forgatások alapján – visszavonható.</span>
      </div>
      {hiba && <p className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-text-danger">{hiba}</p>}
      {briefKesz && (
        <div className="rounded-[var(--radius)] border border-border p-3">
          <p className={briefKesz.visszavonva ? "text-text-muted" : "text-text-success"}>
            {briefKesz.visszavonva
              ? "Visszavonva - a korábbi brief van újra a mezőben."
              : `A brief beírva${briefKesz.hasonlo ? ` (${briefKesz.hasonlo} hasonló forgatás alapján)` : ""}.`}
            {!briefKesz.visszavonva && (
              <button
                type="button"
                disabled={busy !== null}
                onClick={briefVisszavonas}
                className="ml-2 text-text-muted underline hover:text-text-primary"
              >
                Visszavonás
              </button>
            )}
          </p>
          {!briefKesz.visszavonva && (
            <p className="mt-2 whitespace-pre-wrap text-text-secondary">{briefKesz.szoveg}</p>
          )}
        </div>
      )}
      {techKesz && (
        <div className="rounded-[var(--radius)] border border-border p-3">
          <p className={techKesz.visszavonva ? "text-text-muted" : "text-text-success"}>
            {techKesz.visszavonva
              ? "Visszavonva - Lara eszközei lekerültek a forgatásról."
              : `${techKesz.hozzaadva.length} eszköz hozzáadva${techKesz.hasonlo ? ` (${techKesz.hasonlo} hasonló forgatás alapján)` : ""}, a technika-lista frissítve.`}
            {!techKesz.visszavonva && techKesz.hozzaadva.length > 0 && (
              <button
                type="button"
                disabled={busy !== null}
                onClick={technikaVisszavonas}
                className="ml-2 text-text-muted underline hover:text-text-primary"
              >
                Visszavonás
              </button>
            )}
          </p>
          {!techKesz.visszavonva && techKesz.hozzaadva.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-text-secondary">
              {techKesz.hozzaadva.map((h) => (
                <li key={h.assignmentId}>
                  {h.nev}
                  {h.qty > 1 ? ` × ${h.qty}` : ""}
                </li>
              ))}
            </ul>
          )}
          {techKesz.sikertelen.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-text-danger">
              {techKesz.sikertelen.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
          {techKesz.figyelmeztetesek.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-[12px] text-text-muted">
              {techKesz.figyelmeztetesek.slice(0, 5).map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
