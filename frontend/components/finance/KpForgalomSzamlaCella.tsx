"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Paperclip } from "lucide-react";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { ModalReteg } from "@/components/ModalReteg";
import { SelectDropdown } from "@/components/SelectDropdown";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import type { DocumentAttachment } from "@/lib/api";

const OPCIOK = ["van", "nincs"];
const CIMKEK: Record<string, string> = { van: "Van", nincs: "Nincs" };

/** A KP forgalom napló "Számla" cellája egy Notionből örökölt KP forgalom
 * sorhoz - kézzel állítható legördülő (van / nincs számla), és csak akkor
 * jelenik meg a bizonylat-feltöltés lehetősége, ha "van"-ra van állítva
 * (lásd backend models/finance.KpForgalom.van_szamla). */
export function KpForgalomSzamlaCella({
  forrasId,
  vanSzamla,
  csatolmanyok,
  canEdit,
  canDelete,
}: {
  forrasId: number;
  vanSzamla: boolean;
  csatolmanyok: DocumentAttachment[];
  canEdit: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const [ertek, setErtek] = useState(vanSzamla);
  const [nyitva, setNyitva] = useState(false);

  async function onChange(next: string | null) {
    const ujErtek = next === "van";
    const elozo = ertek;
    setErtek(ujErtek);
    try {
      const res = await authFetch(`/api/v1/kp-forgalom/${forrasId}`, {
        method: "PATCH",
        body: JSON.stringify({ van_szamla: ujErtek }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setErtek(elozo);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      setErtek(elozo);
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    }
  }

  if (!canEdit) {
    return <StatusBadge label={ertek ? "Van" : "Nincs"} tone={ertek ? "success" : "warning"} />;
  }

  return (
    <span className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
      <SelectDropdown value={ertek ? "van" : "nincs"} options={OPCIOK} onChange={onChange} labels={CIMKEK} />
      {ertek && (
        <button
          type="button"
          onClick={() => setNyitva(true)}
          title="Bizonylat kezelése"
          className="flex items-center gap-0.5 text-text-muted hover:text-text-accent"
        >
          <Paperclip size={13} />
          {csatolmanyok.length > 0 && <span className="text-[11px]">{csatolmanyok.length}</span>}
        </button>
      )}
      {nyitva && (
        <ModalReteg onClose={() => setNyitva(false)}>
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-3 text-[14px] font-medium text-text-primary">Bizonylat</h3>
            <DokumentumFeltoltes
              entityType="kpForgalom"
              entityId={forrasId}
              attachments={csatolmanyok}
              kategoria="szamla"
              canEdit={canEdit}
              canDelete={canDelete}
              emptyText="Nincs feltöltött számla."
            />
          </div>
        </ModalReteg>
      )}
    </span>
  );
}
