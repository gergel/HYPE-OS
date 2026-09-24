"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { LaraKerdes, LaraNyomozas, LaraNyomozasStat } from "@/lib/api";

type ValaszOpcio = { ertek: string; cim: string; leiras: string };

const VALASZOK: ValaszOpcio[] = [
  {
    ertek: "mindig",
    cim: "Mindig így kell — tanuld meg szabályként",
    leiras: "Ennél a partnernél mindig így kell. Lara partnerre szabott szabályt tanul belőle.",
  },
  {
    ertek: "magyarazat",
    cim: "Megmagyarázom",
    leiras: "Leírod, miért így van. A magyarázat Lara tudásába kerül, és a hasonló eseteknél ebből dolgozik.",
  },
  {
    ertek: "kivetel",
    cim: "Egyszeri kivétel volt",
    leiras: "Most így kellett, de ez nem szabály. Lara feljegyzi, de nem általánosít belőle.",
  },
  {
    ertek: "hibas",
    cim: "Rosszul rögzítettük — Lara javaslata volt a jó",
    leiras: "Nem tanul belőle. Lara javítási feladatot készít a Munkasorba, megoldási javaslattal.",
  },
];

/** A bővített önellenőrzés döntés-kérdései (projektkód, bevétel, megrendelői
 * papír, belsős TIG): a „mindig így" tudás lesz, nem szabály; a „hiba" javítási
 * feladatot készít Lara felelősének. */
const VALASZOK_DONTES: ValaszOpcio[] = [
  {
    ertek: "mindig",
    cim: "Nála mostantól így van — tanuld meg",
    leiras: "Lara megjegyzi, és ennél a partnernél a következő esetektől ezt várja. A régebbi eseteket nem írja át.",
  },
  VALASZOK[1],
  VALASZOK[2],
  {
    ertek: "hibas",
    cim: "Hiba — javítani kell",
    leiras: "Nem tanul belőle; Lara javítási feladatot készít a felelősnek a Munkasorba, megoldási javaslattal.",
  },
];

const VALASZOK_ELTERES: ValaszOpcio[] = [
  {
    ertek: "mindig",
    cim: "Rendben, nála így szokás",
    leiras: "Ennél a partnernél ez nem hiba. Lara megjegyzi, és erre többé nem kérdez rá.",
  },
  VALASZOK[1],
  VALASZOK[2],
  VALASZOK_DONTES[3],
];

const VALASZOK_FOGALOM: ValaszOpcio[] = [
  {
    ertek: "magyarazat",
    cim: "Elmagyarázom",
    leiras: "Írd le, mit jelent ez az állapot, és jár-e vele teendő (számla, TIG, szerződés). Lara ebből érti meg a rendszert.",
  },
];

function valaszOpciok(k: LaraKerdes): ValaszOpcio[] {
  if (k.tipus === "rendszer_fogalom") return VALASZOK_FOGALOM;
  if (k.tipus === "rendszer_elteres") return VALASZOK_ELTERES;
  if (k.tipus === "admin_dontes") return VALASZOK_DONTES;
  return VALASZOK;
}

const TERULETEK: { kulcs: string; cim: string }[] = [
  { kulcs: "szamla", cim: "Számlák" },
  { kulcs: "szerzodes", cim: "Szerződések" },
  { kulcs: "tig", cim: "TIG-ek" },
  { kulcs: "projektkod", cim: "Projektkódok" },
  { kulcs: "bevetel", cim: "Bevételek" },
  { kulcs: "elteres", cim: "Eltérések" },
  { kulcs: "rendszer", cim: "Rendszer" },
];
const TERULET_EGYES: Record<string, string> = {
  szamla: "Számla",
  szerzodes: "Szerződés",
  tig: "TIG",
  projektkod: "Projektkód",
  bevetel: "Bevétel",
  elteres: "Eltérés",
  rendszer: "Rendszer",
};
const DIMENZIO: Record<string, string> = {
  kihagyas: "kell-e a papír",
  osszeg: "nettó összeg",
  afa: "+ÁFA",
  targy: "megbízás tárgya",
  szamla_kihagyas: "kell-e számla",
};
/** admin_dontes: a bővített terület → a szűrő-terület. */
const DONTES_TERULET: Record<string, string> = {
  megrendeloi_szerzodes: "szerzodes",
  megrendeloi_tig: "tig",
  belsos_tig: "tig",
  projektkod: "projektkod",
  bevetel: "bevetel",
};

function terulet(k: LaraKerdes): string {
  if (k.tipus === "papir") return k.kontextus?.terulet ?? "szerzodes";
  if (k.tipus === "admin_dontes") return DONTES_TERULET[k.kontextus?.terulet ?? ""] ?? "projektkod";
  if (k.tipus === "rendszer_elteres") return "elteres";
  if (k.tipus === "rendszer_fogalom") return "rendszer";
  return "szamla";
}

function bovitett(k: LaraKerdes): boolean {
  return k.tipus === "admin_dontes" || k.tipus === "rendszer_elteres" || k.tipus === "rendszer_fogalom";
}

const VALASZ_CIMKE: Record<string, string> = {
  mindig: "Mindig így — szabály",
  magyarazat: "Magyarázat",
  kivetel: "Egyszeri kivétel",
  hibas: "Hibás rögzítés",
  elvet: "Nem releváns",
};

/** Lara KÉRDÉSEI (kliens).
 *
 * Lara a háttérben összeveti, mit javasolt volna a rögzített munkára, és mi
 * lett a valóság. Ahol nem érti az eltérést, itt kérdez. A válasz azonnal
 * tudássá válik — ezzel tanítod folyamatosan. */
export function LaraKerdesek({
  nyitottak,
  megvalaszoltak,
  canEdit,
  nyomozas,
}: {
  nyitottak: LaraKerdes[];
  megvalaszoltak: LaraKerdes[];
  canEdit: boolean;
  nyomozas: LaraNyomozasStat | null;
}) {
  const router = useRouter();
  const [lista, setLista] = useState(nyitottak);
  const [kesz, setKesz] = useState(megvalaszoltak);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [szuro, setSzuro] = useState("mind");
  const lathato = szuro === "mind" ? lista : lista.filter((k) => terulet(k) === szuro);
  const szurok = [
    { kulcs: "mind", cim: "Mind", n: lista.length },
    ...TERULETEK.map((t) => ({ ...t, n: lista.filter((k) => terulet(k) === t.kulcs).length })).filter(
      (t) => t.n > 0 || t.kulcs === szuro,
    ),
  ];

  return (
    <div className="flex flex-col gap-4">
      {uzenet && <div className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>}

      {nyomozas && (
        <p className="text-[12px] text-text-muted">
          Mielőtt kérdez, Lara maga is utánanéz a rendszerben — ugyanazokkal a csak-olvasó eszközökkel és tudással, amivel
          az AI asszisztens dolgozik.{" "}
          {!nyomozas.elerheto ? (
            <span className="text-text-secondary">Beállítás szükséges: a szerveren nincs Gemini-kulcs.</span>
          ) : !nyomozas.bekapcsolva ? (
            <span className="text-text-secondary">
              Most ki van kapcsolva (
              <Link href="/admin-agent/beallitasok" className="text-text-accent hover:underline">
                Beállítások
              </Link>
              ).
            </span>
          ) : (
            <span className="text-text-secondary">
              Eddig <b className="tabular-nums">{nyomozas.nyomozott}</b> kérdésnél nézett utána, ebből{" "}
              <b className="tabular-nums">{nyomozas.valaszt_talalt}</b>-nál talált választ;{" "}
              <b className="tabular-nums">{nyomozas.elfogadva}</b> válaszát fogadtad el.
            </span>
          )}
        </p>
      )}

      {lista.length > 0 && (
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Terület szerinti szűrés">
          {szurok.map((s) => (
            <button
              key={s.kulcs}
              type="button"
              aria-pressed={szuro === s.kulcs}
              onClick={() => setSzuro(s.kulcs)}
              className={`rounded-full border px-3 py-1 text-[12.5px] ${
                szuro === s.kulcs
                  ? "border-text-accent bg-surface-3 text-text-primary"
                  : "border-border text-text-secondary hover:bg-surface-3"
              }`}
            >
              {s.cim} <span className="tabular-nums text-text-muted">{s.n}</span>
            </button>
          ))}
        </div>
      )}

      {lista.length === 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6">
          <p className="t-card mb-1">Most nincs kérdése Larának</p>
          <p className="text-[13px] text-text-secondary">
            Lara kétóránként (és a Tanulás oldalon kézzel indítva) teszteli magát: összeveti, mit javasolt volna a
            rögzített számlákra, a projektkódok papír- és számladöntéseire, a teljes Utókövetésre (megrendelői és belsős
            szerződés, TIG, bevétel), és mi lett a valóság. Közben a projektkódok egészén keresi, ami nem úgy van, ahogy
            várná, és a rendszer állapotait is próbálja megérteni. Ha valamit nem ért, itt kérdez.
          </p>
        </div>
      ) : (
        lathato.map((k) => (
          <KerdesKartya
            key={k.id}
            k={k}
            canEdit={canEdit}
            nyomozhat={!!nyomozas?.elerheto}
            onKesz={(uj, szoveg) => {
              setLista((p) => p.filter((x) => x.id !== uj.id));
              setKesz((p) => [uj, ...p]);
              setUzenet(szoveg);
              router.refresh();
            }}
          />
        ))
      )}

      {kesz.length > 0 && (
        <details className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
          <summary className="cursor-pointer text-[13px] font-medium text-text-primary">
            Megválaszolt kérdések ({kesz.length})
          </summary>
          <ul className="mt-3 flex flex-col gap-2">
            {kesz.map((k) => (
              <li key={k.id} className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2">
                <p className="text-[12.5px] text-text-primary">{k.kerdes}</p>
                <p className="mt-1 text-[12px] text-text-secondary">
                  <span className="font-medium">{VALASZ_CIMKE[k.valasz_tipus ?? ""] ?? k.valasz_tipus}</span>
                  {k.valasz_szoveg ? ` — „${k.valasz_szoveg}”` : ""}
                  {k.megvalaszolva_at ? ` · ${new Date(k.megvalaszolva_at).toLocaleDateString("hu-HU")}` : ""}
                </p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function KerdesKartya({
  k: kezdo,
  canEdit,
  nyomozhat,
  onKesz,
}: {
  k: LaraKerdes;
  canEdit: boolean;
  nyomozhat: boolean;
  onKesz: (k: LaraKerdes, uzenet: string) => void;
}) {
  const [k, setK] = useState(kezdo);
  const [nyomoz, setNyomoz] = useState(false);
  const ny = k.kontextus?.lara_nyomozas;
  const opciok = valaszOpciok(k);
  const [valasz, setValasz] = useState(opciok[0].ertek);
  const [szoveg, setSzoveg] = useState("");
  const [elesit, setElesit] = useState(true);
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);
  const esetek = k.kontextus?.esetek ?? [];
  const papir = k.tipus === "papir";
  const bov = bovitett(k);
  const fogalom = k.tipus === "rendszer_fogalom";

  async function utananez() {
    setHiba(null);
    setNyomoz(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/questions/${k.id}/investigate`, { method: "POST" });
      const d = (await res.json().catch(() => ({}))) as { detail?: unknown; kerdes?: LaraKerdes };
      if (!res.ok || !d.kerdes) {
        setHiba(typeof d.detail === "string" ? d.detail : "Az utánanézés nem sikerült.");
        return;
      }
      setK(d.kerdes);
    } finally {
      setNyomoz(false);
    }
  }

  async function kuld(tipus: string, lara?: LaraNyomozas) {
    setHiba(null);
    const szovegKuld = lara ? lara.valasz : szoveg.trim();
    if (!lara && (tipus === "magyarazat" || (fogalom && tipus !== "elvet")) && !szoveg.trim()) {
      setHiba(fogalom ? "Írd le röviden, mit jelent ez az állapot — ebből tanul Lara." : "Írd le röviden, miért így van — ebből tanul Lara.");
      return;
    }
    setFolyamatban(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/questions/${k.id}/answer`, {
        method: "POST",
        body: JSON.stringify({
          valasz_tipus: tipus,
          magyarazat: lara ? `Lara utánanézése alapján: ${szovegKuld}` : szovegKuld || null,
          elesit,
          lara_valasza: !!lara,
        }),
      });
      const d = (await res.json().catch(() => ({}))) as {
        detail?: unknown;
        kerdes?: LaraKerdes;
        szabaly_allapot?: string | null;
        feladat_id?: number | null;
      };
      if (!res.ok || !d.kerdes) {
        setHiba(typeof d.detail === "string" ? d.detail : "A válasz mentése nem sikerült.");
        return;
      }
      if (tipus === "hibas" && d.feladat_id) {
        // A javítási feladathoz Lara azonnal megoldási javaslatot is ír (a
        // háttérben — a válasz nem vár rá; a feladat oldalán megjelenik).
        if (nyomozhat) {
          void authFetch(`/api/v1/admin-agent/tasks/${d.feladat_id}/solution`, { method: "POST" }).catch(() => undefined);
        }
        onKesz(
          d.kerdes,
          `Rendben, ebből nem tanulok. Javítási feladatot készítettem (#${d.feladat_id}) megoldási lépésekkel` +
            (nyomozhat ? ", és most utánanézek a konkrét megoldásnak is" : "") +
            " — a Munkasorban találod.",
        );
        return;
      }
      const uzenet = bov
        ? bovitettUzenet(k, tipus, d.feladat_id ?? null)
        : tipus === "mindig"
          ? d.szabaly_allapot === "active"
            ? "Köszönöm! Megtanultam szabályként — mostantól így javaslom."
            : "Köszönöm! Szabály-jelöltként a Tudástárba került; élesíteni sikeres értékelés után, jogosultsággal lehet."
          : tipus === "magyarazat"
            ? "Köszönöm a magyarázatot — bekerült a tudásomba, a hasonló eseteknél ebből dolgozom."
            : tipus === "kivetel"
              ? "Rendben, feljegyeztem egyszeri kivételként — nem általánosítok belőle."
              : tipus === "hibas"
                ? k.tipus === "papir"
                  ? "Rendben, ebből nem tanulok. Ha kell, az Utókövetés oldalon javítsd."
                  : "Rendben, ebből nem tanulok. A rögzítést a Beérkező számlák oldalon javítsd."
                : "A kérdést lezártam.";
      onKesz(d.kerdes, uzenet);
    } finally {
      setFolyamatban(false);
    }
  }

  return (
    <article className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <p className="mb-1 flex flex-wrap items-center gap-x-1.5 text-[11.5px] uppercase tracking-[0.08em] text-text-muted">
        <span className="rounded-full border border-border px-2 py-px normal-case tracking-normal text-text-secondary">
          {bov && k.kontextus?.cimke ? k.kontextus.cimke : TERULET_EGYES[terulet(k)]}
          {papir && k.kontextus?.dimenzio ? ` · ${DIMENZIO[k.kontextus.dimenzio] ?? k.kontextus.dimenzio}` : ""}
        </span>
        Lara kérdése · {k.partner_nev}
        {k.letrehozva ? ` · ${new Date(k.letrehozva).toLocaleDateString("hu-HU")}` : ""}
      </p>
      <p className="mb-3 text-[15px] leading-snug text-text-primary">{k.kerdes}</p>

      {papir && esetek.length > 0 && (
        <div className="mb-4 overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                <th className="px-2.5 py-1.5 font-medium">{TERULET_EGYES[terulet(k)]}</th>
                <th className="px-2.5 py-1.5 font-medium">Nettó</th>
                <th className="px-2.5 py-1.5 font-medium">Lezárva</th>
                <th className="px-2.5 py-1.5 font-medium">Lara ezt várta</th>
                <th className="px-2.5 py-1.5 font-medium">Ahogy döntöttetek</th>
              </tr>
            </thead>
            <tbody>
              {esetek.map((e) => (
                <tr key={e.rekord ?? e.rekord_id} className="border-b border-border last:border-0">
                  <td className="px-2.5 py-1.5 text-text-primary">
                    {e.projektkod ?? "—"}
                    {e.projekt && <span className="block text-[11px] text-text-muted">{e.projekt}</span>}
                  </td>
                  <td className="px-2.5 py-1.5 tabular-nums text-text-secondary">{e.netto ?? "—"}</td>
                  <td className="px-2.5 py-1.5 text-text-secondary">{e.datum ?? "—"}</td>
                  <td className="px-2.5 py-1.5 text-text-secondary">
                    {e.lara_szoveg ?? "—"}
                    {e.lara_alap && <span className="block text-[11px] text-text-muted">{e.lara_alap}</span>}
                  </td>
                  <td className="px-2.5 py-1.5 text-text-primary">{e.valosag_szoveg ?? k.kontextus?.valosag?.szoveg}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {bov && esetek.length > 0 && (
        <div className="mb-4 overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                <th className="px-2.5 py-1.5 font-medium">Projektkód / tétel</th>
                <th className="px-2.5 py-1.5 font-medium">Nettó</th>
                <th className="px-2.5 py-1.5 font-medium">Dátum</th>
                {k.tipus === "admin_dontes" && <th className="px-2.5 py-1.5 font-medium">Lara ezt várta</th>}
                <th className="px-2.5 py-1.5 font-medium">{k.tipus === "admin_dontes" ? "Ahogy lett" : "Amit Lara lát"}</th>
              </tr>
            </thead>
            <tbody>
              {esetek.map((e) => (
                <tr key={e.rekord} className="border-b border-border last:border-0">
                  <td className="px-2.5 py-1.5 text-text-primary">
                    {e.projektkod ?? e.rekord ?? "—"}
                    {e.projekt && <span className="block text-[11px] text-text-muted">{e.projekt}</span>}
                  </td>
                  <td className="px-2.5 py-1.5 tabular-nums text-text-secondary">{e.netto ?? "—"}</td>
                  <td className="px-2.5 py-1.5 text-text-secondary">{e.datum ?? "—"}</td>
                  {k.tipus === "admin_dontes" && (
                    <td className="px-2.5 py-1.5 text-text-secondary">
                      {e.lara_szoveg ?? "—"}
                      {e.lara_alap && <span className="block text-[11px] text-text-muted">{e.lara_alap}</span>}
                    </td>
                  )}
                  <td className="px-2.5 py-1.5 text-text-primary">{e.valosag_szoveg ?? k.kontextus?.valosag?.szoveg}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!papir && !bov && esetek.length > 0 && (
        <div className="mb-4 overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                <th className="px-2.5 py-1.5 font-medium">Számla</th>
                <th className="px-2.5 py-1.5 font-medium">Nettó</th>
                <th className="px-2.5 py-1.5 font-medium">Rögzítve</th>
                <th className="px-2.5 py-1.5 font-medium">Lara javaslata</th>
                <th className="px-2.5 py-1.5 font-medium">Ahogy rögzítettétek</th>
              </tr>
            </thead>
            <tbody>
              {esetek.map((e) => (
                <tr key={e.bejovo_id ?? e.szamlaszam} className="border-b border-border last:border-0">
                  <td className="px-2.5 py-1.5 text-text-primary">{e.szamlaszam ?? `#${e.bejovo_id}`}</td>
                  <td className="px-2.5 py-1.5 tabular-nums text-text-secondary">{e.netto ?? "—"}</td>
                  <td className="px-2.5 py-1.5 text-text-secondary">{e.datum ?? "—"}</td>
                  <td className="px-2.5 py-1.5 text-text-secondary">
                    {e.lara_szoveg ?? <span className="text-text-muted">nem tudott javasolni</span>}
                    {e.lara_alap && <span className="block text-[11px] text-text-muted">{e.lara_alap}</span>}
                  </td>
                  <td className="px-2.5 py-1.5 text-text-primary">{e.vegso_szoveg ?? k.kontextus?.valosag?.szoveg}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {ny ? (
        <NyomozasPanel
          ny={ny}
          canEdit={canEdit}
          folyamatban={folyamatban || nyomoz}
          onElfogad={() => kuld(fogalom ? "magyarazat" : ny.javaslat, ny)}
          onUjra={nyomozhat && canEdit ? utananez : undefined}
          nyomoz={nyomoz}
        />
      ) : (
        nyomozhat &&
        canEdit && (
          <div className="mb-4 flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-dashed border-border px-3 py-2.5">
            <span className="text-[12.5px] text-text-secondary">
              Lara még nem nézett utána ennek a kérdésnek a rendszerben.
            </span>
            <button
              type="button"
              disabled={nyomoz || folyamatban}
              onClick={utananez}
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-primary hover:bg-surface-3 disabled:opacity-50"
            >
              {nyomoz ? "Lara utánanéz a rendszerben… (akár egy perc)" : "Nézz utána most"}
            </button>
          </div>
        )
      )}

      {!canEdit ? (
        <p className="text-[12px] text-text-muted">A válaszhoz szerkesztési jogosultság szükséges.</p>
      ) : (
        <div>
          {hiba && <div className="mb-2 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[12.5px] text-text-danger">{hiba}</div>}
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2" role="radiogroup" aria-label="Válasz Larának">
            {opciok.map((v) => (
              <label
                key={v.ertek}
                className={`flex cursor-pointer gap-2.5 rounded-[var(--radius)] border px-3 py-2.5 ${
                  valasz === v.ertek ? "border-text-accent bg-surface-3" : "border-border hover:bg-surface-3"
                }`}
              >
                <input
                  type="radio"
                  name={`valasz-${k.id}`}
                  value={v.ertek}
                  checked={valasz === v.ertek}
                  onChange={() => setValasz(v.ertek)}
                  className="mt-0.5"
                />
                <span>
                  <span className="block text-[13px] font-medium text-text-primary">{v.cim}</span>
                  <span className="block text-[12px] text-text-muted">{v.leiras}</span>
                </span>
              </label>
            ))}
          </div>
          <textarea
            rows={2}
            value={szoveg}
            onChange={(e) => setSzoveg(e.target.value)}
            placeholder={
              fogalom
                ? "Mit jelent ez az állapot? (kötelező) — pl. „Az ügyfél javítást kért; ilyenkor még nem megy ki a TIG.”"
                : valasz === "magyarazat"
                ? papir
                  ? "Miért így van? (kötelező) — pl. „Havidíjas partner, a keretszerződése lefedi, eseti papír nem kell.”"
                  : "Miért így van? (kötelező) — pl. „Ő a forgatásokon a gaffer, a számlája mindig a forgatás projektkódjára megy.”"
                : "Magyarázat (opcionális, de segít Larának)"
            }
            className="mt-2 w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted"
          />
          {valasz === "mindig" && !bov && (
            <label className="mt-1 flex items-center gap-2 text-[12px] text-text-secondary">
              <input type="checkbox" checked={elesit} onChange={(e) => setElesit(e.target.checked)} />
              Szabályként azonnal élesítem (élesítési jog és sikeres értékelés kell hozzá — különben jelölt lesz)
            </label>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={folyamatban}
              onClick={() => kuld(valasz)}
              className="rounded-[var(--radius)] bg-bg-accent px-3.5 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
            >
              {folyamatban ? "Mentés…" : "Válasz elküldése Larának"}
            </button>
            <button
              type="button"
              disabled={folyamatban}
              onClick={() => kuld("elvet")}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
            >
              Nem releváns
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

function bovitettUzenet(k: LaraKerdes, tipus: string, feladatId: number | null): string {
  if (tipus === "elvet") return "A kérdést lezártam.";
  if (k.tipus === "rendszer_fogalom") return "Köszönöm — megértettem, bekerült a rendszer-tudásomba.";
  if (tipus === "hibas")
    return feladatId
      ? `Rendben, ebből nem tanulok. Javítási feladatot készítettem (#${feladatId}) — a Munkasorban találod.`
      : "Rendben, ebből nem tanulok.";
  if (tipus === "kivetel") return "Rendben, feljegyeztem egyszeri kivételként — nem általánosítok belőle.";
  if (tipus === "magyarazat") return "Köszönöm a magyarázatot — bekerült a tudásomba, a hasonló eseteknél ebből dolgozom.";
  return k.tipus === "rendszer_elteres"
    ? "Köszönöm! Megjegyeztem, hogy nála ez így szokás — erre többé nem kérdezek rá."
    : "Köszönöm! Megtanultam — ennél a partnernél a következő esetektől ezt várom.";
}

const JAVASLAT_CIMKE: Record<string, string> = {
  mindig: "Így helyes, ez a bevett gyakorlat",
  magyarazat: "Van rá konkrét magyarázat",
  kivetel: "Egyszeri kivétel",
  hibas: "Rögzítési hiba — javítani kell",
  nem_tudom: "Nem talált elég bizonyítékot",
};

/** Lara utánanézésének eredménye a kérdés kártyáján: mit talált, milyen
 * bizonyítékok alapján, és hol nézett utána. Egy kattintással elfogadható —
 * a kérdést így is ember zárja le. */
function NyomozasPanel({
  ny,
  canEdit,
  folyamatban,
  onElfogad,
  onUjra,
  nyomoz,
}: {
  ny: LaraNyomozas;
  canEdit: boolean;
  folyamatban: boolean;
  onElfogad: () => void;
  onUjra?: () => void;
  nyomoz: boolean;
}) {
  const talalt = ny.javaslat !== "nem_tudom" && !!ny.valasz;
  return (
    <div
      className={`mb-4 rounded-[var(--radius)] border px-3.5 py-3 ${
        talalt ? "border-text-accent/40 bg-surface-3" : "border-border bg-surface-3"
      }`}
    >
      <p className="mb-1.5 flex flex-wrap items-center gap-x-2 text-[11.5px] uppercase tracking-[0.08em] text-text-muted">
        Lara utánanézett
        <span className="normal-case tracking-normal">
          · {new Date(ny.ido).toLocaleString("hu-HU", { dateStyle: "short", timeStyle: "short" })}
        </span>
        <span className="rounded-full border border-border px-2 py-px normal-case tracking-normal text-text-secondary">
          {JAVASLAT_CIMKE[ny.javaslat] ?? ny.javaslat}
          {talalt ? ` · ${Math.round(ny.biztossag * 100)}% biztos` : ""}
        </span>
      </p>
      {ny.valasz ? (
        <p className="text-[13.5px] leading-snug text-text-primary">{ny.valasz}</p>
      ) : (
        <p className="text-[13px] text-text-secondary">
          {ny.allapot === "hiba"
            ? "Az utánanézés most nem sikerült (a modell nem volt elérhető)."
            : "Nem talált a rendszerben magyarázatot."}
        </p>
      )}
      {ny.bizonyitekok.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {ny.bizonyitekok.map((b, i) => (
            <li key={i} className="text-[12.5px] text-text-secondary">
              ·{" "}
              {b.link ? (
                <Link href={b.link} className="text-text-accent hover:underline">
                  {b.leiras}
                </Link>
              ) : (
                b.leiras
              )}
            </li>
          ))}
        </ul>
      )}
      {ny.lepesek.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-[12px] text-text-muted">
            Hol nézett utána ({ny.lepesek.length} lépés)
          </summary>
          <ul className="mt-1.5 flex flex-col gap-0.5">
            {ny.lepesek.map((l, i) => (
              <li key={i} className={`font-mono text-[11.5px] ${l.ok ? "text-text-secondary" : "text-text-danger"}`}>
                {l.cel}
              </li>
            ))}
          </ul>
        </details>
      )}
      {canEdit && (
        <div className="mt-3 flex flex-wrap gap-2">
          {talalt && (
            <button
              type="button"
              disabled={folyamatban}
              onClick={onElfogad}
              className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
            >
              Elfogadom Lara válaszát
            </button>
          )}
          {onUjra && (
            <button
              type="button"
              disabled={folyamatban}
              onClick={onUjra}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
            >
              {nyomoz ? "Lara utánanéz… (akár egy perc)" : "Nézz utána újra"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
