"use client";

import { useState } from "react";
import { ActionButton } from "@/components/ActionButton";
import { StatusBadge } from "@/components/StatusBadge";

/** A projekt "Diszpó küldése" kártyájának két küldés-sora.

 * Kliens-komponens, mert a küldés SIKERE UTÁN AZONNAL át kell váltania (a
 * felhasználó kérése): a zöld "Kiküldve" jelzés megjelenik, a "Küldés" gomb
 * eltűnik, és már csak az "Újraküldés" marad - nem a szerver-frissítés
 * megérkezésére vár (ugyanez a minta, mint a Naptár/Diszpó oldalon, lásd
 * NaptarDiszpoContent helyiKuldve). A tartós állapot a szerverről jön
 * (Project.elozetes_diszpo_kuldes / diszpo, lásd backend services/dispo.py). */
export function DiszpoKuldesGombok({
  projectId,
  elozetesAllapot,
  diszpoAllapot,
}: {
  projectId: number;
  elozetesAllapot: string | null;
  diszpoAllapot: string | null;
}) {
  const [helyiKuldve, setHelyiKuldve] = useState<{ elozetes?: boolean; teljes?: boolean }>({});
  const elozetes = elozetesAllapot || (helyiKuldve.elozetes ? "Kiküldve" : null);
  const teljes = diszpoAllapot || (helyiKuldve.teljes ? "Kiküldve" : null);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <ActionButton
          path={`/api/v1/projects/${projectId}/diszpo/elozetes${elozetes ? "?ujrakuldes=1" : ""}`}
          label={elozetes ? "Előzetes diszpó újraküldése" : "Előzetes diszpó küldése"}
          figyelmeztetes={elozetes ? "AZ ELŐZETES DISZPÓ MÁR KI VAN KÜLDVE" : undefined}
          megerositoCimke={elozetes ? "Igen, újraküldöm" : undefined}
          confirmMessage={
            elozetes
              ? `Állapot: ${elozetes}. Ha most újraküldöd, a stáb MÉG EGYSZER megkapja ugyanazt a levelet. Biztosan újraküldöd?`
              : "Elküldi az előzetes diszpót a résztvevőknek. Folytatod?"
          }
          onSuccess={() => setHelyiKuldve((h) => ({ ...h, elozetes: true }))}
        />
        {elozetes && <StatusBadge label={elozetes} tone="success" />}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <ActionButton
          path={`/api/v1/projects/${projectId}/diszpo/kuldes${teljes ? "?ujrakuldes=1" : ""}`}
          label={teljes ? "Diszpó újraküldése" : "Diszpó küldése"}
          figyelmeztetes={teljes ? "A DISZPÓ MÁR KI VAN KÜLDVE" : undefined}
          megerositoCimke={teljes ? "Igen, újraküldöm" : undefined}
          confirmMessage={
            teljes
              ? `Állapot: ${teljes}. Ha most újraküldöd, a stáb MÉG EGYSZER megkapja a teljes diszpót (technika listával, PDF-fel). Biztosan újraküldöd?`
              : "Elküldi a teljes diszpót (technika listával, PDF-fel) a résztvevőknek. Folytatod?"
          }
          onSuccess={() => setHelyiKuldve((h) => ({ ...h, teljes: true }))}
        />
        {teljes && <StatusBadge label={teljes} tone="success" />}
      </div>
    </div>
  );
}
