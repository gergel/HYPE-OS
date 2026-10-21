import { TopBar } from "@/components/TopBar";
import { AutoAllapotOldal } from "@/components/auto-allapot/AutoAllapotOldal";

/** Egy autó ÁLLAPOT OLDALA (a felhasználó kérése): melyik nap milyen
 * állapotfotó készült róla, és innen kérhető be új fotósor linken. Az adatok
 * a kliensen töltődnek (lásd backend routes/auto_allapot.py). */
export default async function AutoAllapotPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AutoAllapotOldal autoId={Number(id)} />
      </div>
    </div>
  );
}
