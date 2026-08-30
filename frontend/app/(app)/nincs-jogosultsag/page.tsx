import { ShieldAlert } from "lucide-react";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { VisszaGomb } from "@/components/VisszaGomb";

/** Ide irányít a middleware, ha valaki olyan oldalra próbál eljutni
 * (linkről, könyvjelzőről, kézzel beírt címről), amihez a page_permissions
 * beállítása szerint nincs hozzáférése (lásd middleware.ts). Eddig ilyenkor
 * csendben a Dashboardra dobta a felhasználót, magyarázat nélkül - onnan úgy
 * tűnt, mintha a kattintott link egyszerűen nem működne.
 *
 * SZERVER-komponens (mint minden más oldal, lásd TopBar megjegyzését) - a
 * "Vissza" gomb, aminek kliens-oldali böngésző-előzményre van szüksége,
 * külön komponensben van (lásd VisszaGomb.tsx). */
export default function NincsJogosultsagPage() {
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex flex-1 items-center justify-center p-4 md:p-8">
        <Card title="Nincs jogosultságod ehhez az oldalhoz">
          <div className="flex flex-col items-center gap-4 py-6 text-center">
            <ShieldAlert className="h-10 w-10 text-text-muted" aria-hidden />
            <p className="max-w-sm text-[13px] text-text-secondary">
              A fiókodhoz beállított jogosultságok ezt az oldalt nem engedik meg. Ha ez tévedés, keresd meg az
              adminisztrátort.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <VisszaGomb />
              <a
                href="/dashboard"
                className="rounded-[var(--radius)] border border-border px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Dashboard
              </a>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
