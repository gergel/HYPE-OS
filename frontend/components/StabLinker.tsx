"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { M2mLinker } from "@/components/M2mLinker";
import { MegbeszeltDijDialog } from "@/components/MegbeszeltDijDialog";
import { huDatum } from "@/lib/huDate";

type Opcio = { id: number; label: string; href?: string; sublabel?: string | null; group?: string | null };

/** A projekt stáblistája - annyival több a sima M2mLinkernél, hogy egy NEM
 * BELSŐS stábtag felvétele után rögtön megkérdezi, mennyiért vállalja az adott
 * napot.
 *
 * Miért itt? Mert a diszpó írásakor dől el: aki beosztja az embert, az beszéli
 * meg vele a díjat. A szerződést és a TIG-et hetekkel később, más ember
 * adminisztrálja - ha a díj nincs rögzítve, ő vagy visszakeresi valahonnan,
 * vagy tippel. Ami itt megvan, abból nyílik meg mindkét papír piszkozata
 * (lásd backend services/megbeszelt_dij.py).
 *
 * A belsősöknél nincs mit kérdezni: ők havi bérezésűek, nincs projektenkénti
 * napidíjuk (a backend el is utasítja). */
export function StabLinker({
  patchPath,
  projectId,
  currentIds,
  options,
  napSzoveg,
  canEdit = true,
}: {
  patchPath: string;
  projectId: number;
  currentIds: number[];
  /** A `group` a munkatárs típusa ("belsos" / "kulsos" …) - ebből tudjuk, kinél
   * van egyáltalán értelme a kérdésnek. */
  options: Opcio[];
  /** A forgatás napja (ISO) - a felugró ablakban segít, melyik napról van szó. */
  napSzoveg?: string | null;
  canEdit?: boolean;
}) {
  const router = useRouter();
  const [kerdezett, setKerdezett] = useState<Opcio | null>(null);

  async function mentsDij(employeeId: number, dij: number | null, megjegyzes: string) {
    setKerdezett(null);
    try {
      const res = await authFetch(`/api/v1/projekt-szamlazok/${projectId}/${employeeId}/dij`, {
        method: "PUT",
        body: JSON.stringify({ megbeszelt_dij: dij, dij_megjegyzes: megjegyzes || null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`A díj mentése nem sikerült: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`A díj mentése nem sikerült (hálózati hiba): ${err}`);
    }
  }

  return (
    <>
      <M2mLinker
        patchPath={patchPath}
        fieldName="crew_employee_ids"
        currentIds={currentIds}
        options={options}
        emptyText="Nincs stábtag hozzárendelve ehhez a projekthez."
        addLabel="Stábtag hozzáadása"
        onAdded={(id) => {
          if (!canEdit) return;
          const opcio = options.find((o) => o.id === id);
          // Belsősnél nincs projektenkénti díj - nála a kérdés fel sem jön.
          if (!opcio || opcio.group === "belsos") return;
          setKerdezett(opcio);
        }}
      />
      {/* Feltételes renderelés, hogy minden megnyitás friss példány legyen. */}
      {kerdezett && (
        <MegbeszeltDijDialog
          nev={kerdezett.label}
          napSzoveg={napSzoveg ? huDatum(napSzoveg) : null}
          onMegse={() => setKerdezett(null)}
          onKesz={(dij, megjegyzes) => mentsDij(kerdezett.id, dij, megjegyzes)}
        />
      )}
    </>
  );
}
