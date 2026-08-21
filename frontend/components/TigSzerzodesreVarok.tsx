"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { IndoklasDialog } from "@/components/IndoklasDialog";
import type { PendingTigEmployee } from "@/lib/api";

/** Azok a felek, akikről még NEM készíthető TIG, mert nincs meg az eseti
 * szerződésük - de KIHAGYNI már most is lehet őket.
 *
 * A három papír-lépés (szerződés, TIG, számla) KIHAGYÁSA független egymástól.
 * TIG-et készíteni csak szerződés mögé van értelme - a papír éppen egy
 * szerződés teljesítését igazolja -, de kimondani, hogy innen nem lesz TIG, a
 * szerződéstől függetlenül szabad. Enélkül egy sosem elkészült szerződés
 * örökre nyitva tartotta a TIG-lépést is: a felületen meg sem jelentek ezek a
 * felek, tehát nem volt mit kihagyni rajtuk.
 *
 * Az indok itt is kötelező (lásd IndoklasDialog és a backend skip_tig). */
export function TigSzerzodesreVarok({
  projectId,
  felek,
  canEdit = true,
}: {
  projectId: number;
  felek: PendingTigEmployee[];
  canEdit?: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [kihagyando, setKihagyando] = useState<PendingTigEmployee | null>(null);

  if (felek.length === 0) return null;

  async function kihagy(fel: PendingTigEmployee, indok: string) {
    setKihagyando(null);
    setBusy(fel.szamlazo);
    try {
      const res = await authFetch(`/api/v1/teljesitesi-igazolasok/${projectId}/${fel.szamlazo}/skip`, {
        method: "POST",
        // `tetelek: null` = maradjon, ami a bejegyzésen van. Itt nincs
        // szerkesztett tétellista, amit küldhetnénk.
        body: JSON.stringify({ kihagyas_oka: indok, tetelek: null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen kihagyás: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen kihagyás (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-4 border-t border-border pt-3">
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
        Szerződésre vár ({felek.length})
      </p>
      <p className="mb-2 text-[12.5px] text-text-secondary">
        Róluk TIG csak a szerződésük után készíthető – kihagyni viszont már most is lehet, ha tudjuk, hogy innen nem
        lesz papír.
      </p>
      <ul className="space-y-1">
        {felek.map((fel) => (
          <li key={fel.szamlazo} className="flex items-center justify-between gap-3 text-[13px]">
            <span className="truncate text-text-primary">{fel.cimke}</span>
            {canEdit && (
              <button
                type="button"
                disabled={busy === fel.szamlazo}
                onClick={() => setKihagyando(fel)}
                className="whitespace-nowrap rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busy === fel.szamlazo ? "Kihagyás…" : "TIG kihagyása"}
              </button>
            )}
          </li>
        ))}
      </ul>

      {kihagyando && (
        <IndoklasDialog
          cim={`${kihagyando.full_name} kihagyása`}
          leiras="Erről a félről nem készül teljesítési igazolás ezen a projekten – a szerződése nélkül is lezárható a lépés. Írd le, miért marad el: fél év múlva ebből fog kiderülni, hogy szándékos volt."
          mezoCimke="A kihagyás oka"
          placeholder="Pl. a munkát végül nem ő végezte el"
          gombCimke="Kihagyás"
          onMegse={() => setKihagyando(null)}
          onKesz={(indok) => kihagy(kihagyando, indok)}
        />
      )}
    </div>
  );
}
