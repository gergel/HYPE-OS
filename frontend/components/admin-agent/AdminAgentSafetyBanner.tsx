/** Az Admin-Ágens biztonságos alapállását MINDIG láthatóvá tevő csík.
 *
 * A modul alapból KI van kapcsolva, a mellékhatások TILTVA, minden feladat L0
 * (árnyék) módban fut: elemez és javasol, de üzleti rekordot nem ír, e-mailt
 * nem küld, külső hívást nem indít. Ezt a szerver-oldali policy engine
 * kényszeríti ki (lásd backend admin_agent/policy.py) - a felület csak
 * megmutatja, épp milyen állapotban van. */
export function AdminAgentSafetyBanner({
  modul,
}: {
  modul: { engedelyezve: boolean; mellekhatas_engedelyezve: boolean; veszleallitas: boolean };
}) {
  if (modul.veszleallitas) {
    return (
      <div className="mb-5 rounded-[var(--radius)] bg-bg-danger px-4 py-3 text-[13px] text-text-danger">
        <p className="font-medium">Vészleállítás aktív</p>
        <p className="mt-0.5 text-text-danger/80">
          Az ágens minden mellékhatásos lépése le van tiltva. A Beállításokban lehet feloldani.
        </p>
      </div>
    );
  }
  if (!modul.engedelyezve) {
    return (
      <div className="mb-5 rounded-[var(--radius)] bg-surface-3 px-4 py-3 text-[13px] text-text-secondary">
        <p className="font-medium text-text-primary">A modul ki van kapcsolva — árnyék (L0) mód</p>
        <p className="mt-0.5">
          Az ágens csak elemez és javaslatot készít. Nem ír üzleti rekordot, nem küld e-mailt, és nem indít külső
          hívást. Éles működéshez a Beállításokban kell bekapcsolni a modult és — külön — a mellékhatásokat.
        </p>
      </div>
    );
  }
  if (!modul.mellekhatas_engedelyezve) {
    return (
      <div className="mb-5 rounded-[var(--radius)] bg-bg-warning px-4 py-3 text-[13px] text-text-warning">
        <p className="font-medium">Modul bekapcsolva, mellékhatások letiltva</p>
        <p className="mt-0.5 text-text-warning/80">
          Az ágens dolgozik és javaslatokat készít, de a jóváhagyott műveletek végrehajtása (rekordírás, e-mail) még
          le van tiltva. A végrehajtáshoz a mellékhatásokat is engedélyezni kell.
        </p>
      </div>
    );
  }
  return (
    <div className="mb-5 rounded-[var(--radius)] bg-bg-success px-4 py-3 text-[13px] text-text-success">
      <p className="font-medium">Modul és mellékhatások engedélyezve</p>
      <p className="mt-0.5 text-text-success/80">
        A jóváhagyott műveletek a bizalmi szintnek megfelelően végrehajthatók. R3 kockázatú lépés soha nem
        automatizálható.
      </p>
    </div>
  );
}
