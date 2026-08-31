import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { VisszajelzesLista } from "@/components/deliverable/VisszajelzesLista";
import { getMyPagePermissions, getVagoiVisszajelzesek } from "@/lib/api";
import { canDoPageAction } from "@/lib/permissions";

const PAGE = "/utomunka";

/** Vágói visszajelzések - amit a vágók írnak a leforgatott anyagról.
 *
 * A visszajelzés az anyag oldalán születik (a „Visszajelzés" gomb űrlapja),
 * ide pedig gyűlik: ki írta, melyik anyagról, hol a kész anyag, melyik
 * forgatáshoz tartozik és kik voltak ott. Innen küldhető ki a forgatás
 * diszpó-levelére válaszként - a stábnak CSAK a szöveges megjegyzés és a kész
 * anyag linkje megy ki (lásd backend routes/vagoi_visszajelzesek.py). */
export default async function VagoiVisszajelzesekPage() {
  const [visszajelzesek, pagePermissions] = await Promise.all([
    getVagoiVisszajelzesek(),
    getMyPagePermissions(),
  ]);

  const kikuldve = visszajelzesek.filter((v) => v.diszpora_kikuldve).length;
  const pontozott = visszajelzesek.filter((v) => v.atlag != null);
  const atlag =
    pontozott.length > 0
      ? Math.round((pontozott.reduce((sum, v) => sum + (v.atlag ?? 0), 0) / pontozott.length) * 10) / 10
      : null;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card title={`Vágói visszajelzések (${visszajelzesek.length})`}>
          <p className="mb-4 text-[13px] text-text-secondary">
            Amit a vágók írnak a leforgatott anyagról.
            {atlag != null && <> Összesített átlag: {atlag}/10.</>}
            {kikuldve > 0 && <> {kikuldve} már ki lett küldve a forgatás stábjának.</>} A sort lenyitva látszik
            a teljes megjegyzés és az, kik voltak ott a forgatáson.
          </p>
          <VisszajelzesLista
            visszajelzesek={visszajelzesek}
            // Az Utómunkán a szerepkör-kapu nem érvényes - kizárólag a
            // page_permissions dönt (lásd lib/permissions.canDoPageAction).
            canSend={canDoPageAction(pagePermissions, PAGE, "edit")}
          />
        </Card>
      </div>
    </div>
  );
}
