import { redirect } from "next/navigation";
import { GyartasTv } from "@/components/gyartas/GyartasTv";
import { getGyartasTv, getMyPagePermissions } from "@/lib/api";

const PAGE = "/gyartas";

export const metadata = { title: "Gyártás — HYPE OS" };

/** GYÁRTÁS-TV: a gyártási szobában egy TV-re kirakott, élő áttekintő — a heti
 * forgatások és kik dolgoznak, ki mit vág épp, mi küldhető ki, és hol várnak a
 * gyártásra. Menü nélkül, teljes képernyőn; a háttérben folyamatosan frissül
 * (lásd components/gyartas/GyartasTv.tsx, backend services/gyartas_tv.py). */
export default async function GyartasTvPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const kezdo = await getGyartasTv();
  return <GyartasTv kezdo={kezdo} />;
}
