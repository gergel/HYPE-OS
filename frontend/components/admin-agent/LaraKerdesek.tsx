"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { LaraKerdes } from "@/lib/api";

const VALASZOK: { ertek: string; cim: string; leiras: string }[] = [
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
    leiras: "Nem tanul belőle. A rögzítést javítsd (Beérkező számlák, illetve Utókövetés).",
  },
];

const TERULETEK: { kulcs: string; cim: string }[] = [
  { kulcs: "szamla", cim: "Számlák" },
  { kulcs: "szerzodes", cim: "Szerződések" },
  { kulcs: "tig", cim: "TIG-ek" },
];
const TERULET_EGYES: Record<string, string> = { szamla: "Számla", szerzodes: "Szerződés", tig: "TIG" };
const DIMENZIO: Record<string, string> = {
  kihagyas: "kell-e a papír",
  osszeg: "nettó összeg",
  afa: "+ÁFA",
  targy: "megbízás tárgya",
  szamla_kihagyas: "kell-e számla",
};

function terulet(k: LaraKerdes): string {
  return k.tipus === "papir" ? (k.kontextus?.terulet ?? "szerzodes") : "szamla";
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
}: {
  nyitottak: LaraKerdes[];
  megvalaszoltak: LaraKerdes[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [lista, setLista] = useState(nyitottak);
  const [kesz, setKesz] = useState(megvalaszoltak);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [szuro, setSzuro] = useState("mind");
  const lathato = szuro === "mind" ? lista : lista.filter((k) => terulet(k) === szuro);
  const szurok = [
    { kulcs: "mind", cim: "Mind", n: lista.length },
    ...TERULETEK.map((t) => ({ ...t, n: lista.filter((k) => terulet(k) === t.kulcs).length })),
  ];

  return (
    <div className="flex flex-col gap-4">
      {uzenet && <div className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>}

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
            Lara kétóránként (és a Tanulás oldalon kézzel indítva) összeveti, mit javasolt volna a rögzített számlákra
            és az Utókövetés lezárt szerződés- és TIG-döntéseire, és mi lett a valóság. Ha valamit nem ért, itt kérdez.
          </p>
        </div>
      ) : (
        lathato.map((k) => (
          <KerdesKartya
            key={k.id}
            k={k}
            canEdit={canEdit}
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
  k,
  canEdit,
  onKesz,
}: {
  k: LaraKerdes;
  canEdit: boolean;
  onKesz: (k: LaraKerdes, uzenet: string) => void;
}) {
  const [valasz, setValasz] = useState("mindig");
  const [szoveg, setSzoveg] = useState("");
  const [elesit, setElesit] = useState(true);
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);
  const esetek = k.kontextus?.esetek ?? [];
  const papir = k.tipus === "papir";

  async function kuld(tipus: string) {
    setHiba(null);
    if (tipus === "magyarazat" && !szoveg.trim()) {
      setHiba("Írd le röviden, miért így van — ebből tanul Lara.");
      return;
    }
    setFolyamatban(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/questions/${k.id}/answer`, {
        method: "POST",
        body: JSON.stringify({ valasz_tipus: tipus, magyarazat: szoveg.trim() || null, elesit }),
      });
      const d = (await res.json().catch(() => ({}))) as {
        detail?: unknown;
        kerdes?: LaraKerdes;
        szabaly_allapot?: string | null;
      };
      if (!res.ok || !d.kerdes) {
        setHiba(typeof d.detail === "string" ? d.detail : "A válasz mentése nem sikerült.");
        return;
      }
      const uzenet =
        tipus === "mindig"
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
          {TERULET_EGYES[terulet(k)]}
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

      {!papir && esetek.length > 0 && (
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

      {!canEdit ? (
        <p className="text-[12px] text-text-muted">A válaszhoz szerkesztési jogosultság szükséges.</p>
      ) : (
        <div>
          {hiba && <div className="mb-2 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[12.5px] text-text-danger">{hiba}</div>}
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2" role="radiogroup" aria-label="Válasz Larának">
            {VALASZOK.map((v) => (
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
              valasz === "magyarazat"
                ? papir
                  ? "Miért így van? (kötelező) — pl. „Havidíjas partner, a keretszerződése lefedi, eseti papír nem kell.”"
                  : "Miért így van? (kötelező) — pl. „Ő a forgatásokon a gaffer, a számlája mindig a forgatás projektkódjára megy.”"
                : "Magyarázat (opcionális, de segít Larának)"
            }
            className="mt-2 w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted"
          />
          {valasz === "mindig" && (
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
