import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { FileCheck2, FileSignature } from "lucide-react";
import { formatFt } from "@/lib/ido";
import type { ElkeszultSzerzodes, PerformanceCertificate } from "@/lib/api";

/** Alvállalkozói szerződés/TIG áttekintés egy PROJEKTKÓDON, forgatás nélkül -
 * lásd projekt/ProjektPapirokEsKoltsegek (a forgatáshoz kötött megfelelője,
 * ugyanaz a szerep és ugyanaz az indoklás): ez NÉZET, nem munkafelület. A
 * tényleges papírkészítés (mentés, generálás, küldés, kihagyás, törlés) az
 * Utókövetésen történik, lásd utokovetes/projektkodok/[id] - ide csak az
 * állás látszik, a művelethez a lenti linkkel kell átmenni. */
export function AlvallalkozoiPapirokAttekintes({
  projectCodeId,
  szerzodesek,
  tigek,
  lathatKoltseget,
}: {
  projectCodeId: number;
  szerzodesek: ElkeszultSzerzodes[];
  tigek: PerformanceCertificate[];
  lathatKoltseget: boolean;
}) {
  const utokovetes = `/utokovetes/projektkodok/${projectCodeId}`;

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <Card title={`Alvállalkozói szerződések (${szerzodesek.length})`} icon={FileSignature}>
        {szerzodesek.length === 0 ? (
          <p className="text-[13px] text-text-secondary">Még nincs elkészült szerződés ehhez a projektkódhoz.</p>
        ) : (
          <ul className="space-y-2">
            {szerzodesek.map((sz) => (
              <li key={sz.contract_id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                <span className="text-text-primary">{sz.full_name}</span>
                <span className="flex items-center gap-2">
                  {sz.netto_osszeg != null && lathatKoltseget && (
                    <span className="text-text-secondary">{formatFt(sz.netto_osszeg)}</span>
                  )}
                  <StatusBadge
                    label={sz.alairva ? "Aláírva" : (sz.szerzodes_allapota ?? "Készítés alatt")}
                    tone={sz.alairva ? "success" : sz.szerzodes_allapota === "Kiküldve" ? "warning" : "neutral"}
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
        <a href={utokovetes} className="mt-3 block text-[12.5px] text-text-accent hover:underline">
          Szerződés készítése, kiküldése → Utókövetés
        </a>
      </Card>

      <Card title={`Alvállalkozói TIG-ek (${tigek.length})`} icon={FileCheck2}>
        {tigek.length === 0 ? (
          <p className="text-[13px] text-text-secondary">Még nincs teljesítési igazolás ehhez a projektkódhoz.</p>
        ) : (
          <ul className="space-y-2">
            {tigek.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                <span className="text-text-primary">{t.ceg_neve ?? `TIG #${t.id}`}</span>
                <span className="flex items-center gap-2">
                  {t.netto_osszeg != null && lathatKoltseget && (
                    <span className="text-text-secondary">{formatFt(t.netto_osszeg)}</span>
                  )}
                  {/* A KIFIZETÉS a TIG utolsó lépése - amíg nincs meg, a papír
                      önmagában nem zárja le az ügyet (lásd
                      ProjektPapirokEsKoltsegek, a forgatás-alapú
                      megfelelője). */}
                  <StatusBadge
                    label={
                      t.szamla_kifizetve
                        ? "Kifizetve"
                        : t.szamla_kihagyva
                          ? "Nincs számla"
                          : (t.allapot ?? "Készítés alatt")
                    }
                    tone={t.szamla_kifizetve ? "success" : t.allapot === "Kiküldve" ? "warning" : "neutral"}
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
        <a href={utokovetes} className="mt-3 block text-[12.5px] text-text-accent hover:underline">
          TIG készítése, kiküldése → Utókövetés
        </a>
      </Card>
    </div>
  );
}
