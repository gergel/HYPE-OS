"use client";

import { Fragment, useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";
import { linkDarabok } from "@/lib/linkek";
import { vagolapra } from "@/lib/vagolap";

/** Egy link, amit új lapon nyit meg a böngésző.
 *
 * A kattintás megállítása fontos: ezek az értékek helyben szerkeszthető
 * cellákban ülnek (lásd EditableDetailGrid), ahol a cellára kattintás
 * szerkesztő módba vált - enélkül a link megnyitása mellett a mező is
 * átváltana beviteli mezővé. */
export function Hivatkozas({ href, children }: { href: string; children?: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className="text-text-accent break-all hover:underline"
    >
      {children ?? href}
    </a>
  );
}

/** Link EGY kattintásos másoló gombbal (a felhasználó kérése az utómunka
 * "Kész anyag linkje" mezőjéhez - de minden URL-mezőnél hasznos, ezért a
 * részletnézet-rács minden linkje ezt kapja, lásd lib/detail.tsx). A gomb a
 * sikeres másolást pipával jelzi vissza - egy néma gomb után nem tudni,
 * történt-e bármi. */
export function LinkMasolassal({ href }: { href: string }) {
  const [masolva, setMasolva] = useState(false);
  return (
    <span className="inline-flex max-w-full items-center gap-1.5">
      <Hivatkozas href={href} />
      <button
        type="button"
        title="Link másolása"
        onClick={async (e) => {
          // A cellára kattintás szerkesztő módba váltana (lásd Hivatkozas) -
          // a másoló gombnak sem szabad ezt elindítania.
          e.stopPropagation();
          if (await vagolapra(href)) {
            setMasolva(true);
            setTimeout(() => setMasolva(false), 1500);
          }
        }}
        className="shrink-0 rounded-[var(--radius)] p-0.5 text-text-muted hover:bg-surface-3 hover:text-text-primary"
      >
        {masolva ? <Check size={13} className="text-text-success" /> : <Copy size={13} />}
      </button>
    </span>
  );
}

/** Szabad szöveg megjelenítése úgy, hogy a benne lévő linkek kattinthatók
 * legyenek (vágás leírása, gyártás komment). A szöveg minden más része
 * változatlan marad - a sortöréseket a hívó oldal `whitespace-pre-line`
 * osztálya tartja meg. */
export function LinkeltSzoveg({ szoveg }: { szoveg: string }) {
  return (
    <>
      {linkDarabok(szoveg).map((darab, i) => (
        <Fragment key={i}>{darab.href ? <Hivatkozas href={darab.href}>{darab.szoveg}</Hivatkozas> : darab.szoveg}</Fragment>
      ))}
    </>
  );
}
