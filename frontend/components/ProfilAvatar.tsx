/** Kis kerek profilkép-avatár névhez (a felhasználó kérése: a profilkép
 * látszódjon a hozzászólásoknál és az utómunka kártyák "Kiosztva" soránál is).
 * Kép híján monogramot mutat - ugyanazzal a szabállyal, mint a fejléc
 * avatárja (lásd UserMenu/ProfilSzerkeszto). */

function monogram(nev: string): string {
  const darabok = nev.trim().split(/\s+/).filter(Boolean);
  if (darabok.length === 0) return "?";
  if (darabok.length === 1) return darabok[0].slice(0, 2).toUpperCase();
  return (darabok[0][0] + darabok[darabok.length - 1][0]).toUpperCase();
}

export function ProfilAvatar({ nev, kep, meret = 20 }: { nev: string; kep?: string | null; meret?: number }) {
  const stilus = { width: meret, height: meret, fontSize: Math.max(8, Math.round(meret * 0.42)) };
  if (kep) {
    return (
      // data-URL-t mutat - a next/image itt nem adna semmit.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={kep} alt={nev} title={nev} style={stilus} className="inline-block shrink-0 rounded-full border border-border object-cover align-middle" />
    );
  }
  return (
    <span
      style={stilus}
      title={nev}
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-bg-accent font-medium leading-none text-text-accent align-middle"
    >
      {monogram(nev)}
    </span>
  );
}
