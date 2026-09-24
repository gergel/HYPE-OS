/** Menü és fejléc NÉLKÜLI elrendezés a falra/TV-re kirakott oldalaknak (lásd
 * app/(tv)/gyartas). A bejelentkezést és az oldal-jogosultságot ugyanúgy a
 * middleware őrzi, mint a többi belső oldalnál. */
export default function TvLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <main className="h-screen w-screen overflow-hidden">{children}</main>;
}
