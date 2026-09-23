"use client";

import { useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import type { FinanceSummary, OutstandingProject } from "@/lib/api";
import { huDatum } from "@/lib/huDate";
import { formatHuf } from "@/lib/penz";
import { normalizal } from "@/lib/szoveg";

type Csoport = "szamlazando" | "szamla_kint" | "szamla_nelkul";

const PAPIR: Record<string, { cimke: string; tone: "success" | "warning" | "neutral" }> = {
  tig_kesz: { cimke: "TIG kész", tone: "success" },
  tig_hianyzik: { cimke: "TIG hiányzik", tone: "warning" },
  szerzodes_hianyzik: { cimke: "Szerződés hiányzik", tone: "warning" },
  nem_kell: { cimke: "Papír nem kell", tone: "neutral" },
};

/** PROJEKT-KINTLÉVŐSÉGEK: minden projektkód, amiért még nem jött meg a pénz
 * (lásd backend services/kintlevoseg.py) - három teendő szerint:
 *
 * - **Számlázandó**: még nincs számla - ide kell kiállítani;
 * - **Kiállítva, nem fizetve**: kint a számla, a lejárt határidős elöl;
 * - **Számla nélkül**: számla nem lesz, de a rendezés sincs lezárva.
 *
 * Kimarad, amiről kimondtuk, hogy rendezve van (kifizetve, tranzakció nélkül
 * lezárva, elmaradt esemény, megindokolt 0 Ft). */
export function ProjektKintlevosegek({ summary }: { summary: FinanceSummary }) {
  const [csoport, setCsoport] = useState<Csoport>(summary.szamlazando_db > 0 || summary.szamla_kint_db === 0 ? "szamlazando" : "szamla_kint");
  const [kereses, setKereses] = useState("");

  const fulek: { kulcs: Csoport; cim: string; db: number; osszeg: number; al?: string }[] = [
    { kulcs: "szamlazando", cim: "Számlázandó", db: summary.szamlazando_db, osszeg: summary.szamlazando_osszeg, al: "még nincs számla" },
    {
      kulcs: "szamla_kint",
      cim: "Kiállítva, nem fizetve",
      db: summary.szamla_kint_db,
      osszeg: summary.szamla_kint_osszeg,
      al: summary.lejart_db ? `ebből lejárt: ${summary.lejart_db} · ${formatHuf(summary.lejart_osszeg)}` : "nincs lejárt",
    },
    { kulcs: "szamla_nelkul", cim: "Számla nélkül, nincs lezárva", db: summary.szamla_nelkul_db, osszeg: summary.szamla_nelkul_osszeg },
  ];

  const osszegNelkul = summary.kintlevo_projektek.filter((p) => p.allapot === csoport && p.kintlevo_osszeg === null).length;
  const q = normalizal(kereses.trim());
  const sorok = summary.kintlevo_projektek.filter(
    (p) =>
      p.allapot === csoport &&
      (!q || normalizal(`${p.projektkod} ${p.projekt_nev ?? ""}`).includes(q)),
  );

  return (
    <div>
      <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-3" role="tablist" aria-label="Kintlévőség csoportok">
        {fulek.map((f) => (
          <button
            key={f.kulcs}
            type="button"
            role="tab"
            aria-selected={csoport === f.kulcs}
            onClick={() => setCsoport(f.kulcs)}
            className={`rounded-[var(--radius)] border px-3 py-2.5 text-left transition-colors ${
              csoport === f.kulcs ? "border-text-accent bg-surface-3" : "border-border hover:bg-surface-3"
            }`}
          >
            <span className="block text-[12px] text-text-secondary">
              {f.cim} <span className="tabular-nums text-text-muted">· {f.db}</span>
            </span>
            <span className="block text-[18px] font-medium tabular-nums text-text-primary">{formatHuf(f.osszeg)}</span>
            {f.al && <span className="block text-[11.5px] text-text-muted">{f.al}</span>}
          </button>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] text-text-muted">
          {csoport === "szamlazando"
            ? "Ezekre a munkákra még nem ment ki számla. A régen lezajlott elöl, a még meg nem tartott események a lista végén."
            : csoport === "szamla_kint"
              ? "Kint van a számla, a pénz még nem érkezett meg. A lejárt határidejűek elöl."
              : "Kimondtuk, hogy számla nem lesz, de azt nem, hogy a pénz megjött vagy tranzakció nélkül rendeződött. A projektkódon zárd le indokkal."}
          {osszegNelkul > 0 && ` Összeg nélkül: ${osszegNelkul} projektkód — ott a vállalási ár hiányzik.`}
        </p>
        <input
          type="search"
          value={kereses}
          onChange={(e) => setKereses(e.target.value)}
          placeholder="Keresés: projektkód, projekt"
          aria-label="Keresés a kintlévőségek között"
          className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted sm:w-72"
        />
      </div>

      {sorok.length === 0 ? (
        <p className="py-4 text-[13px] text-text-secondary">
          {kereses ? "Nincs találat." : csoport === "szamlazando" ? "Nincs számlázandó projektkód." : csoport === "szamla_kint" ? "Nincs kifizetetlen kiállított számla." : "Nincs ilyen projektkód."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="os-table min-w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-text-secondary">
                <th className="py-1.5 pr-4 font-medium">Projektkód</th>
                {csoport === "szamla_kint" ? (
                  <>
                    <th className="py-1.5 pr-4 font-medium">Számla</th>
                    <th className="py-1.5 pr-4 font-medium">Fizetési határidő</th>
                  </>
                ) : (
                  <>
                    <th className="py-1.5 pr-4 font-medium">Esemény</th>
                    <th className="py-1.5 pr-4 font-medium">{csoport === "szamlazando" ? "Papír" : "Indok"}</th>
                  </>
                )}
                <th className="py-1.5 text-right font-medium">Kintlévő (nettó)</th>
              </tr>
            </thead>
            <tbody>
              {sorok.map((p) => (
                <Sor key={p.project_code_id} p={p} csoport={csoport} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Sor({ p, csoport }: { p: OutstandingProject; csoport: Csoport }) {
  return (
    <tr className={`border-b border-border last:border-0 ${p.esemeny_jovobeli ? "opacity-70" : ""}`}>
      <td className="py-2 pr-4">
        <a href={`/projektek/project-kodok/${p.project_code_id}`} className="text-text-accent hover:underline">
          {p.projektkod}
        </a>
        {p.projekt_nev && <span className="block text-[12px] text-text-muted">{p.projekt_nev}</span>}
      </td>
      {csoport === "szamla_kint" ? (
        <>
          <td className="py-2 pr-4">
            {p.szamlak.length > 0 ? (
              <ul className="flex flex-col gap-0.5">
                {p.szamlak.map((s, i) => (
                  <li key={i} className="text-[12.5px]">
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noreferrer" className="text-text-accent hover:underline">
                        {s.nev}
                      </a>
                    ) : (
                      s.nev
                    )}
                    {s.netto !== null && <span className="text-text-muted"> · {formatHuf(s.netto)}</span>}
                  </li>
                ))}
              </ul>
            ) : p.regi_szamla_url ? (
              <a href={p.regi_szamla_url} target="_blank" rel="noreferrer" className="text-[12.5px] text-text-accent hover:underline">
                Számla (Notion)
              </a>
            ) : (
              <span className="text-[12.5px] text-text-secondary">Bevétel-soron rögzítve</span>
            )}
          </td>
          <td className="py-2 pr-4">
            {p.legkorabbi_hatarido ? (
              <span className="flex flex-col items-start gap-0.5">
                <StatusBadge
                  label={
                    p.lejart
                      ? `${Math.abs(p.hatarido_napok ?? 0)} napja lejárt`
                      : p.hatarido_napok === 0
                        ? "Ma jár le"
                        : `Még ${p.hatarido_napok} nap`
                  }
                  tone={p.lejart ? "danger" : (p.hatarido_napok ?? 99) <= 7 ? "warning" : "neutral"}
                />
                <span className="text-[11.5px] text-text-muted">{huDatum(p.legkorabbi_hatarido)}</span>
              </span>
            ) : (
              <StatusBadge label="Nincs megadva határidő" tone="warning" />
            )}
          </td>
        </>
      ) : (
        <>
          <td className="py-2 pr-4 text-text-secondary">
            {huDatum(p.esemeny_datuma)}
            {p.esemeny_jovobeli && <span className="block text-[11.5px] text-text-muted">még nem volt</span>}
          </td>
          <td className="py-2 pr-4">
            {csoport === "szamlazando" ? (
              p.papir && PAPIR[p.papir] ? <StatusBadge label={PAPIR[p.papir].cimke} tone={PAPIR[p.papir].tone} /> : "–"
            ) : (
              <span className="text-[12.5px] text-text-secondary">{p.megjegyzes ?? "–"}</span>
            )}
          </td>
        </>
      )}
      <td className="py-2 text-right font-medium tabular-nums text-text-primary">
        {p.kintlevo_osszeg === null ? <span className="text-[12.5px] font-normal text-text-warning">Nincs megadva összeg</span> : formatHuf(p.kintlevo_osszeg)}
      </td>
    </tr>
  );
}
