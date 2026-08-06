"use client";

import { Fragment, type ReactNode } from "react";
import { linkDarabok } from "@/lib/linkek";

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
