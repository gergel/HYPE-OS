"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";

/** Lara — TANULÁSI FOLYAMAT és MINŐSÉG (kliens).
 *
 * Forrásonként: mikor futott utoljára sikeresen, mi vár, volt-e hiba, és ha
 * nem fut, miért (nincs adat / kikapcsolva / nincs jogosultság / feldolgozási
 * hiba / jóváhagyásra vár). Alatta öt KÜLÖN minőségmérő szám, mindegyik
 * mintaszámmal — a Tudásháló százaléka bizonyíték-erősség, nem pontosság.
 * Lásd backend admin_agent/folyamat.py, minoseg.py, visszacsatolas.py. */

type ForrasSor = {
  kulcs: string;
  cim: string;
  allapot: "nincs_adat" | "kikapcsolva" | "nincs_jogosultsag" | "feldolgozasi_hiba" | "jovahagyasra_var" | "rendben";
  indok: string | null;
  utolso_siker: string | null;
  utolso_hiba: { ido: string; hiba: string } | null;
  futas_db: number;
  hiba_db: number;
  utolso_eredmeny: Record<string, number | boolean>;
};

type Folyamat = {
  leallitva: boolean;
  forrasok: ForrasSor[];
  varakozo: Record<string, number>;
  visszacsatolas: {
    bekapcsolva: boolean;
    auto_szamla_elemzes: boolean;
    fuggo: number;
    kesz: number;
    karanten: number;
    utolso_feldolgozas: string | null;
    utolso_hiba: { hiba: string; ido: string | null; allapot: string } | null;
  };
};

type Minoseg = {
  idoszak_nap: number;
  tudas_megtalalasa: { n: number; talalt_tudast: number | null; hivatkozott_tudasra: number | null; helyes_ha_hivatkozott: number | null; helyes_osszes: number | null; leiras: string };
  uj_eseteken: {
    tudasproba: { n: number; lefedettseg: number | null; pontossag: number | null; szennyezett: boolean | null; ido: string | null };
    onellenorzes_teruletek: Record<string, { talalati_arany: number | null; n: number | null }>;
    leiras: string;
  };
  emberi_javitas: { n: number; javitott_arany: number | null; javitott: number; leiras: string };
  indokolt_kerdezes: { n: number; indokolt_arany: number | null; tudashoz_vezetett: number; rogzitesi_hibat_tart_fel: number; felesleges: number; leiras: string };
  tanulasi_keses: { n: number; median_perc: number | null; forrasonkent: Record<string, { n: number; median_perc: number }>; leiras: string };
  megjegyzes: string;
};

const ALLAPOT: Record<ForrasSor["allapot"], { cimke: string; osztaly: string }> = {
  rendben: { cimke: "Rendben", osztaly: "bg-bg-success text-text-success" },
  jovahagyasra_var: { cimke: "Jóváhagyásra vár", osztaly: "bg-bg-accent text-text-accent" },
  feldolgozasi_hiba: { cimke: "Feldolgozási hiba", osztaly: "bg-bg-danger text-text-danger" },
  nincs_jogosultsag: { cimke: "Nincs jogosultság", osztaly: "bg-bg-warning text-text-warning" },
  kikapcsolva: { cimke: "Kikapcsolva", osztaly: "bg-surface-4 text-text-secondary" },
  nincs_adat: { cimke: "Nincs adat", osztaly: "bg-surface-4 text-text-muted" },
};

const VARAKOZO_CIMKE: Record<string, string> = {
  tudas_jelolt: "tudás-jelölt a Tudástárban",
  kezikonyv_tervezet: "kézikönyv-tervezet",
  nyitott_kerdes: "nyitott kérdés",
  feldolgozatlan_javitas: "feldolgozatlan javítás",
  szabalyjavaslat: "szabályjavaslat / piszkozat",
  visszacsatolas_fuggo: "esemény a gyors visszacsatolás sorában",
};

const KESES_CIMKE: Record<string, string> = {
  javitas_magyarazat: "javításhoz adott magyarázat",
  kerdesre_valasz: "kérdésre adott válasz",
  tanitas: "tanítás",
  megfigyelt_eset: "megfigyelt eset",
  szamla_eset: "számla-eset",
  tapasztalas: "tapasztalat",
  kezikonyv: "kézikönyv",
};

function ido(s: string | null | undefined): string {
  return s ? new Date(s).toLocaleString("hu-HU") : "—";
}

function sz(x: number | null | undefined): string {
  return x === null || x === undefined ? "nincs adat" : `${Math.round(x * 100)}%`;
}

function perc(x: number | null | undefined): string {
  if (x === null || x === undefined) return "nincs adat";
  if (x < 1) return "1 percen belül";
  if (x < 120) return `${Math.round(x)} perc`;
  return `${(x / 60).toFixed(1)} óra`;
}

export function LaraFolyamat() {
  const [f, setF] = useState<Folyamat | null>(null);
  const [m, setM] = useState<Minoseg | null>(null);
  const [hiba, setHiba] = useState(false);

  useEffect(() => {
    let el = false;
    void (async () => {
      const [r1, r2] = await Promise.all([
        authFetch("/api/v1/admin-agent/folyamat"),
        authFetch("/api/v1/admin-agent/minoseg"),
      ]);
      if (el) return;
      if (!r1.ok || !r2.ok) {
        setHiba(true);
        return;
      }
      setF((await r1.json()) as Folyamat);
      setM((await r2.json()) as Minoseg);
    })();
    return () => {
      el = true;
    };
  }, []);

  if (hiba) return <p className="text-[13px] text-text-secondary">A tanulási folyamat állapota most nem tölthető be.</p>;
  if (!f || !m) return <p className="text-[13px] text-text-muted">Betöltés…</p>;

  const varakozo = Object.entries(f.varakozo).filter(([, v]) => v > 0);
  const vc = f.visszacsatolas;
  return (
    <div className="flex flex-col gap-5">
      <div>
        {f.leallitva && (
          <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">
            Lara le van állítva — egyik forrás sem fut.
          </div>
        )}
        <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                <th className="px-3 py-2 font-medium">Forrás</th>
                <th className="px-3 py-2 font-medium">Állapot</th>
                <th className="px-3 py-2 font-medium">Utolsó sikeres futás</th>
                <th className="px-3 py-2 font-medium">Miért / részletek</th>
              </tr>
            </thead>
            <tbody>
              {f.forrasok.map((s) => (
                <tr key={s.kulcs} className="border-b border-border align-top last:border-0">
                  <td className="px-3 py-2 text-text-primary">{s.cim}</td>
                  <td className="px-3 py-2">
                    <span className={`whitespace-nowrap rounded-[var(--radius)] px-2 py-0.5 text-[12px] ${ALLAPOT[s.allapot].osztaly}`}>
                      {ALLAPOT[s.allapot].cimke}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-text-secondary">
                    {ido(s.utolso_siker)}
                    {s.futas_db > 0 && (
                      <span className="block text-[11px] text-text-muted">
                        {s.futas_db} futás{s.hiba_db ? `, ${s.hiba_db} hibás` : ""}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[12px] text-text-secondary">
                    {s.indok ?? "—"}
                    {s.utolso_hiba && s.allapot !== "feldolgozasi_hiba" && (
                      <span className="block text-text-muted">
                        Legutóbbi hiba ({ido(s.utolso_hiba.ido)}): {s.utolso_hiba.hiba}
                      </span>
                    )}
                    {Object.keys(s.utolso_eredmeny ?? {}).length > 0 && (
                      <span className="block text-text-muted">
                        {Object.entries(s.utolso_eredmeny)
                          .slice(0, 6)
                          .map(([k, v]) => `${k}: ${String(v)}`)
                          .join(" · ")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[12px] text-text-muted">
          A futásnapló a 2026-09-es bővítés óta gyűlik; a korábbi futások a fenti kártyákon látszanak.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5 text-[13px]">
          <p className="mb-1 font-medium text-text-primary">Ami vár</p>
          {varakozo.length === 0 ? (
            <p className="text-text-muted">Semmi nem vár feldolgozásra vagy döntésre.</p>
          ) : (
            <ul className="text-text-secondary">
              {varakozo.map(([k, v]) => (
                <li key={k}>
                  {v} {VARAKOZO_CIMKE[k] ?? k}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5 text-[13px]">
          <p className="mb-1 font-medium text-text-primary">Gyors visszacsatolás</p>
          <p className="text-text-secondary">
            {vc.bekapcsolva ? "Bekapcsolva" : "Kikapcsolva (alapállás)"} · automatikus számla-elemzés:{" "}
            {vc.auto_szamla_elemzes ? "be (csak javaslat)" : "ki"}
          </p>
          <p className="text-[12px] text-text-muted">
            Függő: {vc.fuggo} · feldolgozva: {vc.kesz} · karanténban: {vc.karanten} · utolsó feldolgozás:{" "}
            {ido(vc.utolso_feldolgozas)}
          </p>
          {vc.utolso_hiba && (
            <p className="text-[12px] text-text-danger">
              Utolsó hiba ({ido(vc.utolso_hiba.ido)}): {vc.utolso_hiba.hiba}
            </p>
          )}
        </div>
      </div>

      <div>
        <p className="mb-2 text-[12px] text-text-muted">
          Az elmúlt {m.idoszak_nap} nap — öt külön mérőszám. {m.megjegyzes}
        </p>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <Meroszam
            cim="1. Megtalálja-e a releváns tudást"
            n={m.tudas_megtalalasa.n}
            fo={sz(m.tudas_megtalalasa.hivatkozott_tudasra)}
            fo_cimke="hivatkozott jóváhagyott tudásra"
            sorok={[
              ["Talált tudást", sz(m.tudas_megtalalasa.talalt_tudast)],
              ["Helyes, ha hivatkozott", sz(m.tudas_megtalalasa.helyes_ha_hivatkozott)],
              ["Helyes (összes értékelt)", sz(m.tudas_megtalalasa.helyes_osszes)],
            ]}
            leiras={m.tudas_megtalalasa.leiras}
          />
          <Meroszam
            cim="2. Helyesség új eseteken"
            n={m.uj_eseteken.tudasproba.n}
            fo={sz(m.uj_eseteken.tudasproba.pontossag)}
            fo_cimke="pontosság a javasoltakon (Tudáspróba)"
            sorok={[
              ["Lefedettség", sz(m.uj_eseteken.tudasproba.lefedettseg)],
              ["Szennyezett", m.uj_eseteken.tudasproba.szennyezett ? "igen — a vizsgakészlet nincs elkülönítve" : m.uj_eseteken.tudasproba.n ? "nem" : "—"],
              ...Object.entries(m.uj_eseteken.onellenorzes_teruletek).map(
                ([t, d]) => [`Önellenőrzés — ${t}`, `${sz(d.talalati_arany)}${d.n ? ` (n=${d.n})` : ""}`] as [string, string],
              ),
            ]}
            leiras={m.uj_eseteken.leiras}
          />
          <Meroszam
            cim="3. Emberi javítás igénye"
            n={m.emberi_javitas.n}
            fo={sz(m.emberi_javitas.javitott_arany)}
            fo_cimke="javaslatot kellett javítani"
            sorok={[["Javított javaslat", String(m.emberi_javitas.javitott)]]}
            leiras={m.emberi_javitas.leiras}
          />
          <Meroszam
            cim="4. Indokolt kérdezés"
            n={m.indokolt_kerdezes.n}
            fo={sz(m.indokolt_kerdezes.indokolt_arany)}
            fo_cimke="kérdés volt indokolt"
            sorok={[
              ["Tudáshoz vezetett", String(m.indokolt_kerdezes.tudashoz_vezetett)],
              ["Rögzítési hibát tárt fel", String(m.indokolt_kerdezes.rogzitesi_hibat_tart_fel)],
              ["Felesleges volt", String(m.indokolt_kerdezes.felesleges)],
            ]}
            leiras={m.indokolt_kerdezes.leiras}
          />
          <Meroszam
            cim="5. Mennyi idő alatt lesz használható a lecke"
            n={m.tanulasi_keses.n}
            fo={perc(m.tanulasi_keses.median_perc)}
            fo_cimke="medián"
            sorok={Object.entries(m.tanulasi_keses.forrasonkent).map(
              ([k, v]) => [`${KESES_CIMKE[k] ?? k} (n=${v.n})`, perc(v.median_perc)] as [string, string],
            )}
            leiras={m.tanulasi_keses.leiras}
          />
        </div>
      </div>
    </div>
  );
}

function Meroszam({
  cim,
  n,
  fo,
  fo_cimke,
  sorok,
  leiras,
}: {
  cim: string;
  n: number;
  fo: string;
  fo_cimke: string;
  sorok: [string, string][];
  leiras: string;
}) {
  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5 text-[13px]">
      <p className="font-medium text-text-primary">{cim}</p>
      {n === 0 ? (
        <p className="mt-1 text-text-muted">Nincs adat (n = 0).</p>
      ) : (
        <>
          <p className="mt-1 text-[18px] font-medium text-text-primary">
            {fo} <span className="text-[12px] font-normal text-text-muted">{fo_cimke} · n = {n}</span>
          </p>
          <ul className="mt-1 text-[12px] text-text-secondary">
            {sorok.map(([k, v]) => (
              <li key={k}>
                {k}: {v}
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="mt-1.5 text-[11px] text-text-muted">{leiras}</p>
    </div>
  );
}
