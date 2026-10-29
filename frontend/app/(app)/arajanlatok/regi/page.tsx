import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { ArajanlatFulek } from "@/components/arajanlat/ArajanlatFulek";
import { AjanlatLista } from "@/components/arajanlat/AjanlatLista";
import { ArajanlatokContent } from "@/components/arajanlat/ArajanlatokContent";
import { getArajanlatTetelek, getArajanlatok, getMyPagePermissions } from "@/lib/api";
import { canDoPageAction, lathatjaAzOldalt } from "@/lib/permissions";

const PAGE = "/arajanlatok";

/** Régi ajánlatok: felül a Google Drive-ról importált, Excelben készült
 * árajánlatok (az ajánlat-szerkesztőben nyílnak, átírhatók, „Mentés újként”
 * új számmal menthetők), alatta a KORÁBBI (JSON-alapú) szerkesztő mentett
 * ajánlatai, sablonjai és alap tételei - változatlanul. */
export default async function RegiArajanlatokPage() {
  const [ajanlatok, tetelek, pagePermissions] = await Promise.all([
    getArajanlatok(),
    getArajanlatTetelek(),
    getMyPagePermissions(),
  ]);
  if (!lathatjaAzOldalt(pagePermissions, PAGE)) redirect("/nincs-jogosultsag");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <ArajanlatFulek />
        <p className="mb-4 text-[12.5px] text-text-muted">
          A Drive-on tárolt, Excelben készült árajánlatok. Megnyitva a megszokott ajánlat-kinézetben szerkeszthetők; az
          átírás az ajánlatba mentődik, a „Mentés újként” gomb pedig új számmal, új ajánlatként menti.
        </p>
        <AjanlatLista
          regiek
          canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
          canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
        />
        <h2 className="mb-2 mt-8 text-[14px] font-semibold text-text-primary">A korábbi szerkesztő ajánlatai</h2>
        <p className="mb-4 text-[12.5px] text-text-muted">
          A korábbi szerkesztővel készült ajánlatok. Megnyithatók és szerkeszthetők; új ajánlatot az „Ajánlatok” fülön
          érdemes kezdeni (katalógussal, sablonokkal, XLSX / PDF exporttal).
        </p>
        <ArajanlatokContent
          ajanlatok={ajanlatok}
          tetelek={tetelek}
          canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
          canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
          canDelete={canDoPageAction(pagePermissions, PAGE, "delete")}
        />
      </div>
    </div>
  );
}
