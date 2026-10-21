"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { IndoklasDialog } from "@/components/IndoklasDialog";
import { useToast } from "@/components/ToastProvider";
import { authFetch } from "@/lib/authFetch";

/** A projektkód PAPÍROZÁSI kapcsolói.
 *
 * Két külön kérdés, szándékosan két kapcsolóban - egy közös jelölő elfedné a
 * különbséget:
 *
 * - **Van-e szerződés a projekt mögött?** Ha van, kell hozzá megrendelői eseti
 *   szerződés ÉS teljesítési igazolás is.
 * - **Papír nélkül számoljuk el?** Ilyenkor VAN ügylet, csak nem pénzmozgással
 *   rendeződik (pl. a cégvezető be van jelentve a megrendelőhöz vállalkozóként,
 *   és annyival kevesebb fizetést vesz fel onnan) - a bevétel nem bejövő pénz,
 *   hanem el nem költött pénz. Ehhez INDOK kell: enélkül fél év múlva csak
 *   annyi látszana, hogy erről a munkáról nincs papír.
 *
 * Az indokot a backend is megköveteli (lásd routes/project_codes.py
 * _papir_kapcsolok_ellenorzese); ez az ablak csak azt biztosítja, hogy a
 * felhasználó ne egy hibaüzenetből tudja meg. */
export function PapirKapcsolok({
  patchPath,
  vanSzerzodes,
  papirNelkul,
  papirNelkulIndoka,
  canEdit,
}: {
  /** A projektkód PATCH útvonala. Azért prop, és nem itt épül az
   * ENTITY_PATHS-ból: az a lib/api-ban van, amit kliens-komponensből behúzva a
   * `next/headers` is a böngésző-csomagba kerülne, és eltörne a build. */
  patchPath: string;
  vanSzerzodes: boolean;
  papirNelkul: boolean;
  papirNelkulIndoka: string | null;
  canEdit: boolean;
}) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [indokNyitva, setIndokNyitva] = useState(false);

  async function ment(adat: Record<string, unknown>) {
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify(adat) });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen mentés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      toast(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  /** Bekapcsoláskor kérünk indokot (ha még nincs), kikapcsoláskor nem: a
   * meglévő indokot MEGTARTJUK, hogy egy véletlen ki-be kapcsolás ne törölje. */
  function papirNelkulBillentes(uj: boolean) {
    if (uj && !(papirNelkulIndoka ?? "").trim()) {
      setIndokNyitva(true);
      return;
    }
    ment({ papir_nelkul: uj });
  }

  return (
    <div className="space-y-3 text-[13px]">
      <label className="flex items-start gap-2 text-text-primary">
        <input
          type="checkbox"
          checked={vanSzerzodes}
          disabled={!canEdit || busy}
          onChange={(e) => ment({ van_szerzodes: e.target.checked })}
          className="mt-0.5"
        />
        <span>
          Van szerződés a projekt mögött
          <span className="block text-[12px] text-text-muted">
            Ha be van kapcsolva, megrendelői szerződés ÉS teljesítési igazolás is jár hozzá.
          </span>
        </span>
      </label>

      <label className="flex items-start gap-2 text-text-primary">
        <input
          type="checkbox"
          checked={papirNelkul}
          disabled={!canEdit || busy}
          onChange={(e) => papirNelkulBillentes(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          Papír nélkül elszámolt
          <span className="block text-[12px] text-text-muted">
            A teljesítés ellenértéke nem pénzmozgással rendeződik – a bevétel nem bejövő pénz, hanem el nem költött
            pénz. Ilyenkor nincs mit papírozni.
          </span>
        </span>
      </label>

      {papirNelkul && (
        <div className="rounded-[var(--radius)] border border-border p-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">A papírmentesség oka</p>
          <p className="mt-1 text-text-secondary">{papirNelkulIndoka || "Nincs megadva."}</p>
          {canEdit && (
            <button
              type="button"
              onClick={() => setIndokNyitva(true)}
              disabled={busy}
              className="mt-2 text-text-secondary hover:underline disabled:opacity-50"
            >
              Indok módosítása
            </button>
          )}
        </div>
      )}

      {indokNyitva && (
        <IndoklasDialog
          cim="Papír nélküli elszámolás"
          leiras="Ez a projektkód szerződés és teljesítési igazolás nélkül zárul. Írd le, hogyan rendeződik az ellenértéke – fél év múlva ez az egyetlen dolog, amiből kiderül, mi történt."
          mezoCimke="A papírmentesség oka"
          placeholder="Pl. a cégvezető be van jelentve a megrendelőhöz vállalkozóként, és annyival kevesebb fizetést vesz fel onnan"
          gombCimke="Mentés"
          onMegse={() => setIndokNyitva(false)}
          onKesz={(indok) => {
            setIndokNyitva(false);
            ment({ papir_nelkul: true, papir_nelkul_indoka: indok });
          }}
        />
      )}
    </div>
  );
}
