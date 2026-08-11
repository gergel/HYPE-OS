"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { formatFt } from "@/lib/ido";
import type { KrumpelloMunkaora } from "@/lib/api";

/** Egy MUNKANAP kifizetve-jelölése, a napló sorában.
 *
 * Kattintásra azonnal vált (nincs megerősítő ablak): a jelölés visszavonható
 * ugyanazzal a kattintással, tehát a téves kattintás ára egy újabb kattintás -
 * ehhez képest egy megerősítő ablak minden jelölésnél útban lenne.
 *
 * A dátum a mai napra kerül; ha az utalás máskor történt, a sor szerkesztőjében
 * átírható. */
export function KifizetesKapcsolo({ munkaora }: { munkaora: KrumpelloMunkaora }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function valt() {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/krumpello/munkaorak/${munkaora.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          kifizetve: !munkaora.kifizetve,
          kifizetes_datuma: munkaora.kifizetve ? null : new Date().toISOString().slice(0, 10),
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={valt}
      disabled={busy}
      title={
        munkaora.kifizetve
          ? `Kifizetve${munkaora.kifizetes_datuma ? ` – ${munkaora.kifizetes_datuma}` : ""}. Kattints a visszavonáshoz.`
          : "Kattints, ha ezt a napot kifizettük."
      }
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius)] border px-2 py-1 text-[11.5px] transition-colors disabled:opacity-50 ${
        munkaora.kifizetve
          ? "border-[color:var(--text-success)]/40 bg-bg-success text-text-success"
          : "border-border text-text-muted hover:bg-surface-3 hover:text-text-primary"
      }`}
    >
      {munkaora.kifizetve ? <Check size={12} /> : null}
      {munkaora.kifizetve ? "Kifizetve" : "Még jár"}
    </button>
  );
}

/** Egy ember TELJES (szűrt) időszakának jelölése egyben.
 *
 * Ez a valódi munkafolyamat: a kifizetés időszakonként történik ("Horváth
 * Patrik, július 22. – augusztus 3."), nem naponként. Soronként kattintgatva
 * ugyanezt tizennyolcszor kellene, és pont a végén maradna ki egy nap.
 *
 * Csak akkor jelenik meg, ha van mit jelölni - egy "0 nap" gomb csak zaj. */
export function IdoszakKifizetes({
  dolgozoId,
  nev,
  hatralek,
  hatralekosNapok,
  tol,
  ig,
}: {
  dolgozoId: number;
  nev: string;
  hatralek: number;
  hatralekosNapok: number;
  tol?: string;
  ig?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  if (hatralekosNapok === 0) return null;

  async function jelol() {
    const idoszak = tol || ig ? `${tol ?? "…"} – ${ig ?? "…"}` : "a teljes eddigi időszak";
    if (
      !confirm(
        `${nev}: ${hatralekosNapok} nap, ${formatFt(hatralek)} jelölése kifizetettként (${idoszak}).\n\n` +
          "Csak a még jelöletlen napokat érinti.",
      )
    )
      return;
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/krumpello/munkaorak/kifizetes", {
        method: "POST",
        body: JSON.stringify({ dolgozo_id: dolgozoId, tol: tol || null, ig: ig || null, kifizetve: true }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={jelol}
      disabled={busy}
      className="whitespace-nowrap rounded-[var(--radius)] border border-border px-2 py-1 text-[11.5px] text-text-secondary transition-colors hover:bg-surface-3 hover:text-text-primary disabled:opacity-50"
    >
      {busy ? "Jelölés…" : `Kifizetve (${hatralekosNapok} nap)`}
    </button>
  );
}
