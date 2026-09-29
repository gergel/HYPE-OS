import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { ArajanlatFulek } from "@/components/arajanlat/ArajanlatFulek";
import { ArajanlatokContent } from "@/components/arajanlat/ArajanlatokContent";
import { getArajanlatTetelek, getArajanlatok, getMyPagePermissions } from "@/lib/api";
import { canDoPageAction, lathatjaAzOldalt } from "@/lib/permissions";

const PAGE = "/arajanlatok";

/** A KORÁBBI (JSON-alapú) árajánlat-szerkesztő mentett ajánlatai, sablonjai és
 * alap tételei - változatlanul megnyithatók és szerkeszthetők. Az új ajánlatok
 * az „Ajánlatok” fülön készülnek (lásd components/arajanlat/AjanlatSzerkeszto). */
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
