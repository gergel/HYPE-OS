import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { BevetelekKartya } from "@/components/finance/BevetelekKartya";
import { datumParam, PENZUGYEK_PAGE } from "@/components/finance/listaSegedek";
import { getMyPagePermissions } from "@/lib/api";

/** BEVÉTELEK - önálló oldalon is (a felhasználó kérése: a gyorsabb elérés
 * miatt). Ugyanaz a lista, űrlap és szűrő, mint a Pénzügyekben (lásd
 * components/finance/BevetelekKartya.tsx), ugyanazzal a jogosultsággal. */
export default async function BevetelekPage({
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
        <BevetelekKartya tol={datumParam(sp.bevetel_tol)} ig={datumParam(sp.bevetel_ig)} />
      </div>
    </div>
  );
}
