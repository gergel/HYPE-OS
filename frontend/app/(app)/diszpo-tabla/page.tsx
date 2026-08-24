import { notFound } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { DiszpoTablaRacs } from "@/components/DiszpoTablaRacs";
import { MunkanapokKartya } from "@/components/MunkanapokKartya";
import {
  getDiszpoMunkalap,
  getDiszpoMunkalapok,
  getEmployees,
  getMyPagePermissions,
} from "@/lib/api";

const PAGE = "/diszpo-tabla";

/** A HYPE 2026 táblázat - a Google Sheet munkalapjai a rendszerben.
 *
 * Ez a tábla nem csak beosztás volt: a CELLA SZÍNE hordozta a legfontosabb
 * adatot, azt, hogy ki melyik nap dolgozott. Ebből derül ki, hány munkanapja
 * van valakinek egy hónapban - és ez dönti el, mikor fogy el a szerződött
 * napjainak száma, vagyis mikortól kell a PLUSZ NAP díján számolni a
 * projektek önköltségébe (lásd backend services/munkanap_szamlalo.py).
 *
 * A munkalapok fülekként állnak egymás mellett, ahogy a Sheetben. */
export default async function DiszpoTablaPage({
  searchParams,
}: {
  searchParams: Promise<{ lap?: string }>;
}) {
  const { lap } = await searchParams;
  const [munkalapok, pagePermissions] = await Promise.all([getDiszpoMunkalapok(), getMyPagePermissions()]);

  if (munkalapok.length === 0) {
    return (
      <div className="flex flex-1 flex-col">
        <TopBar />
        <div className="flex-1 p-4 md:p-8">
          <Card title="HYPE 2026 tábla">
            <p className="text-[13px] text-text-secondary">
              A táblázat még nincs átvéve. A backend gépén futtatható:{" "}
              <code className="rounded bg-surface-3 px-1 py-0.5">
                python scripts/diszpo_tabla_import.py --vegrehajt
              </code>{" "}
              – ez hozza át a Google Sheet minden munkalapját, a cellák színével együtt.
            </p>
          </Card>
        </div>
      </div>
    );
  }

  const aktivId = lap ? Number(lap) : munkalapok[0].id;
  const aktiv = munkalapok.find((m) => m.id === aktivId);
  if (!aktiv) notFound();

  const [munkalap, emberek] = await Promise.all([getDiszpoMunkalap(aktiv.id), getEmployees()]);
  if (!munkalap) notFound();

  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");
  // A sor/oszlop TÖRLÉSE külön jog: az a tartalmát is viszi, és egy 146
  // oszlopos munkalapon nem visszavonható egy kattintással.
  const canDelete = pagePermissions === null || !!pagePermissions[PAGE]?.includes("delete");

  // A "Munkanapok" kártya kezdő hónapja - a mai. A kártya ezután a saját
  // kliens-oldali állapotát vezeti (lásd MunkanapokKartya), a rács tehát nem
  // renderelődik újra, amikor ott hónapot vált valaki.
  const ma = new Date();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <Card title="HYPE 2026 tábla">
          {/* A FÜLEK - ahogy a Sheetben, balról jobbra. */}
          <div className="mb-4 flex flex-wrap gap-1.5 border-b border-border pb-3">
            {munkalapok.map((m) => (
              <Link
                key={m.id}
                href={`/diszpo-tabla?lap=${m.id}`}
                className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] transition-colors ${
                  m.id === aktiv.id
                    ? "bg-bg-accent text-text-accent"
                    : "text-text-secondary hover:bg-surface-3"
                }`}
              >
                {m.nev}
              </Link>
            ))}
          </div>

          <DiszpoTablaRacs
            munkalap={munkalap}
            canEdit={canEdit}
            canDelete={canDelete}
            emberek={emberek.map((e) => ({ id: e.id, nev: e.full_name }))}
          />
        </Card>

        {/* A TÁBLÁZAT LÉNYEGE SZÁMOKBAN: ki hány napot dolgozott ebben a
            hónapban, és kinél fogyott el a szerződött napszám. Külön
            kliens-komponens - lásd a fenti megjegyzést. */}
        <MunkanapokKartya kezdoEv={ma.getFullYear()} kezdoHonap={ma.getMonth() + 1} />
      </div>
    </div>
  );
}
