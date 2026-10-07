import { TopBar } from "@/components/TopBar";
import { AdminEllenorzes } from "@/components/admin-ellenorzes/AdminEllenorzes";
import { getEmployees } from "@/lib/api";

/** ADMINISZTRÁCIÓ ELLENŐRZÉSE (a felhasználó kérése, 2026-10): a tulajdonos
 * itt követi, mikor mi készült el, mindenhez van-e papír, és nincs-e csendben
 * kihagyva semmi - és itt jelez Lara, ha a figyelt kolléga munkájában valami
 * szokatlan. Az adatok a kliensen töltődnek: a szerver csak a tulajdonosnak
 * adja ki őket (lásd backend routes/admin_ellenorzes.py), bárki másnak 403. */
export default async function AdminEllenorzesPage() {
  const employees = await getEmployees();
  const emberek = employees
    .filter((e) => e.is_active !== false && e.tipus !== "kulsos")
    .map((e) => ({ id: e.id, full_name: e.full_name }))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminEllenorzes emberek={emberek} />
      </div>
    </div>
  );
}
