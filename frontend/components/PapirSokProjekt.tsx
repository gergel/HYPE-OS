"use client";

/** SOK PROJEKTRE szóló papír (a felhasználó kérése): ha sok minden van
 * bejelölve, ne kelljen a papíron felsorolni az összes projektet - meg lehet
 * adni, mi álljon helyette, és a kimenő levél tárgyát is. Üresen hagyva a
 * szokásos (a felsorolás, ill. a projektből képzett tárgy) marad. Szerződésnél
 * és TIG-nél ugyanez (lásd backend services/papir_elonezet.py).
 *
 * Csak akkor jelenik meg, ha a papír több projektre szól - vagy ha már van
 * benne beírt szöveg (hogy egy korábban megadott érték ne bújjon el). */
export function PapirSokProjekt({
  tobbProjekt,
  projektSzoveg,
  emailTargy,
  onProjektSzoveg,
  onEmailTargy,
  felsorolas,
  mitIrHelyette,
  tiltva,
}: {
  tobbProjekt: boolean;
  projektSzoveg: string;
  emailTargy: string;
  onProjektSzoveg: (ertek: string) => void;
  onEmailTargy: (ertek: string) => void;
  /** Ami üresen hagyva a papírra kerülne (a kijelölt projektekből). */
  felsorolas: string;
  /** Mit helyettesít a szöveg: "a projektnevek" / "a projektkódok". */
  mitIrHelyette: string;
  tiltva?: boolean;
}) {
  if (!tobbProjekt && !projektSzoveg.trim() && !emailTargy.trim()) return null;
  return (
    <div className="mt-4 rounded-[var(--radius)] border border-border p-3">
      <p className="text-[13px] font-medium text-text-primary">Több projektre szól</p>
      <p className="mb-3 text-[12px] text-text-muted">
        Nem kell felsorolni az összes projektet: írd be, mi álljon a papíron {mitIrHelyette} helyett, és mi legyen a
        levél tárgya. Üresen hagyva a szokásos marad.
      </p>
      <div className="grid grid-cols-1 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-text-muted">A papíron {mitIrHelyette} helyett</label>
          <input
            value={projektSzoveg}
            onChange={(e) => onProjektSzoveg(e.target.value)}
            disabled={tiltva}
            placeholder={felsorolas ? `Üresen: ${felsorolas}` : "Pl. 2026. szeptemberi forgatások"}
            className={inputClass}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] text-text-muted">E-mail tárgya</label>
          <input
            value={emailTargy}
            onChange={(e) => onEmailTargy(e.target.value)}
            disabled={tiltva}
            placeholder="Üresen: a szokásos tárgy (az előnézetben látod)"
            className={inputClass}
          />
        </div>
      </div>
    </div>
  );
}

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";
