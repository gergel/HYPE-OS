import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { KiadasokKartya } from "@/components/finance/KiadasokKartya";
import { datumParam, PENZUGYEK_PAGE } from "@/components/finance/listaSegedek";
import { getMyPagePermissions } from "@/lib/api";

/** KIADÁSOK - önálló oldalon is (a felhasználó kérése: a gyorsabb elérés
 * miatt, ne csak a Pénzügyek oldal aljáról). Ugyanaz a lista, űrlap és
 * szűrő, mint a Pénzügyekben (lásd components/finance/KiadasokKartya.tsx),
 * ugyanazzal a jogosultsággal. */
export default async function KiadasokPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const pagePermissions = await getMyPagePermissions();
  if (pagePermissions !== null && !pagePermissions[PENZUGYEK_PAGE]?.includes("view")) redirect("/nincs-jogosultsag");
  const sp = await searchParams;
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <KiadasokKartya tol={datumParam(sp.kiadas_tol)} ig={datumParam(sp.kiadas_ig)} />
      </div>
    </div>
  );
}
