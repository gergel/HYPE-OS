import Link from "next/link";
import { ConfirmProvider } from "@/components/ConfirmProvider";
import { ToastProvider } from "@/components/ToastProvider";
import { KrumpelloNav } from "@/components/krumpello/KrumpelloNav";
import { KrumpelloTemaTest } from "@/components/krumpello/KrumpelloTemaTest";

/** A Krumpello váza - SZÁNDÉKOSAN nem az (app) elrendezés alatt.
 *
 * Külön útvonal-csoport, tehát nem örökli a HYPE OS oldalsávját és fejlécét:
 * itt nincs projekt, nincs naptár, nincs papírozás, csak pénzügy. Aki átvált,
 * egy MÁSIK felületre érkezik, nem a HYPE OS egyik aloldalára - ezt a
 * `.krumpello-root` arculat (sötét éjkék + narancs, lásd
 * app/krumpello-theme.css) az első pillanatban meg is mutatja.
 *
 * Miért számít ez a látvány? Mert két kassza van egy rendszerben. Ha
 * ugyanúgy nézne ki, egy fáradt pillanatban bárki a rossz helyre vezetne be
 * egy tételt - a másik felület viszont már azelőtt szól, hogy elkezdené.
 *
 * A jogosultság-ellenőrzés nem itt van: a middleware a "/krumpello" oldal-
 * kulccsal már a renderelés előtt elutasítja, akinek nincs joga (lásd
 * lib/nav.ts KULON_JOGOSULTSAGOK), a backend pedig minden végponton külön is
 * ellenőrzi (routes/krumpello.py) - a felület elrejtése önmagában sosem
 * védelem.
 */
export default function KrumpelloLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // A `.krumpello-root` a PROVIDEREKEN KÍVÜL van, nem csak a tartalom körül:
    // a megerősítő ablak és a toast a providerek saját JSX-ében renderelődik,
    // a tartalom TESTVÉREKÉNT. Beljebb téve az arculatot ezek nem örökölnék, és
    // egy Krumpello-oldalról nyíló kérdés a HYPE OS titánszürkéjében jelenne
    // meg - pont az a szakadás, amit az egész külön arculat el akar kerülni.
    <div className="krumpello-root">
      {/* A felugró ablakok egy része a <body> végére portálozik (lásd
          ModalReteg), tehát kilép ebből a dobozból - nekik a body-ra tett
          osztály viszi át az arculatot. */}
      <KrumpelloTemaTest />
      <ToastProvider>
        <ConfirmProvider>
          <div className="flex min-h-screen">
            <aside className="hidden w-[228px] shrink-0 flex-col border-r border-border bg-surface-1 px-3 py-6 md:flex">
              <div className="mb-8 px-3">
                <p className="text-[19px] font-extrabold tracking-[-0.02em] text-text-accent">krumpello</p>
                <p className="mt-0.5 text-[11px] text-text-muted">Pénzügy</p>
              </div>
              <KrumpelloNav />
              <div className="mt-auto border-t border-border pt-4">
                {/* Vissza a HYPE OS-be. Mindig látszik: a Krumpello egy
                    mellékág, nem zsákutca. */}
                <Link
                  href="/dashboard"
                  className="flex items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-[12.5px] text-text-secondary transition-colors hover:bg-surface-3 hover:text-text-primary"
                >
                  ← Vissza a HYPE OS-be
                </Link>
              </div>
            </aside>
            <main className="flex min-w-0 flex-1 flex-col">{children}</main>
          </div>
        </ConfirmProvider>
      </ToastProvider>
    </div>
  );
}
