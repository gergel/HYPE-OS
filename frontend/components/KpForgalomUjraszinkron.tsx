"use client";

import { useState } from "react";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

/** Egyszeri admin-eszköz: ha a KP forgalom napló (lásd services/kassza.py)
 * elszáll a Notion "KP forgalom" táblájától - pl. mert egy korábbi import
 * félbeszakadt, vagy kézi javítás húzta el a darabszámot -, ez a gomb
 * ürít-és-újratölt egy lépésben, ahelyett hogy a felhasználónak két külön
 * admin-végpontot kellene ismernie/hívnia.
 *
 * A törlés MAGÁT a kp_forgalmak táblát üríti (a hozzá kötött Kiadás-sorokat
 * nem érinti - lásd backend finance.torol_minden_kp_forgalmat), utána pedig
 * elindítja a KpForgalom-importert (lásd NotionImportPanel/admin_import.py) -
 * a NotionImportMap idempotens leképezése miatt ez pontosan annyi sort hoz
 * vissza, amennyi a Notionben ténylegesen van, duplázás vagy kimaradás
 * nélkül. */
export function KpForgalomUjraszinkron() {
  const confirm = useConfirm();
  const [futAlatt, setFutAlatt] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  async function ujraszinkron() {
    if (
      !(await confirm(
        "Törlöd a teljes KP forgalom naplót, és újra áthozod a Notionből? A helyi (kp_forgalmak) sorok véglegesen törlődnek, majd a Notion 'KP forgalom' táblája alapján épülnek újra - ez percekig is tarthat.",
      ))
    ) {
      return;
    }
    setFutAlatt(true);
    setHiba(null);
    setUzenet("Törlés folyamatban…");
    try {
      const torles = await authFetch("/api/v1/finance/kp-forgalom/mind", { method: "DELETE" });
      if (!torles.ok) {
        const detail = await torles.json().catch(() => null);
        setHiba(detail?.detail ?? `Törlés sikertelen: HTTP ${torles.status}`);
        return;
      }
      setUzenet("Törölve - Notion import indítása…");
      const importStart = await authFetch("/api/v1/admin/notion-import", {
        method: "POST",
        body: JSON.stringify({ importerek: ["KpForgalom"] }),
      });
      if (!importStart.ok) {
        const detail = await importStart.json().catch(() => null);
        setHiba(detail?.detail ?? `Az újraimport indítása sikertelen: HTTP ${importStart.status}`);
        return;
      }
      setUzenet(
        "A törlés megtörtént, az újraimport elindult a háttérben - a haladása a fenti Notion import naplóban követhető (frissítsd az oldalt, ha nem indul automatikusan a lekérdezés).",
      );
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setFutAlatt(false);
    }
  }

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="mb-2 text-[12px] text-text-muted">
        Ha a KP forgalom napló darabszáma nem stimmel a Notion „KP forgalom” táblájával (pl. egy korábbi import
        félbeszakadt), ez a gomb egy lépésben üríti a helyi táblát, és újraépíti a Notionből - a hozzá kötött Kiadás-
        sorokat nem érinti.
      </p>
      <button
        type="button"
        onClick={ujraszinkron}
        disabled={futAlatt}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        {futAlatt ? "Fut…" : "KP forgalom törlése és újraimportálása"}
      </button>
      {uzenet && !hiba && <p className="mt-2 text-[12px] text-text-muted">{uzenet}</p>}
      {hiba && <p className="mt-2 text-[12px] text-text-danger">{hiba}</p>}
    </div>
  );
}
