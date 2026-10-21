import { Trophy } from "lucide-react";
import type { VagoAllas } from "@/lib/api";

/** A verseny állása mint FUTAM: mindenki egy sávban halad, a sáv hossza a
 * pontja az éllovaséhoz képest.
 *
 * Miért nem sima táblázat? Mert a kérdés nem az, hogy "hány pontja van", hanem
 * hogy "mennyivel vagyok lemaradva" - és ezt egy szám sosem mondja el olyan
 * gyorsan, mint két egymás mellé rajzolt sáv. A számok ettől még ott vannak a
 * sáv végén: a látvány nem helyettesíti az adatot, csak elé teszi a
 * viszonyítást.
 *
 * Az arány mindig az ÉLLOVASHOZ mérve 100% - nem egy fix maximumhoz. Így a
 * hónap elején, pár pontnál is van mit nézni, nem három hajszálvékony csík.
 *
 * Szerver-komponens: nincs benne állapot, csak kirajzol - a frissítést az
 * oldal újratöltése hozza. */
export function Versenypalya({ allas }: { allas: VagoAllas[] }) {
  const versenyzok = allas.filter((a) => a.pont > 0);
  if (versenyzok.length === 0) {
    return (
      <p className="text-[13px] text-text-muted">
        Ebben a hónapban még senki nem szerzett pontot. Az első ellenőrzésbe tett anyaggal indul a verseny.
      </p>
    );
  }

  const elso = versenyzok[0].pont;

  return (
    <div className="space-y-3">
      {versenyzok.map((a) => {
        const szazalek = Math.max(4, Math.round((a.pont / elso) * 100));
        const dobogos = a.helyezes <= 3;
        return (
          <div key={a.employee_id}>
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="flex items-center gap-2 text-[13px]">
                <Helyszam helyezes={a.helyezes} />
                <span className={dobogos ? "font-medium text-text-primary" : "text-text-secondary"}>{a.nev}</span>
                {/* Az arányosítás ténye látszódjon: aki kevesebb napot
                    dolgozott, annak a pontja fel van szorozva - ha ez rejtve
                    maradna, a lista igazságtalannak tűnne. */}
                {a.munkanap !== 20 && (
                  <span className="text-[11px] text-text-muted" title={`${a.nyers_pont} nyers pont ${a.munkanap} munkanapra arányosítva`}>
                    {a.munkanap} nap
                  </span>
                )}
              </span>
              <span className="shrink-0 text-[13px] font-semibold tabular-nums text-text-primary">
                {a.pont.toLocaleString("hu-HU")} pont
              </span>
            </div>
            {/* A sáv mindig kap keretet: a mezőny végén a kitöltés (surface-4)
                alig válik el a pályától (surface-3), és pont ott a legfontosabb
                látni, hol tart valaki - a lemaradó sáv ne olvadjon a háttérbe. */}
            <div className="h-7 overflow-hidden rounded-[var(--radius)] bg-surface-3">
              <div
                className={`flex h-full items-center justify-end rounded-[var(--radius)] border px-2 ${
                  a.helyezes === 1
                    ? "border-[color:var(--text-warning)]/50 bg-bg-warning"
                    : dobogos
                      ? "border-[color:var(--text-accent)]/40 bg-bg-accent"
                      : "border-border-strong bg-surface-4"
                }`}
                style={{ width: `${szazalek}%` }}
              >
                {/* A bontás a sávon belül: mennyi jött ellenőrzésből és
                    mennyi vágásból. Csak ha elfér - keskeny sávon olvashatatlan
                    lenne, és a lényeg úgyis a hossz. */}
                {szazalek >= 35 && (
                  <span className="truncate text-[11px] text-text-secondary">
                    {a.ellenorzes_db} anyag · {Math.round(a.vagas_perc / 60)} óra vágás
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Helyezés-jelölő. Az első hely kupát kap, a többi számot - a dobogó legyen
 * ránézésre megkülönböztethető, ne kelljen elolvasni. */
function Helyszam({ helyezes }: { helyezes: number }) {
  if (helyezes === 1) {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-bg-warning text-text-warning">
        <Trophy size={12} aria-label="Első helyen" />
      </span>
    );
  }
  return (
    <span
      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold tabular-nums ${
        helyezes <= 3 ? "bg-bg-accent text-text-accent" : "bg-surface-3 text-text-muted"
      }`}
    >
      {helyezes}
    </span>
  );
}
