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
  redirectPrefix,
}: {
  path: string;
  label: string;
  confirmMessage?: string;
  redirectPrefix?: string;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  // A hibát felugró ablakban mutatjuk (nem magától eltűnő értesítés-sávban):
  // ezek blokkoló hibák, amik akár több soros listát is tartalmaznak (pl. kinek
  // hiányzik az email címe a diszpó küldése előtt), és el kell olvasni őket.
  const alertDialog = useAlertDialog();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (confirmMessage && !(await confirm(confirmMessage))) return;
    setBusy(true);
    try {
      const res = await authFetch(path, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        await alertDialog(String(detail?.detail ?? `Sikertelen művelet (HTTP ${res.status}).`));
        return;
      }
      const data = await res.json().catch(() => null);
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
    <button type="button" onClick={handleClick} disabled={busy} className="btn btn-primary">
      {busy ? "Folyamatban…" : label}
    </button>
  );
}
