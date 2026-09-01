"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useAlertDialog, useConfirm } from "@/components/ConfirmProvider";

/** Egy Notion button-automatizmust portoló, egy kattintásos backend akció (pl.
 * Feldarabolás, Utómunka létrehozása) - POST a megadott útvonalra, majd vagy
 * frissíti az oldalt, vagy (ha redirectPrefix meg van adva és a válasz tartalmaz
 * egy 'id' mezőt) átirányít az új rekord részletnézetére.
 *
 * A redirectPrefix szándékosan string, nem függvény: szerver komponensből
 * nem lehet függvényt propként átadni egy "use client" komponensnek. */
export function ActionButton({
  path,
  label,
  confirmMessage,
  figyelmeztetes,
  megerositoCimke,
  redirectPrefix,
  onSuccess,
  halkabb,
}: {
  path: string;
  label: string;
  confirmMessage?: string;
  /** Nagy, PIROS felirat a megerősítő kérdés fölött (pl. "MÁR KI VAN KÜLDVE").
   * Ha meg van adva, a kérdés akkor is felugrik, ha confirmMessage nincs. */
  figyelmeztetes?: string;
  /** A megerősítő gomb felirata ("Rendben" helyett). */
  megerositoCimke?: string;
  redirectPrefix?: string;
  /** Sikeres művelet után hívódik (a router.refresh() MELLETT) - kliens
   * komponensből átadva azonnali, helyi visszajelzésre (pl. a diszpó-küldés
   * gombja rögtön "Kiküldve"-t mutasson, ne a szerver-frissítésre várjon). */
  onSuccess?: () => void;
  /** Visszafogott (ghost) megjelenés a fő gomb MELLÉ szánt másodlagos
   * művelethez (pl. "Kiküldöttnek jelölés küldés nélkül"). */
  halkabb?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  // A hibát felugró ablakban mutatjuk (nem magától eltűnő értesítés-sávban):
  // ezek blokkoló hibák, amik akár több soros listát is tartalmaznak (pl. kinek
  // hiányzik az email címe a diszpó küldése előtt), és el kell olvasni őket.
  const alertDialog = useAlertDialog();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (
      (confirmMessage || figyelmeztetes) &&
      !(await confirm(confirmMessage ?? "", { figyelmeztetes, megerositoCimke }))
    )
      return;
    setBusy(true);
    try {
      const res = await authFetch(path, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        await alertDialog(String(detail?.detail ?? `Sikertelen művelet (HTTP ${res.status}).`));
        return;
      }
      const data = await res.json().catch(() => null);
      onSuccess?.();
      if (redirectPrefix && data && typeof data.id !== "undefined") {
        router.push(`${redirectPrefix}${data.id}`);
      } else {
        router.refresh();
      }
    } catch (err) {
      await alertDialog(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className={halkabb ? "btn btn-ghost !text-[12.5px]" : "btn btn-primary"}
    >
      {busy ? "Folyamatban…" : label}
    </button>
  );
}
