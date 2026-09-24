import { ConfirmProvider } from "@/components/ConfirmProvider";
import { FelugroAblak } from "@/components/FelugroAblak";
import { NavigationTracker } from "@/components/NavigationTracker";
import { Sidebar } from "@/components/Sidebar";
import { ToastProvider } from "@/components/ToastProvider";
import { getMyAccess } from "@/lib/api";
import { LiveProvider } from "@/lib/live";

export default async function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // EGY hívás a korábbi három helyett: mindhárom adat ugyanabból a
  // /user-access/me válaszból jön, fölösleges volt háromszor lekérni minden
  // oldalváltásnál (lásd lib/api.getMyAccess).
  const { allowedPages, pagePermissions, anyagKorlat } = await getMyAccess();

  return (
    <ToastProvider>
      <ConfirmProvider>
        <LiveProvider>
          {/* A Pénzügyek csoportban és a projektkódoknál minden megnyitás
              felugró ablakban (lásd components/FelugroAblak.tsx). */}
          <FelugroAblak>
            <div className="flex min-h-screen">
              <NavigationTracker />
              <Sidebar allowedPages={allowedPages} pagePermissions={pagePermissions} anyagKorlat={anyagKorlat} />
              <main className="flex min-w-0 flex-1 flex-col">{children}</main>
            </div>
          </FelugroAblak>
        </LiveProvider>
      </ConfirmProvider>
    </ToastProvider>
  );
}
