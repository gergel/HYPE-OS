"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** Admin egy kattintással visszavonja MINDENKI MÁS bejelentkezési hozzáférését
 * a sajátja kivételével - a munkatárs-rekordok megmaradnak (csak a jelszavuk
 * törlődik), admin bármikor újra beállíthatja őket egyénenként a keresőben. */
export function RevokeAllOthersButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (
      !confirm(
        "Biztosan törlöd MINDENKI MÁS hozzáférését (a sajátod kivételével)? " +
          "A munkatársak megmaradnak, csak a jelszavuk törlődik (nem tudnak többé bejelentkezni), " +
          "és az oldal-/mező-hozzáférésük alapértelmezettre áll vissza. Bármikor újra beállíthatod őket egyénenként.",
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/user-access/others", { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const data = await res.json().catch(() => null);
      alert(`Kész - ${data?.revoked_count ?? 0} munkatárs hozzáférése lett törölve.`);
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
      disabled={busy}
      onClick={handleClick}
      className="rounded-[var(--radius)] border border-text-danger/40 px-3 py-1.5 text-[13px] text-text-danger hover:bg-bg-danger disabled:opacity-50"
    >
      Minden más felhasználó hozzáférésének törlése
    </button>
  );
}
