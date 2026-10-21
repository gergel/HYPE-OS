"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";
import type { OnellenorzesFutas } from "@/lib/api";

const TERULETEK: { kulcs: string; cim: string; egyseg: string }[] = [
  { kulcs: "szamla", cim: "Beérkező számlák", egyseg: "rögzített számla" },
  { kulcs: "szerzodes", cim: "Eseti szerződések", egyseg: "szerződés-döntés" },
  { kulcs: "tig", cim: "Alvállalkozói TIG-ek", egyseg: "TIG-döntés" },
  { kulcs: "megrendeloi_szerzodes", cim: "Megrendelői szerződések", egyseg: "döntés" },
  { kulcs: "megrendeloi_tig", cim: "Megrendelői TIG-ek", egyseg: "döntés" },
  { kulcs: "belsos_tig", cim: "Belsős TIG-ek", egyseg: "döntés" },
  { kulcs: "projektkod", cim: "Projektkód-döntések", egyseg: "döntés" },
  { kulcs: "bevetel", cim: "Bevételek (kimenő számla)", egyseg: "fizetés" },
  { kulcs: "elvaras", cim: "Projektkód egésze", egyseg: "" },
  { kulcs: "fogalom", cim: "Rendszer-fogalmak (megértés)", egyseg: "" },
];

function szazalek(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`;
}

/** Lara ÖNELLENŐRZÉSE (kliens).
 *
 * Lara a rögzített számlákra, a projektkódok papír- és számladöntéseire és a
 * teljes Utókövetésre (megrendelői/belsős szerződés, TIG, bevétel) „vakon" (az
 * adott rekord saját tanulsága nélkül) megmondja, mit javasolt volna a jelenlegi
 * tudásával, és összeveti a valósággal. A projektkódok egészén keresi, ami nem a
 * várt módon áll, és a rendszer állapotait is próbálja megérteni. A futásonkénti találati arány mutatja, hogyan tanul; ahol nem érti
 * az eltérést, kérdez (Kérdések oldal). Kétóránként magától is lefut. */
export function LaraOnellenorzes({ kezdo, canRun }: { kezdo: OnellenorzesFutas[]; canRun: boolean }) {
  const router = useRouter();
  const [futasok, setFutasok] = useState(kezdo);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState<"minta" | "teljes" | null>(null);
  const utolso = futasok[0];

  async function futtat(vizsga: "minta" | "teljes" = "minta") {
    setUzenet(null);
    setHiba(null);
    setFut(vizsga);
    try {
      const res = await authFetch(`/api/v1/admin-agent/self-check?vizsga=${vizsga}`, { method: "POST" });
      if (!res.ok) {
        setHiba("Az önellenőrzés nem sikerült.");
        return;
      }
      const d = (await res.json()) as OnellenorzesFutas;
      setFutasok((p) => [{ ...d, id: Date.now(), trigger: "onellenorzes:kezi", veg_at: new Date().toISOString() }, ...p]);
      const v = d.vizsga;
      setUzenet(
        `Kész: ${d.ellenorzott ?? 0} döntést ellenőriztem — pontosság a válaszaid után ${szazalek(d.pontossag)}, ` +
          `vak találati arány ${szazalek(d.talalati_arany)}; ${d.nyitott_elteres ?? 0} nyitott eltérés.` +
          (v
            ? ` Vizsga a régi adaton (${v.mod === "teljes" ? "mind" : `véletlen ${Math.round(v.minta_arany * 100)}%`}): ` +
              `${v.ellenorzott} döntés, ${szazalek(v.pontossag)}.`
            : "") +
          ` ${d.uj_kerdes ?? 0} új kérdésem van` +
          (d.vizsga_kerdes ? ` (ebből ${d.vizsga_kerdes} a régi adatból)` : "") +
          ".",
      );
      router.refresh();
    } finally {
      setFut(null);
    }
  }

  return (
    <div>
      <p className="mb-3 text-[12px] text-text-muted">
        Lara a tanulás kezdete óta rögzített munkára megmondja, mit javasolt volna a mostani tudásával (az adott
        rekord saját tanulsága nélkül), és összeveti azzal, amit döntöttetek: beérkező számlák, a teljes Utókövetés
        (eseti, megrendelői és belsős szerződés és TIG: kellett-e, összeg, ÁFA, tárgy, számla), a projektkódok
        papír- és számladöntései és a bevételek fizetése. A projektkód egészén azt is nézi, ami nem úgy áll, ahogy
        várná (pl. a megrendelő fizetett, de nincs papír), és a rendszer állapotait is próbálja megérteni. Ahol nem
        érti, miért van valami úgy, ahogy,{" "}
        <Link href="/admin-agent/kerdesek" className="text-text-accent hover:underline">
          kérdez
        </Link>
        . Kétóránként magától is lefut, ha a „Tanulás és megfigyelés” be van kapcsolva — és minden körben a tanulás
        kezdete előtti adatból is kivizsgáztat magán egy véletlen adagot (kézzel az összeset is). A{" "}
        <b>pontosság</b> beszámítja a válaszaidat: ha Larának volt igaza (hibás rögzítés), vagy megtanulta az okot, az
        eset nem hiba többé; a kivétel kimarad. A <b>vak arány</b> a szigorú mérce, a saját tanulság nélkül.
      </p>
      {uzenet && (
        <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>
      )}
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      {canRun && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={fut !== null}
            onClick={() => futtat("minta")}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            {fut === "minta" ? "Önellenőrzés fut…" : "Önellenőrzés most"}
          </button>
          <button
            type="button"
            disabled={fut !== null}
            onClick={() => futtat("teljes")}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-primary hover:bg-surface-3 disabled:opacity-50"
          >
            {fut === "teljes" ? "Vizsga az összes adaton… (akár pár perc)" : "Vizsga az összes elérhető adaton"}
          </button>
        </div>
      )}
      {!utolso ? (
        <p className="text-[13px] text-text-secondary">Még nem futott önellenőrzés.</p>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Szam
              cimke="Pontosság a válaszaid után"
              ertek={szazalek(utolso.pontossag ?? utolso.talalati_arany)}
              al={
                (utolso.lara_helyes ? `${utolso.lara_helyes}× Larának volt igaza` : "") +
                (utolso.lara_helyes && utolso.tanult ? " · " : "") +
                (utolso.tanult ? `${utolso.tanult} megtanulva` : "") || "a megválaszolt eltérésekkel"
              }
            />
            <Szam cimke="Vak találati arány" ertek={szazalek(utolso.talalati_arany)} al="szigorú: a saját tanulság nélkül" />
            <Szam cimke="Ellenőrzött döntés" ertek={String(utolso.ellenorzott ?? 0)} al="számla, projektkód, papír, bevétel" />
            <Szam
              cimke="Nyitott eltérés"
              ertek={String(utolso.nyitott_elteres ?? Math.max(0, (utolso.elter ?? 0) + (utolso.nem_tudta ?? 0) - (utolso.megmagyarazva ?? 0)))}
              al={utolso.megmagyarazva ? `${utolso.megmagyarazva} már megválaszolva` : "amire még nincs válasz"}
            />
            <Szam cimke="Tudása" ertek={String(utolso.szabalyok ?? 0)} al={`élesített szabály · ${utolso.tanult_partnerek ?? 0} tanult partner`} />
          </div>
          {utolso.vizsga && (
            <div className="mb-4 rounded-[var(--radius)] border border-border bg-surface-3 px-3.5 py-3">
              <p className="text-[11.5px] uppercase tracking-[0.08em] text-text-muted">
                Vizsga a régi adaton ·{" "}
                {utolso.vizsga.mod === "teljes"
                  ? "az összes elérhető adat"
                  : `véletlen ${Math.round(utolso.vizsga.minta_arany * 100)}%-os adag (futásonként más)`}
              </p>
              <p className="mt-1 text-[13px] text-text-primary">
                {utolso.vizsga.ellenorzott > 0 ? (
                  <>
                    <b className="tabular-nums">{utolso.vizsga.ellenorzott}</b> döntés a tanulás kezdete előttről —
                    pontosság <b className="tabular-nums">{szazalek(utolso.vizsga.pontossag)}</b>, vak arány{" "}
                    <b className="tabular-nums">{szazalek(utolso.vizsga.talalati_arany)}</b>.
                  </>
                ) : (
                  "Ebben a körben nem volt régi, lezárt döntés a mintában."
                )}
              </p>
            </div>
          )}
          {utolso.teruletek && (
            <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-5">
              {TERULETEK.filter((t) => utolso.teruletek?.[t.kulcs] !== undefined || ["szamla", "szerzodes", "tig"].includes(t.kulcs)).map((t) => {
                const d = utolso.teruletek?.[t.kulcs];
                return (
                  <div key={t.kulcs} className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
                    <p className="text-[11.5px] text-text-muted">{t.cim}</p>
                    <p className="text-[18px] font-medium tabular-nums text-text-primary">
                      {szazalek(d?.pontossag ?? d?.talalati_arany)}
                      {d?.pontossag != null && d.talalati_arany != null && d.pontossag !== d.talalati_arany && (
                        <span className="ml-1.5 text-[11.5px] font-normal text-text-muted">vak: {szazalek(d.talalati_arany)}</span>
                      )}
                    </p>
                    <p className="text-[11.5px] text-text-muted">
                      {d && d.ellenorzott
                        ? (t.kulcs === "fogalom"
                            ? `${d.egyezik}/${d.ellenorzott} állapotot ért · ${d.elter} még kérdés`
                            : t.kulcs === "elvaras"
                              ? `${d.egyezik}/${d.ellenorzott} a várt módon áll · ${d.elter} eltér`
                              : `${d.egyezik}/${d.ellenorzott} ${t.egyseg} eltalálva · ${d.elter} eltért`) +
                          (d.nem_tudta ? ` · ${d.nem_tudta} nem tudta` : "") +
                          (d.megmagyarazva ? ` · ${d.megmagyarazva} megválaszolva` : "")
                        : "még nincs lezárt eset a tanulás kezdete óta"}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
          <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                  <th className="px-3 py-2 font-medium">Mikor</th>
                  <th className="px-3 py-2 font-medium">Ellenőrzött</th>
                  <th className="px-3 py-2 font-medium">Eltalálta</th>
                  <th className="px-3 py-2 font-medium">Eltért</th>
                  <th className="px-3 py-2 font-medium">Nem tudta</th>
                  <th className="px-3 py-2 font-medium">Pontosság</th>
                  <th className="px-3 py-2 font-medium">Vak arány</th>
                  <th className="px-3 py-2 font-medium">Vizsga (régi adat)</th>
                  <th className="px-3 py-2 font-medium">Új kérdés</th>
                </tr>
              </thead>
              <tbody>
                {futasok.slice(0, 20).map((f) => (
                  <tr key={f.id} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 text-text-secondary">
                      {f.veg_at ? new Date(f.veg_at).toLocaleString("hu-HU") : "—"}
                      <span className="ml-1 text-[11px] text-text-muted">
                        {f.trigger.endsWith("kezi") ? "kézi" : f.trigger.endsWith("utemezett") ? "ütemezett" : ""}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.ellenorzott ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.egyezik ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.elter ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.nem_tudta ?? 0}</td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{szazalek(f.pontossag)}</td>
                    <td className="px-3 py-2 tabular-nums text-text-secondary">{szazalek(f.talalati_arany)}</td>
                    <td className="px-3 py-2 tabular-nums text-text-secondary">
                      {f.vizsga ? `${f.vizsga.ellenorzott} · ${szazalek(f.vizsga.pontossag)}` : "—"}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-text-primary">{f.uj_kerdes ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Szam({ cimke, ertek, al }: { cimke: string; ertek: string; al?: string }) {
  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
      <p className="text-[11.5px] text-text-muted">{cimke}</p>
      <p className="text-[20px] font-medium tabular-nums text-text-primary">{ertek}</p>
      {al && <p className="text-[11.5px] text-text-muted">{al}</p>}
    </div>
  );
}
