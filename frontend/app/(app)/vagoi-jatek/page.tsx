import { Gift, Trophy } from "lucide-react";
import { TopBar } from "@/components/TopBar";
import { Versenypalya } from "@/components/vagoi-jatek/Versenypalya";
import { NyeremenySzerkeszto } from "@/components/vagoi-jatek/NyeremenySzerkeszto";
import { MunkanapSzerkeszto } from "@/components/vagoi-jatek/MunkanapSzerkeszto";
import { getMyPagePermissions, getVagoHonap, getVagoKorabbiHonapok, getVagoSzabalyok } from "@/lib/api";
import { HONAP_NEVEK } from "@/lib/ido";
import type { VagoHonap } from "@/lib/api";

export const metadata = { title: "Vágói játék" };

function honapCimke(ev: number, honap: number): string {
  return `${ev}. ${HONAP_NEVEK[honap - 1]}`;
}

/** Vágói játék - havi pontverseny.
 *
 * Az oldal három részből áll, ebben a sorrendben, mert ez a fontossági
 * sorrend is: mi a nyeremény, ki hol tart most, és mi volt eddig. */
export default async function VagoiJatekPage() {
  const [honap, korabbiak, szabalyok, jogok] = await Promise.all([
    getVagoHonap(),
    getVagoKorabbiHonapok(12),
    getVagoSzabalyok(),
    getMyPagePermissions(),
  ]);

  // A nyeremény és a munkanapok állítása szerkesztési jog - az állás
  // mindenkinek látszik, akit beengedünk (a verseny lényege, hogy lássák
  // egymást). A backend ettől függetlenül minden íráskor ellenőriz.
  const szerkesztheto = jogok === null || (jogok["/vagoi-jatek"] ?? []).includes("edit");

  return (
    <>
      <TopBar />
      <div className="p-8">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="t-page">Vágói játék</h1>
            <p className="mt-1.5 text-[13px] text-text-secondary">
              Minden ellenőrzésbe tett anyag {szabalyok.ellenorzes_pont} pont, minden{" "}
              {szabalyok.perc_per_pont} perc vágás 1 pont. A hónap végén a legtöbb pontot gyűjtő viszi a nyereményt.
            </p>
          </div>
          {honap && szerkesztheto && (
            <NyeremenySzerkeszto
              ev={honap.ev}
              honap={honap.honap}
              nyeremeny={honap.nyeremeny}
              megjegyzes={honap.megjegyzes}
            />
          )}
        </div>

        {honap === null ? (
          <p className="text-[13px] text-text-danger">Nem sikerült betölteni a versenyt.</p>
        ) : (
          <div className="space-y-6">
            <NyeremenyKartya honap={honap} szerkesztheto={szerkesztheto} />

            <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6">
              <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="t-section">Állás – {honapCimke(honap.ev, honap.honap)}</h2>
                <span className="text-[12px] text-text-muted">
                  {honap.allas.filter((a) => a.pont > 0).length} versenyző
                </span>
              </div>
              <Versenypalya allas={honap.allas} />
            </div>

            {honap.allas.length > 0 && (
              <Reszletek honap={honap} szerkesztheto={szerkesztheto} alapMunkanap={szabalyok.alap_munkanap} />
            )}

            <DicsosegTabla honapok={korabbiak} />
          </div>
        )}
      </div>
    </>
  );
}

/** A nyeremény - a legfelső helyen, mert ezért megy a verseny. */
function NyeremenyKartya({ honap, szerkesztheto }: { honap: VagoHonap; szerkesztheto: boolean }) {
  if (!honap.nyeremeny) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[color:var(--text-warning)]/35 bg-bg-warning p-5">
        <p className="text-[13.5px] font-medium text-text-warning">
          Erre a hónapra még nincs kihirdetve nyeremény.
        </p>
        <p className="mt-1 text-[12.5px] text-text-secondary">
          {szerkesztheto
            ? "A verseny akkor működik, ha a hónap elején tudják, miért mennek – hirdesd ki a jobb felső gombbal."
            : "Szólj az adminnak, hogy hirdesse ki."}
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-[var(--radius-lg)] border border-[color:var(--text-warning)]/35 bg-bg-warning p-6">
      <p className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-text-muted">
        <Gift size={13} />A hónap nyereménye
      </p>
      <p className="mt-1.5 text-[26px] font-semibold leading-tight text-text-warning">{honap.nyeremeny}</p>
      {honap.megjegyzes && <p className="mt-1.5 text-[13px] text-text-secondary">{honap.megjegyzes}</p>}
    </div>
  );
}

/** A pontok bontása - "ez a szám miből jött ki", plusz a munkanapok
 * szerkesztése. A versenypálya alatt van, mert az a fontosabb: ez már a
 * részletkérdés. */
function Reszletek({
  honap,
  szerkesztheto,
  alapMunkanap,
}: {
  honap: VagoHonap;
  szerkesztheto: boolean;
  alapMunkanap: number;
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6">
      <h2 className="t-section mb-1">Pontok bontása</h2>
      <p className="mb-4 text-[12.5px] text-text-muted">
        A <strong className="text-text-secondary">munkanap</strong> oszlop teszi igazságossá a versenyt: mindenki
        pontja úgy arányosodik, mintha {alapMunkanap} napja lett volna. Menet közben is átírható – betegség,
        szabadság, plusz vállalt nap.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-2 pr-4 text-left font-medium text-text-muted">Név</th>
              <th className="py-2 pr-4 text-right font-medium text-text-muted">Ellenőrzésbe tett</th>
              <th className="py-2 pr-4 text-right font-medium text-text-muted">Vágás</th>
              <th className="py-2 pr-4 text-right font-medium text-text-muted">Nyers pont</th>
              <th className="py-2 pr-4 text-right font-medium text-text-muted">Munkanap</th>
              <th className="py-2 text-right font-medium text-text-muted">Pont</th>
            </tr>
          </thead>
          <tbody>
            {honap.allas.map((a) => (
              <tr key={a.employee_id} className="border-b border-border last:border-0">
                <td className="py-2.5 pr-4 text-text-primary">{a.nev}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                  {a.ellenorzes_db} db
                  <span className="ml-1.5 text-[11px] text-text-muted">{a.ellenorzes_pont} p</span>
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                  {Math.round(a.vagas_perc / 60)} óra
                  <span className="ml-1.5 text-[11px] text-text-muted">{a.vagas_pont} p</span>
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">{a.nyers_pont}</td>
                <td className="py-2.5 pr-4 text-right">
                  <MunkanapSzerkeszto
                    ev={honap.ev}
                    honap={honap.honap}
                    employeeId={a.employee_id}
                    munkanap={a.munkanap}
                    szerkesztheto={szerkesztheto}
                  />
                </td>
                <td className="py-2.5 text-right font-semibold tabular-nums text-text-primary">{a.pont}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** A korábbi hónapok: ki nyert, ki hányadik lett, hány ponttal. */
function DicsosegTabla({ honapok }: { honapok: VagoHonap[] }) {
  if (honapok.length === 0) return null;
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6">
      <h2 className="t-section mb-4">Korábbi hónapok</h2>
      <div className="space-y-5">
        {honapok.map((h) => (
          <div key={`${h.ev}-${h.honap}`} className="border-b border-border pb-5 last:border-0 last:pb-0">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
              <span className="flex items-center gap-2">
                {/* A kupa a győztes mellett - a dicsőségtáblán ez az egyetlen
                    dolog, amit messziről is látni kell. */}
                <Trophy size={15} className="text-text-warning" aria-hidden />
                <span className="text-[14px] font-medium text-text-primary">{honapCimke(h.ev, h.honap)}</span>
                {h.gyoztes_nev && (
                  <span className="text-[13px] text-text-secondary">
                    – {h.gyoztes_nev} ({h.gyoztes_pont} pont)
                  </span>
                )}
              </span>
              {h.nyeremeny && <span className="text-[12.5px] text-text-muted">Nyeremény: {h.nyeremeny}</span>}
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-1">
              {h.allas
                .filter((a) => a.helyezes > 0)
                .map((a) => (
                  <span key={a.employee_id} className="text-[12.5px] text-text-secondary">
                    <span
                      className={`mr-1 tabular-nums ${a.helyezes === 1 ? "text-text-warning" : "text-text-muted"}`}
                    >
                      {a.helyezes}.
                    </span>
                    {a.nev}
                    <span className="ml-1 tabular-nums text-text-muted">{a.pont}</span>
                  </span>
                ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
