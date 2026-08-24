import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { GoogleTablazatImport } from "@/components/kotelezettseg/GoogleTablazatImport";
import { KotelezettsegKezelo } from "@/components/kotelezettseg/KotelezettsegKezelo";
import { getCurrentUser, getEmployees, getKotelezettsegek, getMyPagePermissions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";
import { formatHuf } from "@/lib/penz";

const PAGE = "/kotelezettsegek";

/** E-Rezsi: a cég előfizetései - ami hónapról hónapra vagy évről évre magától
 * lefut a kártyáról.
 *
 * Ez az oldal váltja ki a Google-táblázatot: ugyanaz az adat (szolgáltató,
 * csomag, forduló, ár, felelős, honnan jön a számla), de a forduló itt nem
 * szöveg, hanem dátum - ezért tud szólni, mielőtt lejár, és ezért tud
 * fordulónként várni egy összeget meg egy számlát.
 *
 * A biztosítások és az autók papírjai ugyanezen a motoron futnak, csak külön
 * oldalon (lásd /kotelezettsegek és /autok). */
export default async function ERezsiPage() {
  const [kotelezettsegek, employees, currentUser, pagePermissions] = await Promise.all([
    getKotelezettsegek({ tipus: "elofizetes" }),
    getEmployees(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);

  const aktiv = kotelezettsegek.filter((k) => k.aktiv);
  const lejart = aktiv.filter((k) => k.allapot === "lejart").length;
  const hamarosan = aktiv.filter((k) => k.allapot === "hamarosan").length;
  const nyitott = kotelezettsegek.reduce((sum, k) => sum + k.nyitott_idoszakok, 0);
  // A becsült havi költség a táblázatból hozott forintosított értékekből -
  // csak tájékoztató, mert a devizás tételeknél az árfolyam napról napra
  // változik (a tényleges összeg fordulónként, kézzel kerül be).
  const havonta = aktiv.reduce((sum, k) => sum + (k.huf_becsles_honap ?? 0), 0);

  const emberek = employees
    .map((e) => ({ id: e.id, full_name: e.full_name }))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <Card title={`E-Rezsi – előfizetések (${kotelezettsegek.length})`}>
          <p className="mb-4 text-[13px] text-text-secondary">
            {aktiv.length} aktív előfizetés
            {havonta > 0 && <> · becsült havi költség: {formatHuf(havonta)}</>}
            {lejart > 0 && <> · {lejart} lejárt</>}
            {hamarosan > 0 && <> · {hamarosan} hamarosan lejár</>}
            {nyitott > 0 && <> · {nyitott} fordulónál hiányzik az összeg vagy a számla</>}
          </p>
          <KotelezettsegKezelo
            kotelezettsegek={kotelezettsegek}
            emberek={emberek}
            alapTipus="elofizetes"
            canEdit={canDoAction(currentUser, pagePermissions, PAGE, "edit")}
            canCreate={canDoAction(currentUser, pagePermissions, PAGE, "create")}
            canDelete={canDoAction(currentUser, pagePermissions, PAGE, "delete")}
          />
        </Card>

        {canDoAction(currentUser, pagePermissions, PAGE, "create") && (
          <Card title="Behozatal Google Táblázatból">
            <GoogleTablazatImport />
          </Card>
        )}
      </div>
    </div>
  );
}
