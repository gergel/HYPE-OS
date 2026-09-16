import { notFound } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { AnyagbekeresReszletek } from "@/components/anyagbekeres/AnyagbekeresReszletek";
import { getAnyagbekeres, getEmployees, getMyPagePermissions } from "@/lib/api";

/** EGY ANYAGBEKÉRÉS admin nézete - leadások, mappák, fájlok, videóigények. */
export default async function AnyagbekeresOldal({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [adat, munkatarsak, pagePermissions] = await Promise.all([
    getAnyagbekeres(Number(id)),
    getEmployees(),
    getMyPagePermissions(),
  ]);
  if (!adat) notFound();
  const canEdit = pagePermissions === null || !!pagePermissions["/media-portal"]?.includes("edit");
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <AnyagbekeresReszletek
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        kezdeti={adat as any}
        munkatarsak={munkatarsak.filter((m) => m.is_active).map((m) => ({ id: m.id, nev: m.full_name }))}
        canEdit={canEdit}
      />
    </div>
  );
}
