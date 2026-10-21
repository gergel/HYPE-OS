/** Vágólapra másolás.
 *
 * SZÁNDÉKOSAN nem csak a `navigator.clipboard`-ot használja: az kizárólag
 * biztonságos környezetben (https vagy localhost) létezik, tehát egy belső
 * hálózati http-címen megnyitott oldalon a másolás némán nem csinálna semmit.
 * Ilyenkor a régi, mindenhol működő úton megyünk: egy ideiglenes textarea +
 * `execCommand("copy")`.
 *
 * A visszatérési érték mondja meg, sikerült-e - a hívó ebből tud visszajelezni
 * a felhasználónak (egy néma "nem történt semmi" a legrosszabb kimenetel). */
export async function vagolapra(szoveg: string): Promise<boolean> {
  if (!szoveg) return false;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(szoveg);
      return true;
    }
  } catch {
    // Elbukhat jogosultság miatt is - ilyenkor jöjjön a tartalék út.
  }
  try {
    const mezo = document.createElement("textarea");
    mezo.value = szoveg;
    // A képernyőn kívülre tesszük, de olvashatóként kell maradnia, különben a
    // kijelölés (és vele a másolás) nem működik.
    mezo.style.position = "fixed";
    mezo.style.top = "-1000px";
    mezo.setAttribute("readonly", "");
    document.body.appendChild(mezo);
    mezo.select();
    const sikeres = document.execCommand("copy");
    document.body.removeChild(mezo);
    return sikeres;
  } catch {
    return false;
  }
}
