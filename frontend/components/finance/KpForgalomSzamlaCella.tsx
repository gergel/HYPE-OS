"use client";

import { useState } from "react";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { ModalReteg } from "@/components/ModalReteg";
import { StatusBadge } from "@/components/StatusBadge";
import type { DocumentAttachment } from "@/lib/api";

/** A KP forgalom napló "Számla" cellája egy Notionből örökölt KP forgalom
 * sorhoz - ellentétben a Kiadással/Bevétellel, ezeknek eddig NEM volt saját
 * bizonylat-feltöltési felülete (lásd backend services/kassza.py
 * "Ezekhez nincs bizonylat" megjegyzése, ami már nem igaz). A kompakt badge
 * kattintásra nyit egy kis ablakot a tényleges feltöltéshez/törléshez - a
 * sűrű táblázatban nem fér el helyben egy teljes feltöltő-felület. */
export function KpForgalomSzamlaCella({
  forrasId,
  vanSzamla,
  bevetel,
  fedezetJelolt,
  csatolmanyok,
  canEdit,
  canDelete,
}: {
  forrasId: number;
  vanSzamla: boolean;
  /** s.be > 0 - ez dönti el (van_szamla hiányában), Fedezet vagy Nincs a
   * felirat, ugyanúgy, mint a Kiadás/Bevétel forrású soroknál. */
  bevetel: boolean;
  /** A sor kifejezetten "fedezet"-nek van jelölve - ilyenkor a
   * bizonylat-feltöltés szándékosan ki van kapcsolva, mert épp az a jelölés
   * lényege, hogy ez számla nélküli bevétel (lásd backend van_szamla). */
  fedezetJelolt: boolean;
  csatolmanyok: DocumentAttachment[];
  canEdit: boolean;
  canDelete: boolean;
}) {
  const [nyitva, setNyitva] = useState(false);

  const jelzo = vanSzamla
    ? { label: "Van", tone: "success" as const }
    : bevetel
      ? { label: "Fedezet", tone: "blue" as const }
      : { label: "Nincs", tone: "warning" as const };

  if (fedezetJelolt || !(canEdit || canDelete)) {
    return <StatusBadge label={jelzo.label} tone={jelzo.tone} />;
  }

  return (
    <>
      <button type="button" onClick={() => setNyitva(true)} className="cursor-pointer">
        <StatusBadge label={jelzo.label} tone={jelzo.tone} />
      </button>
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
    </>
  );
}
