"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Download, ExternalLink, Inbox, RefreshCw } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { formatSzam } from "@/lib/penz";
import { huDatum } from "@/lib/huDate";
import { KeresosSelect } from "@/components/KeresosSelect";
import { StatusBadge } from "@/components/StatusBadge";
import type { BejovoSzamla, BejovoSzamlaReszlet } from "@/lib/api";

/** Állapot → felirat + szín. A feldolgozás, az ellenőrzés/jóváhagyás és a
 * kifizetés KÜLÖN állapotok: egy jóváhagyott számla ettől még nem kifizetett
 * (a kiadás nyitottként születik). */
const ALLAPOTOK: Record<string, { cimke: string; tone: "success" | "warning" | "danger" | "neutral" | "blue" }> = {
  feldolgozas: { cimke: "Feldolgozás alatt", tone: "blue" },
  ellenorzendo: { cimke: "Ellenőrizendő", tone: "warning" },
  pontositas: { cimke: "Pontosítás szükséges", tone: "warning" },
  jovahagyva: { cimke: "Rögzítve", tone: "success" },
  duplikatum: { cimke: "Duplikátum", tone: "neutral" },
  nem_szamla: { cimke: "Nem számla / elutasítva", tone: "neutral" },
  egyeb_dokumentum: { cimke: "Nem számla jellegű melléklet", tone: "neutral" },
  hiba: { cimke: "Feldolgozási hiba", tone: "danger" },
};

/** A besorolási javaslat MEGALAPOZOTTSÁGA (a felhasználó kérése): a lista és
 * az ellenőrző ebből mutatja, mennyire lehet megbízni a javaslatban. */
const EROSSEG: Record<string, { cimke: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  biztos: { cimke: "Biztos javaslat", tone: "success" },
  tobb_lehetseges: { cimke: "Több lehetséges cél", tone: "warning" },
  ellentmondo: { cimke: "Ellentmondó jelek", tone: "danger" },
  keves_info: { cimke: "Kevés információ", tone: "neutral" },
};

/** A NÉZETEK: a napi munkát a teendők vezetik, a technikai állapot a
 * badge-eken marad (a felhasználó kérése). */
const NEZETEK: { kulcs: string; cimke: string; allapotok: string[] | null }[] = [
  { kulcs: "ellenorzes", cimke: "Ellenőrzésre vár", allapotok: ["ellenorzendo"] },
  { kulcs: "elakadt", cimke: "Elakadt", allapotok: ["pontositas", "hiba", "feldolgozas"] },
  { kulcs: "rogzitett", cimke: "Rögzített", allapotok: ["jovahagyva"] },
  { kulcs: "felretett", cimke: "Félretett", allapotok: ["duplikatum", "nem_szamla", "egyeb_dokumentum"] },
  { kulcs: "mind", cimke: "Mind", allapotok: null },
];

const CEL_CIMKEK: Record<string, string> = {
  kiadas_uj: "Új kiadás (projekthez)",
  kiadas_csatolas: "Számla meglévő kiadáshoz",
  kulsos_tig: "Meglévő külsős TIG számlája",
  belsos_tig: "Meglévő belsős TIG számlája",
  erezsi: "E-Rezsi előfizetés számlája",
  auto: "Autó költsége (új kiadás)",
  kp: "KP-tétel bizonylat-pótlása",
  mukodesi: "Általános működési költség (tudatosan projekt nélkül)",
  kimeno: "Kimenő számla (megrendelői folyamat)",
  bontas: "Bontás több cél között (több projekt egy számlán)",
  egyeb: "Tisztázandó / egyéb",
};

/** A bontás-sorokban választható célok (lásd backend BONTAS_CEL_TIPUSOK). */
const BONTAS_CELOK: { kulcs: string; cimke: string }[] = [
  { kulcs: "kiadas_uj", cimke: "Új kiadás projekthez" },
  { kulcs: "mukodesi", cimke: "Működési (projekt nélkül)" },
  { kulcs: "kulsos_tig", cimke: "Meglévő külsős TIG" },
  { kulcs: "kiadas_csatolas", cimke: "Meglévő kiadás" },
];

//: Melyik cél-típus hoz létre ÚJ kiadást, és melyik csatol MEGLÉVŐHÖZ.
const UJ_KOLTSEG = new Set(["kiadas_uj", "mukodesi", "auto"]);
const CSATOLOS = new Set(["kiadas_csatolas", "kulsos_tig", "belsos_tig", "erezsi", "kp"]);

//: A cél-típushoz tartozó rekord-mező és a kereshető választék-forrás.
const CEL_MEZO: Record<string, { mezo: string; valasztek: string | null; cimke: string }> = {
  kiadas_csatolas: { mezo: "cel_expense_id", valasztek: "kiadas_csatolas", cimke: "Melyik kiadáshoz" },
  kulsos_tig: { mezo: "cel_certificate_id", valasztek: "kulsos_tig", cimke: "Melyik külsős TIG-hez" },
  belsos_tig: { mezo: "cel_internal_certificate_id", valasztek: "belsos_tig", cimke: "Melyik belsős TIG-hez" },
  erezsi: { mezo: "cel_kotelezettseg_idoszak_id", valasztek: "erezsi", cimke: "Melyik előfizetés-időszakhoz" },
  kp: { mezo: "cel_kp_forgalom_id", valasztek: "kp", cimke: "Melyik KP-tételhez" },
};

type Valasztek = { projektkodok: { id: number; kod: string }[]; emberek: { id: number; nev: string }[]; autok: { id: number; nev: string }[] };

function bruttoSzoveg(b: BejovoSzamla): string {
  if (b.brutto != null) return `${formatSzam(b.brutto)} ${b.penznem}`;
  if (b.netto != null) return `${formatSzam(b.netto)} ${b.penznem} (nettó)`;
  return "–";
}

function kovetkezoTeendo(b: BejovoSzamla): string {
  if (b.allapot === "ellenorzendo") return "Ellenőrizd és hagyd jóvá";
  if (b.allapot === "pontositas") return b.fajl_nev ? "Válassz célt / pontosíts" : "Töltsd fel a letöltött számlát";
  if (b.allapot === "hiba") return "Nézd meg a hibát, próbáld újra";
  if (b.allapot === "feldolgozas") return "Feldolgozás alatt";
  if (b.allapot === "jovahagyva") return "Kész";
  return "–";
}

export function BejovoSzamlak({
  kezdoLista,
  valasztek,
  canEdit,
  canCreate,
  canDelete,
}: {
  kezdoLista: BejovoSzamla[];
  valasztek: Valasztek;
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [lista, setLista] = useState(kezdoLista);
  const [nezet, setNezet] = useState("ellenorzes");
  const [kereses, setKereses] = useState("");
  const [rendezes, setRendezes] = useState<"beerkezes" | "osszeg" | "hatarido">("beerkezes");
  const [nyitottId, setNyitottId] = useState<number | null>(null);
  useEffect(() => setLista(kezdoLista), [kezdoLista]);
  // Törlés/lehúzás/reset után a listát KÖZVETLENÜL a szerverről töltjük újra -
  // nem csak a router.refresh()-re bízzuk, hogy a képernyő biztosan a valós
  // állapotot mutassa.
  const frissit = useCallback(async () => {
    try {
      const r = await authFetch("/api/v1/bejovo-szamlak");
      if (r.ok) setLista(await r.json());
    } catch {
      // a router.refresh() lentebb így is megpróbálja
    }
    router.refresh();
  }, [router]);
  useEffect(() => {
    const id = searchParams.get("id");
    if (id) setNyitottId(Number(id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const darabok = useMemo(() => {
    const t: Record<string, number> = {};
    for (const n of NEZETEK) {
      t[n.kulcs] = n.allapotok === null ? lista.length : lista.filter((b) => n.allapotok!.includes(b.allapot)).length;
    }
    return t;
  }, [lista]);

  const szurt = useMemo(() => {
    const aktiv = NEZETEK.find((n) => n.kulcs === nezet);
    let t = aktiv?.allapotok === null || !aktiv ? [...lista] : lista.filter((b) => aktiv.allapotok!.includes(b.allapot));
    const k = kereses.trim().toLowerCase();
    if (k) {
      t = t.filter((b) =>
        [b.kibocsato_nev, b.szamlaszam, b.email_targy, b.email_felado, b.cel_cimke, b.fajl_nev]
          .filter(Boolean)
          .some((x) => String(x).toLowerCase().includes(k)),
      );
    }
    t.sort((a, b) => {
      if (rendezes === "osszeg") return (b.brutto ?? b.netto ?? 0) - (a.brutto ?? a.netto ?? 0);
      if (rendezes === "hatarido") return (a.fizetesi_hatarido ?? "9999").localeCompare(b.fizetesi_hatarido ?? "9999");
      return (b.email_beerkezes ?? b.created_at).localeCompare(a.email_beerkezes ?? a.created_at);
    });
    return t;
  }, [lista, nezet, kereses, rendezes]);

  return (
    <div className="space-y-4">
      <EmailSav canEdit={canEdit} canDelete={canDelete} onFrissul={() => void frissit()} />

      <div className="flex flex-wrap items-center gap-1.5">
        {NEZETEK.map((n) => (
          <button
            key={n.kulcs}
            type="button"
            onClick={() => setNezet(n.kulcs)}
            className={`rounded-[var(--radius)] px-2.5 py-1 text-[12.5px] ${nezet === n.kulcs ? "bg-bg-accent text-text-accent" : "border border-border text-text-secondary hover:bg-surface-3"}`}
          >
            {n.cimke} ({darabok[n.kulcs] ?? 0})
          </button>
        ))}
        <input
          value={kereses}
          onChange={(e) => setKereses(e.target.value)}
          placeholder="Keresés (kibocsátó, számlaszám, tárgy)…"
          className="ml-auto w-[220px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none"
        />
        <select
          value={rendezes}
          onChange={(e) => setRendezes(e.target.value as typeof rendezes)}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-secondary focus:outline-none"
        >
          <option value="beerkezes">Beérkezés szerint</option>
          <option value="osszeg">Összeg szerint</option>
          <option value="hatarido">Határidő szerint</option>
        </select>
      </div>

      {szurt.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-text-secondary">
          <Inbox size={16} className="mr-1 inline" />
          Nincs tétel ebben a nézetben. A szamla@ címre érkező levelek automatikusan bejönnek a háttérben (és az
          „Ellenőrzés most" gombbal azonnal) - az AI Assistantba is bedobhatsz számlát.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b border-border text-left text-text-secondary">
                <th className="py-1.5 pr-3 font-medium">Kibocsátó / számlaszám</th>
                <th className="py-1.5 pr-3 text-right font-medium">Bruttó</th>
                <th className="py-1.5 pr-3 font-medium">Projekt / cél</th>
                <th className="py-1.5 pr-3 font-medium">Művelet</th>
                <th className="py-1.5 pr-3 font-medium">Következő teendő</th>
                <th className="py-1.5 pr-3 font-medium">Beérkezés</th>
                <th className="py-1.5 font-medium" />
              </tr>
            </thead>
            <tbody>
              {szurt.map((b) => (
                <tr key={b.id} className="border-b border-border last:border-0 hover:bg-surface-3">
                  <td className="py-2 pr-3">
                    <span className="text-text-primary">{b.kibocsato_nev ?? b.fajl_nev ?? b.email_targy ?? "(ismeretlen)"}</span>
                    <span className="block text-[11px] text-text-muted">
                      {b.szamlaszam ?? "számlaszám nélkül"} · {b.forras === "email" ? "e-mail" : b.forras === "asszisztens" ? "asszisztens" : "kézi"}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums text-text-primary">{bruttoSzoveg(b)}</td>
                  <td className="max-w-[240px] truncate py-2 pr-3 text-text-secondary" title={b.cel_cimke ?? undefined}>
                    {b.cel_cimke ?? (b.cel_tipus ? CEL_CIMKEK[b.cel_tipus] : "még nincs cél")}
                  </td>
                  <td className="py-2 pr-3">
                    {b.cel_tipus ? (
                      <StatusBadge
                        label={UJ_KOLTSEG.has(b.cel_tipus) ? "Új kiadás" : CSATOLOS.has(b.cel_tipus) ? "Csatolás meglévőhöz" : "Egyéb"}
                        tone={UJ_KOLTSEG.has(b.cel_tipus) ? "orange" : "teal"}
                      />
                    ) : (
                      <span className="text-text-muted">–</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-text-secondary">
                    <span className="flex items-center gap-1.5">
                      <StatusBadge label={ALLAPOTOK[b.allapot]?.cimke ?? b.allapot} tone={ALLAPOTOK[b.allapot]?.tone ?? "neutral"} />
                      {b.javaslat_erosseg && ["ellenorzendo", "pontositas"].includes(b.allapot) && EROSSEG[b.javaslat_erosseg] && (
                        <StatusBadge label={EROSSEG[b.javaslat_erosseg].cimke} tone={EROSSEG[b.javaslat_erosseg].tone} />
                      )}
                      {b.allapot !== "jovahagyva" && <span className="hidden text-[11.5px] xl:inline">{kovetkezoTeendo(b)}</span>}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-text-secondary">{huDatum((b.email_beerkezes ?? b.created_at).slice(0, 10))}</td>
                  <td className="py-2 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        type="button"
                        title="Lara árnyék-elemzés indítása erre a számlára (nem hajt végre semmit)"
                        onClick={async () => {
                          const res = await authFetch(`/api/v1/admin-agent/tasks/from-bejovo/${b.id}`, { method: "POST" });
                          if (res.ok) {
                            const t = (await res.json()) as { id: number };
                            router.push(`/admin-agent/munkasor/${t.id}`);
                          }
                        }}
                        className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3"
                      >
                        Lara
                      </button>
                      <button
                        type="button"
                        onClick={() => setNyitottId(b.id)}
                        className="rounded-[var(--radius)] border border-border bg-bg-accent px-2.5 py-1 text-[12px] text-text-accent hover:opacity-90"
                      >
                        Megnyitás
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {nyitottId !== null && (
        <Reszletes
          bejovoId={nyitottId}
          valasztek={valasztek}
          canEdit={canEdit}
          canCreate={canCreate}
          canDelete={canDelete}
          onZaras={() => {
            setNyitottId(null);
            void frissit();
          }}
        />
      )}
    </div>
  );
}

/** Az e-mailes bekötés sávja. A háttérben AUTOMATIKUS érkeztetés fut
 * (konfigurálható gyakorisággal, az olvasottság nem számít - lásd backend
 * services/szamla_email_lehuzas.py); itt az állapota látszik, plusz a kézi
 * „Ellenőrzés most" és a dátumtartományos visszatöltés. */
function EmailSav({ canEdit, canDelete, onFrissul }: { canEdit: boolean; canDelete: boolean; onFrissul: () => void }) {
  const [adat, setAdat] = useState<{
    cel_cim: string;
    legkorabbi_nap?: string;
    auto_gyakorisag_perc?: number;
    utolso_futas?: string | null;
    lehuzas_fut?: boolean;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [elonezet, setElonezet] = useState<{ felado: string; targy: string; csatolmanyok: string[] }[] | null>(null);
  const [visszatoltes, setVisszatoltes] = useState(false);
  const [kezdoDatum, setKezdoDatum] = useState("");
  const [vegDatum, setVegDatum] = useState("");
  //: A veszélyes műveletek beépített (nem böngésző-dialógusos) megerősítése -
  //: a confirm()/prompt() némítható a böngészőben, és akkor a gomb
  //: látszólag nem csinál semmit.
  const [megerosites, setMegerosites] = useState<null | "osszes" | "reset">(null);
  const [resetSzo, setResetSzo] = useState("");

  useEffect(() => {
    authFetch("/api/v1/bejovo-szamlak/email-allapot")
      .then((r) => (r.ok ? r.json() : null))
      .then(setAdat)
      .catch(() => setAdat(null));
  }, []);

  async function lehuzas(csakElonezet: boolean) {
    setBusy(true);
    setUzenet(null);
    setElonezet(null);
    try {
      const body: Record<string, unknown> = { limit: 100, elonezet: csakElonezet };
      if (visszatoltes && kezdoDatum) body.kezdo_datum = kezdoDatum;
      if (visszatoltes && vegDatum) body.veg_datum = vegDatum;
      const res = await authFetch("/api/v1/bejovo-szamlak/email-lehuzas", {
        method: "POST",
        body: JSON.stringify(body),
      });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        setUzenet(`Sikertelen: ${d?.detail ?? res.status}`);
        return;
      }
      if (csakElonezet) {
        setElonezet(d.elonezet ?? []);
        setUzenet(`${d.talalt_level} levél a keresésben - lent az előnézet (semmi nem jött létre, a postafiókhoz nem nyúltunk).`);
      } else {
        setUzenet(
          `${d.talalt_level} levelet vizsgáltunk: ${d.uj_level} levélből ${d.uj_szamla} új tétel készült` +
            `${d.ujra_behozott ? ` (ebből ${d.ujra_behozott} újra behozott: törölt tételű, még olvasatlan levél)` : ""}` +
            `${d.kihagyott_korabbi ? `, ${d.kihagyott_korabbi} korábban már átvett/kizárt levél kimaradt` : ""}` +
            `${d.hibas_level ? `, ${d.hibas_level} levél hibára futott (lásd a listát)` : ""}.`,
        );
        onFrissul();
      }
    } catch (err) {
      setUzenet(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    setUzenet(null);
    setMegerosites(null);
    try {
      const res = await authFetch("/api/v1/bejovo-szamlak/reset", {
        method: "POST",
        body: JSON.stringify({ megerosites: resetSzo }),
      });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        setUzenet(`Sikertelen: ${d?.detail ?? res.status}`);
        return;
      }
      const o = d.osszefoglalo;
      setUzenet(
        `Tiszta újraindítás kész: ${o.torolt_piszkozat} piszkozat törölve, ${o.visszavont_kiadas} import-kiadás visszavonva, ` +
          `${o.eltavolitott_kapcsolat} kapcsolat eltávolítva, ${o.visszaallitott_mezo} mező visszaállítva, ` +
          `${o.rendezendo_kivetel} rendezendő kivétel. A jegyzék mentve${d.jegyzek_tarhely_kulcs ? ` (${d.jegyzek_tarhely_kulcs})` : ""}.` +
          (d.kivetelek?.length ? ` Kivételek: ${d.kivetelek.map((k: { tipus: string; id: number; ok: string }) => `${k.tipus} #${k.id} (${k.ok})`).join("; ")}` : ""),
      );
      onFrissul();
    } catch (err) {
      setUzenet(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function osszesTorles() {
    setBusy(true);
    setUzenet(null);
    setMegerosites(null);
    try {
      const res = await authFetch("/api/v1/bejovo-szamlak/osszes-torles", { method: "POST" });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        setUzenet(`Sikertelen: ${d?.detail ?? res.status}`);
        return;
      }
      setUzenet(`${d.torolt} tétel törölve - a lista üres.`);
      onFrissul();
    } catch (err) {
      setUzenet(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[12.5px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-text-secondary">
          Bejövő cím: <b className="text-text-primary">{adat?.cel_cim ?? "…"}</b>
          <span className="ml-2 text-text-muted">
            {adat?.auto_gyakorisag_perc
              ? `· automatikus ellenőrzés ${adat.auto_gyakorisag_perc} percenként (az olvasottság nem számít)`
              : "· automatikus ellenőrzés kikapcsolva - csak kézi indítás"}
            {adat?.lehuzas_fut
              ? " · ellenőrzés fut…"
              : adat?.utolso_futas
                ? ` · utolsó futás: ${huDatum(adat.utolso_futas.slice(0, 10))} ${adat.utolso_futas.slice(11, 16)}`
                : ""}
            {adat?.legkorabbi_nap ? ` · ${huDatum(adat.legkorabbi_nap)} előtti levelet sosem néz` : ""}
          </span>
        </span>
        {canEdit && (
          <span className="ml-auto flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              disabled={busy}
              onClick={() => setVisszatoltes((v) => !v)}
              title="Régebbi levelek visszamenőleges feldolgozása megadott dátumtartományban - a már átvett levelek akkor sem duplikálódnak"
              className={`rounded-[var(--radius)] border px-2.5 py-1 text-[12px] disabled:opacity-50 ${visszatoltes ? "border-text-accent text-text-accent" : "border-border text-text-secondary hover:bg-surface-2"}`}
            >
              Visszatöltés…
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => lehuzas(true)}
              title="Megmutatja, mit hozna be - semmit nem hoz létre, és a postafiókhoz sem nyúl"
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-2 disabled:opacity-50"
            >
              Előnézet
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => lehuzas(false)}
              className="flex items-center gap-1 rounded-[var(--radius)] border border-border bg-bg-accent px-2.5 py-1 text-[12px] text-text-accent hover:opacity-90 disabled:opacity-50"
            >
              <RefreshCw size={12} className={busy ? "animate-spin" : ""} />
              Ellenőrzés most
            </button>
            {canDelete && (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setMegerosites(megerosites === "osszes" ? null : "osszes")}
                  title="Az összes beérkező tétel törlése egyben - a már rögzített kiadásokhoz nem nyúl (csak admin)"
                  className="rounded-[var(--radius)] border border-text-danger/40 px-2.5 py-1 text-[12px] text-text-danger hover:bg-text-danger/10 disabled:opacity-50"
                >
                  Összes törlése
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setMegerosites(megerosites === "reset" ? null : "reset")}
                  title="Az eddigi érkeztetési beérkezések kitakarítása a jóváhagyás-hatások visszavonásával - csak admin, kifejezett megerősítéssel"
                  className="rounded-[var(--radius)] border border-text-danger/40 px-2.5 py-1 text-[12px] text-text-danger hover:bg-text-danger/10 disabled:opacity-50"
                >
                  Tiszta újraindítás
                </button>
              </>
            )}
          </span>
        )}
      </div>
      {visszatoltes && (
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[12px] text-text-secondary">
          <span>Visszamenőleges időszak:</span>
          <input
            type="date"
            value={kezdoDatum}
            min={adat?.legkorabbi_nap}
            onChange={(e) => setKezdoDatum(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-0.5 text-text-primary"
          />
          <span>–</span>
          <input
            type="date"
            value={vegDatum}
            onChange={(e) => setVegDatum(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-0.5 text-text-primary"
          />
          <span className="text-text-muted">
            Az „Ellenőrzés most" erre az időszakra fut; a már átvett levelek nem duplikálódnak
            {adat?.legkorabbi_nap ? `, ${huDatum(adat.legkorabbi_nap)} előttre nem nyit` : ""}.
          </span>
        </div>
      )}
      {megerosites === "osszes" && (
        <div className="mt-1.5 flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-text-danger/50 bg-text-danger/10 px-2.5 py-1.5 text-[12px] text-text-danger">
          <span>
            Törlöd az ÖSSZES beérkező tételt? Minden piszkozat végleg törlődik a fájljával együtt; a már
            rögzített kiadásokat/TIG-számlákat nem érinti. A még olvasatlan levelek a következő ellenőrzéskor
            újra bejönnek.
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={() => void osszesTorles()}
            className="rounded-[var(--radius)] border border-text-danger bg-text-danger/15 px-2.5 py-1 font-medium hover:bg-text-danger/25 disabled:opacity-50"
          >
            Igen, mindet törlöm
          </button>
          <button type="button" onClick={() => setMegerosites(null)} className="text-text-muted hover:underline">
            mégse
          </button>
        </div>
      )}
      {megerosites === "reset" && (
        <div className="mt-1.5 flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-text-danger/50 bg-text-danger/10 px-2.5 py-1.5 text-[12px] text-text-danger">
          <span>
            TISZTA ÚJRAINDÍTÁS: mentés és visszaállítási jegyzék készül, a jóváhagyott tételek import-hatásai
            bizonyítható eredet alapján visszavonódnak. A megerősítéshez írd be: <b>TISZTA INDULAS</b>
          </span>
          <input
            value={resetSzo}
            onChange={(e) => setResetSzo(e.target.value)}
            placeholder="TISZTA INDULAS"
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-0.5 text-text-primary"
          />
          <button
            type="button"
            disabled={busy || resetSzo.trim() !== "TISZTA INDULAS"}
            onClick={() => void reset()}
            className="rounded-[var(--radius)] border border-text-danger bg-text-danger/15 px-2.5 py-1 font-medium hover:bg-text-danger/25 disabled:opacity-50"
          >
            Indítás
          </button>
          <button type="button" onClick={() => setMegerosites(null)} className="text-text-muted hover:underline">
            mégse
          </button>
        </div>
      )}
      {uzenet && <p className="mt-1.5 text-[12px] text-text-secondary">{uzenet}</p>}
      {elonezet && elonezet.length > 0 && (
        <ul className="mt-1.5 max-h-[160px] space-y-0.5 overflow-y-auto text-[12px] text-text-secondary">
          {elonezet.map((e, i) => (
            <li key={i}>
              {e.felado} – {e.targy} {e.csatolmanyok.length > 0 ? `(${e.csatolmanyok.join(", ")})` : "(nincs csatolmány)"}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Az első http(s) link a levél szövegéből - a "Számla megnyitása a
 * szolgáltatónál" gombhoz (Számlázz.hu/Billingo értesítők). */
function elsoLink(szoveg: string | null): string | null {
  const t = /(https?:\/\/[^\s<>"']+)/.exec(szoveg ?? "");
  return t ? t[1] : null;
}

/** A kiválasztott cél emberi RÉSZLETEI a javaslat alternatívái közül. */
function celReszletek(adat: BejovoSzamlaReszlet): Record<string, unknown> | null {
  const celId =
    adat.cel_certificate_id ?? adat.cel_internal_certificate_id ?? adat.cel_expense_id ?? adat.cel_kotelezettseg_idoszak_id ?? adat.cel_kp_forgalom_id;
  const talalat = (adat.javaslat?.alternativak ?? []).find(
    (a) => a.tipus === adat.cel_tipus && a.cel_id === celId,
  ) as { reszletek?: Record<string, unknown> } | undefined;
  return talalat?.reszletek ?? null;
}

/** A célrekord MEGNYITHATÓ helye a rendszerben. */
function celLink(adat: BejovoSzamlaReszlet): { href: string; cimke: string } | null {
  if (UJ_KOLTSEG.has(adat.cel_tipus ?? "") && adat.cel_project_code_id) {
    return { href: `/projektek/project-kodok/${adat.cel_project_code_id}`, cimke: "Projektkód megnyitása" };
  }
  if (adat.cel_tipus === "kulsos_tig") return { href: "/utokovetes", cimke: "Megnyitás az Utókövetésben" };
  if (adat.cel_tipus === "belsos_tig") return { href: "/belsos-tig", cimke: "Megnyitás a Belsős TIG-nél" };
  if (adat.cel_tipus === "erezsi") return { href: "/e-rezsi", cimke: "Megnyitás az E-Rezsinél" };
  if (adat.cel_tipus === "kp") return { href: "/penzugyek/kp-forgalom", cimke: "Megnyitás a KP forgalomnál" };
  if (adat.cel_tipus === "kiadas_csatolas") return { href: "/penzugyek", cimke: "Megnyitás a Pénzügyekben" };
  return null;
}

/** MI FOG TÖRTÉNNI jóváhagyáskor - egy mondatban, emberi nyelven (rögzített
 * tételnél múlt időben). */
function ezTortenik(adat: BejovoSzamlaReszlet, mult: boolean): string {
  const r = celReszletek(adat) as {
    projekt_nev?: string;
    projektkod?: string;
    forgatas_datuma?: string;
    szamlazo_fel?: string;
  } | null;
  const lanc = [r?.projekt_nev, r?.projektkod, r?.forgatas_datuma ? `${r.forgatas_datuma} forgatás` : null, r?.szamlazo_fel]
    .filter(Boolean)
    .join(" → ");
  const osszeg = adat.netto != null ? `${formatSzam(adat.netto)} ${adat.penznem} nettó` : "a megadott összegű";
  if (adat.cel_tipus === "kulsos_tig") {
    return `${lanc ? lanc + ". " : ""}A számlát ${mult ? "a meglévő külsős TIG-hez csatoltuk" : "a meglévő külsős TIG-hez csatoljuk"}. Új költség nem ${mult ? "keletkezett" : "keletkezik"}. A fizetési állapot változatlan.`;
  }
  if (adat.cel_tipus === "belsos_tig") {
    return `A számla ${mult ? "a havi belsős TIG-hez került" : "a havi belsős TIG-hez kerül"}. Új költség nem ${mult ? "keletkezett" : "keletkezik"}.`;
  }
  if (adat.cel_tipus === "kiadas_csatolas") {
    return `A számla ${mult ? "a kiválasztott meglévő kiadás mellé került" : "a kiválasztott meglévő kiadás mellé kerül"} - összege és állapota nem ${mult ? "változott" : "változik"}.`;
  }
  if (adat.cel_tipus === "erezsi") {
    return `A számla tényleges összege ${mult ? "az előfizetés időszakára került" : "az előfizetés időszakára kerül"}; a fizetve-jelölés nem ${mult ? "változott" : "változik"}.`;
  }
  if (adat.cel_tipus === "kp") {
    return `A bizonylat ${mult ? "a KP-tételhez került" : "a KP-tételhez kerül"} - új pénzmozgás nem ${mult ? "keletkezett" : "keletkezik"}.`;
  }
  if (adat.cel_tipus === "mukodesi") {
    return `Új, NEM kifizetett általános működési kiadás ${mult ? "jött létre" : "jön létre"} (${osszeg}), tudatosan projekt nélkül.`;
  }
  if (UJ_KOLTSEG.has(adat.cel_tipus ?? "")) {
    return `Új, NEM kifizetett kiadás ${mult ? "jött létre" : "jön létre"} (${osszeg})${adat.cel_tipus === "auto" ? " a kiválasztott autóhoz" : ""} - a kifizetés és a fedezet külön lépés marad.`;
  }
  if (adat.cel_tipus === "bontas") {
    return `A számla összege a bontás sorai szerint ${mult ? "oszlott meg" : "oszlik meg"} a célok között: az új-kiadás sorok NEM kifizetett kiadásként ${mult ? "jöttek" : "jönnek"} létre, a meglévő TIG-ek/kiadások összegét nem ${mult ? "írtuk" : "írjuk"} át. A számla EGY pénzügyi dokumentum marad (${osszeg}).`;
  }
  return mult ? "A tétel rögzítésre került." : "Válassz célt a rögzítéshez.";
}

/** Egy SZERKESZTHETŐ bontás-sor (a beviteli mezők szövegként tartják az
 * értékeket; küldés előtt a bontasKuldheto számmá alakítja). */
type BontasRow = {
  cel_tipus: string;
  project_code_id: string;
  cel_id: string;
  netto: string;
  megjegyzes: string;
  forras: string | null;
};

function szamma(s: string): number {
  return Number((s || "0").replace(/[  ]/g, "").replace(",", "."));
}

function bontasKuldheto(rows: BontasRow[]): Record<string, unknown>[] {
  return rows.map((r) => ({
    cel_tipus: r.cel_tipus || null,
    project_code_id: r.project_code_id ? Number(r.project_code_id) : null,
    cel_id: r.cel_id ? Number(r.cel_id) : null,
    netto: szamma(r.netto),
    megjegyzes: r.megjegyzes || null,
    forras: r.forras,
  }));
}

/** Mi HIÁNYZIK a jóváhagyáshoz - üres lista = mehet. */
function hianyok(adat: BejovoSzamlaReszlet, arfolyam: string, bontas: BontasRow[] | null): string[] {
  const h: string[] = [];
  if (!adat.cel_tipus) h.push("nincs kiválasztva cél");
  if (adat.cel_tipus === "kimeno") h.push("kimenő számla kiadásként nem rögzíthető");
  if (adat.cel_tipus === "egyeb") h.push("a „tisztázandó” nem rögzíthető - válassz konkrét célt");
  if (adat.dokumentum_tipus === "dijbekero" && (UJ_KOLTSEG.has(adat.cel_tipus ?? "") || adat.cel_tipus === "bontas"))
    h.push("díjbekérő nem rögzíthető végleges számlaként");
  if (adat.dokumentum_tipus === "ertesito" && (UJ_KOLTSEG.has(adat.cel_tipus ?? "") || adat.cel_tipus === "bontas"))
    h.push("ez számlaértesítő - várd meg / töltsd fel a számlafájlt");
  if (UJ_KOLTSEG.has(adat.cel_tipus ?? "") && adat.netto == null) h.push("hiányzik a nettó összeg");
  if (UJ_KOLTSEG.has(adat.cel_tipus ?? "") && adat.penznem !== "HUF" && !arfolyam.trim()) h.push(`add meg a(z) ${adat.penznem}→HUF árfolyamot`);
  if (adat.cel_tipus === "auto" && !adat.cel_auto_id) h.push("válaszd ki az autót");
  const cm = CEL_MEZO[adat.cel_tipus ?? ""];
  if (cm && !(adat as unknown as Record<string, number | null>)[cm.mezo]) h.push("válaszd ki a cél-rekordot");
  if (CSATOLOS.has(adat.cel_tipus ?? "") && !adat.fajl_nev) h.push("nincs fájl - töltsd fel a számlát");
  if (adat.cel_tipus === "bontas") {
    if (!bontas || bontas.length === 0) h.push("vedd fel a bontás sorait");
    else {
      if (adat.netto == null) h.push("hiányzik a számla nettó összege");
      if (bontas.some((r) => !r.cel_tipus)) h.push("minden bontás-sorhoz válassz célt");
      if (bontas.some((r) => r.cel_tipus === "kiadas_uj" && !r.project_code_id)) h.push("az új-kiadás sorokhoz válassz projektkódot");
      if (bontas.some((r) => (r.cel_tipus === "kulsos_tig" || r.cel_tipus === "kiadas_csatolas") && !r.cel_id))
        h.push("a meglévő tételhez kapcsolt sorokhoz válaszd ki a tételt");
      if (bontas.some((r) => !szamma(r.netto))) h.push("minden bontás-sorhoz kell összeg");
      const osszesen = bontas.reduce((s, r) => s + szamma(r.netto), 0);
      if (adat.netto != null && Math.abs(osszesen - adat.netto) > 1)
        h.push(`a bontás összegei (${formatSzam(Math.round(osszesen * 100) / 100)}) nem adják ki a számla nettóját (${formatSzam(adat.netto)})`);
      if (adat.penznem !== "HUF" && !arfolyam.trim() && bontas.some((r) => r.cel_tipus === "kiadas_uj" || r.cel_tipus === "mukodesi"))
        h.push(`add meg a(z) ${adat.penznem}→HUF árfolyamot`);
      if (!adat.fajl_nev && bontas.some((r) => r.cel_tipus === "kulsos_tig")) h.push("a TIG-hez kapcsoláshoz kell a számla fájlja");
    }
  }
  return h;
}

function gombFelirat(adat: BejovoSzamlaReszlet): string {
  if (adat.cel_tipus === "kulsos_tig" || adat.cel_tipus === "belsos_tig") return "Csatolás ehhez a TIG-hez";
  if (adat.cel_tipus === "kiadas_csatolas") return "Csatolás ehhez a kiadáshoz";
  if (adat.cel_tipus === "erezsi") return "Rögzítés az előfizetés-időszakra";
  if (adat.cel_tipus === "kp") return "Bizonylat csatolása a KP-tételhez";
  if (UJ_KOLTSEG.has(adat.cel_tipus ?? "")) return "Új kiadás rögzítése";
  if (adat.cel_tipus === "bontas") return "Bontás rögzítése";
  return "Jóváhagyás és rögzítés";
}

/** A RÉSZLETES ELLENŐRZŐ: bal oldalon a számla, jobb oldalon a vezetett
 * folyamat - Mit olvastunk ki? / Ide kerül / Ez fog történni / Művelet. */
function Reszletes({
  bejovoId,
  valasztek,
  canEdit,
  canCreate,
  canDelete,
  onZaras,
}: {
  bejovoId: number;
  valasztek: Valasztek;
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
  onZaras: () => void;
}) {
  const [adat, setAdat] = useState<BejovoSzamlaReszlet | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [arfolyam, setArfolyam] = useState("");
  const [felosztas, setFelosztas] = useState<{ project_code_id: string; netto: string }[] | null>(null);
  const [celOpciok, setCelOpciok] = useState<{ value: string; label: string }[] | null>(null);
  //: A bontás-szerkesztő sorai (több projekt egy számlán) - a szerverre a
  //: PATCH `bontas` mezője viszi (piszkozat), a jóváhagyás pedig a
  //: cel_tipus="bontas" + bontas párossal rögzít.
  const [bontas, setBontas] = useState<BontasRow[] | null>(null);
  const [bontasCelOpciok, setBontasCelOpciok] = useState<Record<string, { value: string; label: string }[]>>({});
  const [elonezetAllapot, setElonezetAllapot] = useState<"tolt" | "kesz" | "lassu">("tolt");
  const fajlPotloRef = useRef<HTMLInputElement>(null);

  const betolt = useCallback(async () => {
    const res = await authFetch(`/api/v1/bejovo-szamlak/${bejovoId}`);
    if (res.ok) {
      const d: BejovoSzamlaReszlet = await res.json();
      setAdat(d);
      setDraft({});
    }
  }, [bejovoId]);

  useEffect(() => {
    void betolt();
  }, [betolt]);

  // A PDF-előnézet betöltés-figyelése: amíg nem jelez az iframe, "Betöltés…"
  // látszik; 10 mp után felajánljuk a megnyitást/letöltést - nem marad néma
  // szürke panel (a felhasználó hibajelzése).
  useEffect(() => {
    setElonezetAllapot("tolt");
    const t = setTimeout(() => setElonezetAllapot((e) => (e === "tolt" ? "lassu" : e)), 10000);
    return () => clearTimeout(t);
  }, [adat?.url]);

  // A mentett bontás-piszkozat betöltése a szerkesztőbe (csak amíg a
  // felhasználó helyben nem kezdett szerkeszteni).
  useEffect(() => {
    if (adat?.bontas?.length && bontas === null) {
      setBontas(
        adat.bontas.map((s) => ({
          cel_tipus: s.cel_tipus ?? "",
          project_code_id: s.project_code_id != null ? String(s.project_code_id) : "",
          cel_id: s.cel_id != null ? String(s.cel_id) : "",
          netto: s.netto != null ? String(s.netto) : "",
          megjegyzes: s.megjegyzes ?? "",
          forras: s.forras ?? null,
        })),
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adat?.id, adat?.bontas]);

  // A kereshető cél-választék betöltése a kiválasztott cél-típushoz.
  const celTipus = adat?.cel_tipus ?? "";
  useEffect(() => {
    const cm = CEL_MEZO[celTipus];
    if (!cm?.valasztek) {
      setCelOpciok(null);
      return;
    }
    let elve = false;
    authFetch(`/api/v1/bejovo-szamlak/celok/${cm.valasztek}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!elve && d) setCelOpciok(d.lista.map((x: { id: number; cimke: string }) => ({ value: String(x.id), label: x.cimke })));
      })
      .catch(() => setCelOpciok([]));
    return () => {
      elve = true;
    };
  }, [celTipus]);

  // A bontás-sorokhoz kellő cél-választékok (TIG-ek, kiadások) betöltése.
  useEffect(() => {
    if (celTipus !== "bontas") return;
    let elve = false;
    for (const t of ["kulsos_tig", "kiadas_csatolas"]) {
      authFetch(`/api/v1/bejovo-szamlak/celok/${t}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (!elve && d)
            setBontasCelOpciok((p) => ({ ...p, [t]: d.lista.map((x: { id: number; cimke: string }) => ({ value: String(x.id), label: x.cimke })) }));
        })
        .catch(() => undefined);
    }
    return () => {
      elve = true;
    };
  }, [celTipus]);

  async function hivas(ut: string, body: unknown, method = "POST"): Promise<boolean> {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/bejovo-szamlak/${bejovoId}${ut}`, { method, body: JSON.stringify(body) });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setHiba(d?.detail ?? `Sikertelen művelet (${res.status})`);
        return false;
      }
      setAdat(await res.json());
      setDraft({});
      return true;
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  function mentendoMezok(): Record<string, unknown> {
    const t: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(draft)) {
      if (["netto", "afa_osszeg", "brutto"].includes(k)) t[k] = v === "" ? null : Number(v.replace(/[  ]/g, "").replace(",", "."));
      else t[k] = v === "" ? null : v;
    }
    return t;
  }

  async function piszkozatMentes(): Promise<boolean> {
    const t = mentendoMezok();
    if ((adat?.cel_tipus === "bontas" || draft.cel_tipus === "bontas") && bontas !== null) t.bontas = bontasKuldheto(bontas);
    if (Object.keys(t).length === 0) return true;
    return hivas("", t, "PATCH");
  }

  async function jovahagyas() {
    if (!(await piszkozatMentes())) return;
    const body: Record<string, unknown> = {};
    if (arfolyam.trim()) body.arfolyam = Number(arfolyam.replace(",", "."));
    if (felosztas && felosztas.length > 0) {
      body.felosztas = felosztas.map((f) => ({
        project_code_id: f.project_code_id ? Number(f.project_code_id) : null,
        netto: Number((f.netto || "0").replace(/[  ]/g, "").replace(",", ".")),
      }));
    }
    if (adat?.cel_tipus === "bontas" && bontas !== null) body.bontas = bontasKuldheto(bontas);
    await hivas("/jovahagyas", body);
  }

  async function fajlPotlas(fajl: File) {
    setBusy(true);
    setHiba(null);
    try {
      const fd = new FormData();
      fd.append("file", fajl);
      const res = await authFetch(`/api/v1/bejovo-szamlak/${bejovoId}/fajl`, { method: "POST", body: fd });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setHiba(d?.detail ?? `Sikertelen feltöltés (${res.status})`);
        return;
      }
      setAdat(await res.json());
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (adat === null) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <p className="text-[13px] text-text-secondary">Betöltés…</p>
      </div>
    );
  }

  const bizonytalan = new Set(adat.kinyert?.bizonytalan ?? []);
  const forrasok = adat.kinyert?.mezo_forrasok ?? {};
  const rogzitett = adat.allapot === "jovahagyva";
  const lezart = rogzitett || adat.allapot === "nem_szamla";
  const cel = (draft.cel_tipus as string) ?? adat.cel_tipus ?? "";
  const hianyLista = hianyok(adat, arfolyam, bontas);
  const szolgaltatoLink = elsoLink(adat.email_szoveg);
  const kep = (adat.content_type ?? "").startsWith("image/");
  const cm = CEL_MEZO[cel];
  const celAktualisId = cm ? (adat as unknown as Record<string, number | null>)[cm.mezo] : null;
  const link = celLink(adat);
  const reszletek = celReszletek(adat) as {
    projekt_nev?: string;
    projektkod?: string;
    forgatas_datuma?: string;
    szamlazo_fel?: string;
    fedett_szemelyek?: string[];
    netto?: number;
    meglevo_szamlak?: number;
    egyezik?: string[];
    elter?: string[];
  } | null;

  function mezo(nev: keyof BejovoSzamlaReszlet & string, cimke: string, tipus: "text" | "date" | "szam" = "text") {
    const ertek = draft[nev] ?? (adat![nev] != null ? String(adat![nev]) : "");
    const gyanus = bizonytalan.has(nev) || bizonytalan.has(nev.replace("_datuma", ""));
    const forras = draft[nev] !== undefined ? "felhasznalo" : forrasok[nev];
    return (
      <div className="flex flex-col gap-0.5">
        <label className="flex items-center gap-1 text-[11px] text-text-muted">
          {cimke}
          {gyanus && (
            <span className="rounded bg-bg-warning px-1 text-[10px] text-text-warning" title="A kiolvasás bizonytalan - ellenőrizd a dokumentumon">
              bizonytalan
            </span>
          )}
          {forras === "felhasznalo" && (
            <span className="text-[10px] text-text-accent" title="Kézzel javított érték">
              ✎
            </span>
          )}
        </label>
        <input
          type={tipus === "date" ? "date" : "text"}
          value={ertek}
          disabled={lezart || !canEdit}
          onChange={(e) => setDraft((p) => ({ ...p, [nev]: e.target.value }))}
          className={`rounded-[var(--radius)] border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none disabled:opacity-60 ${gyanus ? "border-text-warning/60" : "border-border"}`}
        />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3" onMouseDown={onZaras}>
      <div
        onMouseDown={(e) => e.stopPropagation()}
        className="flex h-[94vh] w-full max-w-[1240px] flex-col overflow-hidden rounded-[var(--radius)] border border-border bg-surface-1"
      >
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
          <h2 className="text-[14px] font-medium text-text-primary">
            {adat.kibocsato_nev ?? adat.fajl_nev ?? "Beérkező számla"}
            {adat.szamlaszam ? ` · ${adat.szamlaszam}` : ""}
          </h2>
          <StatusBadge label={ALLAPOTOK[adat.allapot]?.cimke ?? adat.allapot} tone={ALLAPOTOK[adat.allapot]?.tone ?? "neutral"} />
          {adat.dokumentum_tipus && adat.dokumentum_tipus !== "szamla" && <StatusBadge label={adat.dokumentum_tipus} tone="warning" />}
          {!rogzitett && adat.javaslat?.erosseg && EROSSEG[adat.javaslat.erosseg] && (
            <StatusBadge label={EROSSEG[adat.javaslat.erosseg].cimke} tone={EROSSEG[adat.javaslat.erosseg].tone} />
          )}
          <button type="button" onClick={onZaras} className="ml-auto rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3">
            Bezárás
          </button>
        </div>

        <div className="flex min-h-0 flex-1">
          {/* BAL: a számla előnézete - betöltés-jelzéssel és mindig elérhető
              megnyitás/letöltés úttal. */}
          <div className="hidden w-1/2 flex-col border-r border-border bg-surface-2 md:flex">
            {adat.url ? (
              <>
                <div className="flex items-center gap-2 border-b border-border px-3 py-1.5 text-[12px] text-text-secondary">
                  <span className="truncate">{adat.fajl_nev}</span>
                  {elonezetAllapot === "tolt" && <span className="text-text-muted">Betöltés…</span>}
                  {elonezetAllapot === "lassu" && <span className="text-text-warning">Az előnézet nem töltött be - nyisd meg külön:</span>}
                  <a href={adat.url} target="_blank" rel="noreferrer" className="ml-auto flex shrink-0 items-center gap-1 text-text-accent hover:underline">
                    <ExternalLink size={12} />
                    Megnyitás új lapon
                  </a>
                  <a href={adat.url} download className="flex shrink-0 items-center gap-1 text-text-accent hover:underline">
                    <Download size={12} />
                    Letöltés
                  </a>
                </div>
                {kep ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={adat.url} alt="Számla" onLoad={() => setElonezetAllapot("kesz")} className="min-h-0 flex-1 object-contain" />
                ) : (
                  <iframe src={adat.url} title="Számla előnézet" onLoad={() => setElonezetAllapot("kesz")} className="min-h-0 w-full flex-1" />
                )}
              </>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-[13px] text-text-muted">
                <p>Ehhez a levélhez nem tartozott csatolmány - a számla a szolgáltatónál van.</p>
                {szolgaltatoLink && (
                  <a href={szolgaltatoLink} target="_blank" rel="noreferrer" className="text-text-accent hover:underline">
                    Számla megnyitása a szolgáltatónál →
                  </a>
                )}
                <p className="text-[12px]">A letöltött PDF-et a jobb oldali „Letöltött számla csatolása" gombbal töltsd fel - ugyanez a tétel folytatódik.</p>
              </div>
            )}
          </div>

          {/* JOBB: a vezetett folyamat. */}
          <div className="flex w-full flex-col md:w-1/2">
            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
              {hiba && <p className="rounded-[var(--radius)] border border-text-danger/50 bg-text-danger/10 px-3 py-2 text-[12.5px] text-text-danger">{hiba}</p>}
              {adat.hiba_uzenet && <p className="text-[12.5px] text-text-danger">Feldolgozási hiba: {adat.hiba_uzenet}</p>}
              {(adat.javaslat?.figyelmeztetesek ?? []).map((f, i) => (
                <p key={i} className="rounded-[var(--radius)] border border-text-warning/50 bg-bg-warning px-3 py-2 text-[12.5px] text-text-warning">
                  {f}
                </p>
              ))}
              {adat.duplikatum_megjegyzes && <p className="text-[12.5px] text-text-warning">{adat.duplikatum_megjegyzes}</p>}

              {/* 1) MIT OLVASOTT KI A RENDSZER. */}
              <section>
                <h3 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-text-muted">1 · Mit olvastunk ki</h3>
                <div className="grid grid-cols-2 gap-2">
                  {mezo("kibocsato_nev", "Kibocsátó")}
                  {mezo("kibocsato_adoszam", "Kibocsátó adószáma")}
                  {mezo("szamlaszam", "Számlaszám")}
                  {mezo("penznem", "Pénznem")}
                  {mezo("netto", "Nettó", "szam")}
                  {mezo("brutto", "Bruttó", "szam")}
                  {mezo("kiallitas_datuma", "Számla kelte", "date")}
                  {mezo("teljesites_datuma", "Teljesítés", "date")}
                  {mezo("fizetesi_hatarido", "Fizetési határidő", "date")}
                </div>
                <p className="mt-1.5 text-[11px] text-text-muted">
                  Vevő a számlán: {adat.vevo_nev ?? "–"} · irány: {adat.irany === "kimeno" ? "KIMENŐ (mi állítottuk ki)" : adat.irany === "bejovo" ? "bejövő" : "ismeretlen"}
                  {adat.email_beerkezes ? ` · levél érkezett: ${huDatum(adat.email_beerkezes.slice(0, 10))}` : ""} · importálva: {huDatum(adat.created_at.slice(0, 10))} · a ✎ a kézzel javított mezőt jelöli
                </p>
              </section>

              {/* 2) IDE KERÜL. */}
              <section>
                <h3 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-text-muted">{rogzitett ? "2 · Ide került" : "2 · Ide kerül"}</h3>
                {!lezart && canEdit && (
                  <div className="space-y-2">
                    <select
                      value={cel}
                      disabled={busy}
                      onChange={(e) => void hivas("", { cel_tipus: e.target.value || null }, "PATCH")}
                      className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[12.5px] text-text-primary focus:outline-none"
                    >
                      <option value="">– válassz célt –</option>
                      {Object.entries(CEL_CIMKEK).map(([k, c]) => (
                        <option key={k} value={k}>
                          {c}
                        </option>
                      ))}
                    </select>
                    {/* Kereshető REKORD-választó a cél-típushoz. */}
                    {cm && (
                      <KeresosSelect
                        value={celAktualisId != null ? String(celAktualisId) : ""}
                        options={[{ value: "", label: `– ${cm.cimke} –` }, ...(celOpciok ?? [])]}
                        disabled={busy || celOpciok === null}
                        onChange={(v) => void hivas("", { cel_tipus: cel, [cm.mezo]: v ? Number(v) : null }, "PATCH")}
                      />
                    )}
                    {UJ_KOLTSEG.has(cel) && cel !== "mukodesi" && (
                      <KeresosSelect
                        value={adat.cel_project_code_id != null ? String(adat.cel_project_code_id) : ""}
                        options={[{ value: "", label: "– melyik projektkódhoz –" }, ...valasztek.projektkodok.map((p) => ({ value: String(p.id), label: p.kod }))]}
                        disabled={busy}
                        onChange={(v) => void hivas("", { cel_tipus: cel, cel_project_code_id: v ? Number(v) : null }, "PATCH")}
                      />
                    )}
                    {UJ_KOLTSEG.has(cel) && (
                      <KeresosSelect
                        value={adat.cel_employee_id != null ? String(adat.cel_employee_id) : ""}
                        options={[{ value: "", label: "– nincs számlázó fél (alvállalkozó) –" }, ...valasztek.emberek.map((e) => ({ value: String(e.id), label: e.nev }))]}
                        disabled={busy}
                        onChange={(v) => void hivas("", { cel_employee_id: v ? Number(v) : null }, "PATCH")}
                      />
                    )}
                    {cel === "auto" && (
                      <KeresosSelect
                        value={adat.cel_auto_id != null ? String(adat.cel_auto_id) : ""}
                        options={[{ value: "", label: "– válassz autót –" }, ...valasztek.autok.map((a) => ({ value: String(a.id), label: a.nev }))]}
                        disabled={busy}
                        onChange={(v) => void hivas("", { cel_tipus: "auto", cel_auto_id: v ? Number(v) : null }, "PATCH")}
                      />
                    )}
                  </div>
                )}
                {/* A KIVÁLASZTOTT CÉL emberi részletei. */}
                {adat.cel_cimke && (
                  <div className="mt-2 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[12.5px]">
                    <p className="font-medium text-text-primary">{adat.cel_cimke}</p>
                    {reszletek && (
                      <p className="mt-0.5 text-text-secondary">
                        {[
                          reszletek.projekt_nev,
                          reszletek.projektkod,
                          reszletek.forgatas_datuma ? `forgatás: ${reszletek.forgatas_datuma}` : null,
                          reszletek.szamlazo_fel ? `számlázó: ${reszletek.szamlazo_fel}` : null,
                          reszletek.fedett_szemelyek?.length ? `lefedett: ${reszletek.fedett_szemelyek.join(", ")}` : null,
                          reszletek.netto != null ? `${formatSzam(reszletek.netto)} Ft nettó` : null,
                          reszletek.meglevo_szamlak ? `${reszletek.meglevo_szamlak} számla már van rajta` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    )}
                    {reszletek?.egyezik?.length ? <p className="mt-0.5 text-[12px] text-text-success">Egyezik: {reszletek.egyezik.join(", ")}</p> : null}
                    {reszletek?.elter?.length ? <p className="text-[12px] text-text-warning">Eltér: {reszletek.elter.join(", ")}</p> : null}
                    {link && (
                      <Link href={link.href} className="mt-1 inline-block text-[12px] text-text-accent hover:underline">
                        {link.cimke} →
                      </Link>
                    )}
                  </div>
                )}
                {!rogzitett && adat.javaslat_indoklas && <p className="mt-1.5 text-[12px] text-text-muted">{adat.javaslat_indoklas}</p>}

                {/* MIRE ÉPÜL a javaslat - visszakereshető bizonyíték-sorok. */}
                {!rogzitett && (adat.javaslat?.bizonyitek?.length ?? 0) > 0 && (
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-[12px] text-text-accent">Mire épül a javaslat ({adat.javaslat!.bizonyitek!.length})</summary>
                    <ul className="mt-1 list-inside list-disc space-y-0.5 text-[12px] text-text-secondary">
                      {adat.javaslat!.bizonyitek!.map((b, i) => (
                        <li key={i}>{b}</li>
                      ))}
                    </ul>
                  </details>
                )}

                {/* ALTERNATÍVÁK - részletekkel, egy kattintásra átvéve. */}
                {!lezart && (adat.javaslat?.alternativak?.length ?? 0) > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[12px] text-text-accent">További lehetőségek ({adat.javaslat!.alternativak.length})</summary>
                    <ul className="mt-1.5 space-y-1">
                      {adat.javaslat!.alternativak.map((a, i) => {
                        const r = (a as { reszletek?: { egyezik?: string[]; elter?: string[] } }).reszletek;
                        return (
                          <li key={i}>
                            <button
                              type="button"
                              disabled={busy || !canEdit}
                              onClick={() => {
                                const mezoNev =
                                  a.tipus === "kulsos_tig"
                                    ? "cel_certificate_id"
                                    : a.tipus === "belsos_tig"
                                      ? "cel_internal_certificate_id"
                                      : a.tipus === "kiadas_csatolas"
                                        ? "cel_expense_id"
                                        : a.tipus === "erezsi"
                                          ? "cel_kotelezettseg_idoszak_id"
                                          : a.tipus === "auto"
                                            ? "cel_auto_id"
                                            : "cel_project_code_id";
                                void hivas("", { cel_tipus: a.tipus, [mezoNev]: a.cel_id }, "PATCH");
                              }}
                              className="w-full rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-left text-[12.5px] hover:bg-surface-3 disabled:opacity-50"
                            >
                              <span className="text-text-primary">{a.cimke}</span>
                              <span className="block text-[11px] text-text-muted">{a.indoklas}</span>
                              {r?.egyezik?.length ? <span className="block text-[11px] text-text-success">Egyezik: {r.egyezik.join(", ")}</span> : null}
                              {r?.elter?.length ? <span className="block text-[11px] text-text-warning">Eltér: {r.elter.join(", ")}</span> : null}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </details>
                )}

                {/* KÖLTSÉG-RÉSZLETEZŐ ÉRKEZETT: egy kattintással bontássá tehető. */}
                {!lezart && canEdit && adat.javaslat?.bontas_javaslat && cel !== "bontas" && (
                  <div className="mt-2 rounded-[var(--radius)] border border-text-accent/40 bg-surface-3 px-3 py-2 text-[12.5px]">
                    <p className="text-text-primary">
                      Költség-részletező érkezett a számla mellé ({adat.javaslat.bontas_javaslat.forras_fajl ?? "táblázat"}):{" "}
                      {adat.javaslat.bontas_javaslat.sorok.length} sor, összesen {formatSzam(adat.javaslat.bontas_javaslat.osszesen)}
                      {adat.javaslat.bontas_javaslat.penznem ? ` ${adat.javaslat.bontas_javaslat.penznem}` : ""}.
                    </p>
                    {adat.javaslat.bontas_javaslat.figyelmeztetesek.map((f, i) => (
                      <p key={i} className="mt-0.5 text-[12px] text-text-warning">
                        {f}
                      </p>
                    ))}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        const sorok = adat.javaslat!.bontas_javaslat!.sorok.map((s) => ({
                          cel_tipus: s.cel_tipus ?? "",
                          project_code_id: s.project_code_id != null ? String(s.project_code_id) : "",
                          cel_id: s.cel_id != null ? String(s.cel_id) : "",
                          netto: s.netto != null ? String(s.netto) : "",
                          megjegyzes: s.megjegyzes ?? "",
                          forras: s.forras ?? null,
                        }));
                        setBontas(sorok);
                        void hivas("", { cel_tipus: "bontas", bontas: bontasKuldheto(sorok) }, "PATCH");
                      }}
                      className="mt-1 rounded-[var(--radius)] border border-border bg-bg-accent px-2.5 py-1 text-[12px] text-text-accent hover:opacity-90 disabled:opacity-50"
                    >
                      Bontás megnyitása a részletező soraival
                    </button>
                  </div>
                )}

                {/* BONTÁS-SZERKESZTŐ: több projekt egy számlán, vegyes célokkal. */}
                {cel === "bontas" && !lezart && canEdit && (
                  <div className="mt-2 space-y-1.5 rounded-[var(--radius)] border border-border p-2">
                    {(() => {
                      const sorok = bontas ?? [];
                      const felosztva = sorok.reduce((s, r) => s + szamma(r.netto), 0);
                      const hatra = adat.netto != null ? Math.round((adat.netto - felosztva) * 100) / 100 : null;
                      return (
                        <p className="text-[11.5px] text-text-muted">
                          A számla EGY pénzügyi dokumentum marad - a sorok nettói pontosan a számla nettóját (
                          {adat.netto != null ? formatSzam(adat.netto) : "?"} {adat.penznem}) adják ki.{" "}
                          <b className={hatra !== null && Math.abs(hatra) > 1 ? "text-text-warning" : "text-text-success"}>
                            Felosztva: {formatSzam(Math.round(felosztva * 100) / 100)}
                            {hatra !== null ? ` · hátra: ${formatSzam(hatra)}` : ""}
                          </b>
                        </p>
                      );
                    })()}
                    {(bontas ?? []).map((r, i) => (
                      <div key={i} className="space-y-1 rounded-[var(--radius)] border border-border/70 p-1.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <select
                            value={r.cel_tipus}
                            onChange={(e) =>
                              setBontas((p) => (p ?? []).map((x, j) => (j === i ? { ...x, cel_tipus: e.target.value, project_code_id: "", cel_id: "" } : x)))
                            }
                            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary"
                          >
                            <option value="">– cél –</option>
                            {BONTAS_CELOK.map((c) => (
                              <option key={c.kulcs} value={c.kulcs}>
                                {c.cimke}
                              </option>
                            ))}
                          </select>
                          <input
                            placeholder="nettó"
                            value={r.netto}
                            onChange={(e) => setBontas((p) => (p ?? []).map((x, j) => (j === i ? { ...x, netto: e.target.value } : x)))}
                            className="w-28 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-right text-[12px] text-text-primary"
                          />
                          <input
                            placeholder="megjegyzés"
                            value={r.megjegyzes}
                            onChange={(e) => setBontas((p) => (p ?? []).map((x, j) => (j === i ? { ...x, megjegyzes: e.target.value } : x)))}
                            className="min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary"
                          />
                          <button
                            type="button"
                            onClick={() => setBontas((p) => (p ?? []).filter((_, j) => j !== i))}
                            title="Sor törlése"
                            className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-muted hover:bg-surface-3"
                          >
                            ×
                          </button>
                        </div>
                        {r.cel_tipus === "kiadas_uj" && (
                          <KeresosSelect
                            value={r.project_code_id}
                            options={[{ value: "", label: "– melyik projektkódhoz –" }, ...valasztek.projektkodok.map((p) => ({ value: String(p.id), label: p.kod }))]}
                            onChange={(v) => setBontas((p) => (p ?? []).map((x, j) => (j === i ? { ...x, project_code_id: v } : x)))}
                          />
                        )}
                        {(r.cel_tipus === "kulsos_tig" || r.cel_tipus === "kiadas_csatolas") && (
                          <KeresosSelect
                            value={r.cel_id}
                            options={[
                              { value: "", label: r.cel_tipus === "kulsos_tig" ? "– melyik külsős TIG-hez –" : "– melyik kiadáshoz –" },
                              ...(bontasCelOpciok[r.cel_tipus] ?? []),
                            ]}
                            disabled={!bontasCelOpciok[r.cel_tipus]}
                            onChange={(v) => setBontas((p) => (p ?? []).map((x, j) => (j === i ? { ...x, cel_id: v } : x)))}
                          />
                        )}
                        {r.forras && <p className="text-[11px] text-text-muted">Forrás: {r.forras}</p>}
                      </div>
                    ))}
                    <div className="flex flex-wrap gap-2 text-[12px]">
                      <button
                        type="button"
                        onClick={() => setBontas((p) => [...(p ?? []), { cel_tipus: "", project_code_id: "", cel_id: "", netto: "", megjegyzes: "", forras: null }])}
                        className="text-text-accent hover:underline"
                      >
                        + sor
                      </button>
                      {adat.javaslat?.bontas_javaslat && (
                        <button
                          type="button"
                          onClick={() =>
                            setBontas(
                              adat.javaslat!.bontas_javaslat!.sorok.map((s) => ({
                                cel_tipus: s.cel_tipus ?? "",
                                project_code_id: s.project_code_id != null ? String(s.project_code_id) : "",
                                cel_id: s.cel_id != null ? String(s.cel_id) : "",
                                netto: s.netto != null ? String(s.netto) : "",
                                megjegyzes: s.megjegyzes ?? "",
                                forras: s.forras ?? null,
                              })),
                            )
                          }
                          className="text-text-accent hover:underline"
                        >
                          Részletező sorainak átvétele
                        </button>
                      )}
                      <span className="text-text-muted">A „Piszkozat mentése" hiányosan is elment - véglegesíteni csak teljes bontással lehet.</span>
                    </div>
                  </div>
                )}

                {/* Rögzített bontás megjelenítése. */}
                {cel === "bontas" && rogzitett && (adat.bontas?.length ?? 0) > 0 && (
                  <div className="mt-2 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[12.5px]">
                    <p className="font-medium text-text-primary">A rögzített bontás sorai</p>
                    <ul className="mt-1 space-y-0.5 text-text-secondary">
                      {adat.bontas!.map((s, i) => (
                        <li key={i}>
                          {BONTAS_CELOK.find((c) => c.kulcs === s.cel_tipus)?.cimke ?? s.cel_tipus} · {formatSzam(s.netto)}
                          {s.projektkod ? ` · ${s.projektkod}` : ""}
                          {s.megjegyzes ? ` · ${s.megjegyzes}` : ""}
                          {s.forras ? ` · (${s.forras})` : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Felosztás több projekt közt. */}
                {UJ_KOLTSEG.has(cel) && !lezart && canEdit && (
                  <div className="mt-2">
                    {felosztas === null ? (
                      <button
                        type="button"
                        onClick={() => setFelosztas([{ project_code_id: adat.cel_project_code_id ? String(adat.cel_project_code_id) : "", netto: "" }, { project_code_id: "", netto: "" }])}
                        className="text-[12px] text-text-accent hover:underline"
                      >
                        + Felosztás több projekt között
                      </button>
                    ) : (
                      <div className="space-y-1.5 rounded-[var(--radius)] border border-border p-2">
                        <p className="text-[11.5px] text-text-muted">
                          A rész-összegeknek pontosan ki kell adniuk a számla nettóját ({adat.netto != null ? formatSzam(adat.netto) : "?"} {adat.penznem}). A számla egy dokumentum marad, az első tételhez csatolva.
                        </p>
                        {felosztas.map((f, i) => (
                          <div key={i} className="flex gap-1.5">
                            <select
                              value={f.project_code_id}
                              onChange={(e) => setFelosztas(felosztas.map((x, j) => (j === i ? { ...x, project_code_id: e.target.value } : x)))}
                              className="min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary"
                            >
                              <option value="">– projektkód –</option>
                              {valasztek.projektkodok.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.kod}
                                </option>
                              ))}
                            </select>
                            <input
                              placeholder="nettó"
                              value={f.netto}
                              onChange={(e) => setFelosztas(felosztas.map((x, j) => (j === i ? { ...x, netto: e.target.value } : x)))}
                              className="w-28 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-right text-[12px] text-text-primary"
                            />
                          </div>
                        ))}
                        <div className="flex gap-2 text-[12px]">
                          <button type="button" onClick={() => setFelosztas([...felosztas, { project_code_id: "", netto: "" }])} className="text-text-accent hover:underline">
                            + sor
                          </button>
                          <button type="button" onClick={() => setFelosztas(null)} className="text-text-muted hover:underline">
                            felosztás elvetése
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {(UJ_KOLTSEG.has(cel) || cel === "bontas") && (draft.penznem ?? adat.penznem) !== "HUF" && !lezart && (
                  <div className="mt-2 flex items-center gap-2">
                    <label className="text-[12px] text-text-muted">Árfolyam ({adat.penznem}→HUF):</label>
                    <input value={arfolyam} onChange={(e) => setArfolyam(e.target.value)} placeholder="pl. 395,5" className="w-24 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary" />
                  </div>
                )}
              </section>

              {/* 3) EZ FOG TÖRTÉNNI / EZ TÖRTÉNT. */}
              <section>
                <h3 className="mb-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">{rogzitett ? "3 · Ez történt" : "3 · Ez fog történni"}</h3>
                <p className="rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[12.5px] text-text-secondary">{ezTortenik(adat, rogzitett)}</p>
                {rogzitett && (
                  <div className="mt-2 space-y-1 text-[12.5px] text-text-secondary">
                    <p>
                      Jóváhagyta: <b className="text-text-primary">{adat.jovahagyo_nev ?? "?"}</b>
                      {adat.jovahagyva_at ? ` · ${huDatum(adat.jovahagyva_at.slice(0, 10))}` : ""}
                    </p>
                    {adat.rogzitett_expense_id && (
                      <Link
                        href={adat.cel_project_code_id ? `/projektek/project-kodok/${adat.cel_project_code_id}` : "/penzugyek"}
                        className="inline-block rounded-[var(--radius)] border border-border px-2.5 py-1 text-text-accent hover:bg-surface-3"
                      >
                        Rögzített tétel megnyitása →
                      </Link>
                    )}
                    {!adat.rogzitett_expense_id && link && (
                      <Link href={link.href} className="inline-block rounded-[var(--radius)] border border-border px-2.5 py-1 text-text-accent hover:bg-surface-3">
                        {link.cimke} →
                      </Link>
                    )}
                  </div>
                )}
              </section>

              {/* Linkes levél folytatása / fájl-pótlás. */}
              {!lezart && canEdit && (
                <section className="text-[12.5px]">
                  <input
                    ref={fajlPotloRef}
                    type="file"
                    accept="application/pdf,image/jpeg,image/png,image/webp,image/heic"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) void fajlPotlas(f);
                      e.target.value = "";
                    }}
                  />
                  <div className="flex flex-wrap gap-2">
                    {szolgaltatoLink && !adat.fajl_nev && (
                      <a href={szolgaltatoLink} target="_blank" rel="noreferrer" className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-text-accent hover:bg-surface-3">
                        Számla megnyitása a szolgáltatónál
                      </a>
                    )}
                    <button type="button" disabled={busy} onClick={() => fajlPotloRef.current?.click()} className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                      {adat.fajl_nev ? "Fájl cseréje" : "Letöltött számla csatolása"}
                    </button>
                    {/* HELY ÚJRAKERESÉSE (a felhasználó kérése): a már kinyert
                        adatokon újra fut a párosítás - pl. miután felvetted a
                        hiányzó TIG-et/kiadást/projektkódot. Gyors, nem olvassa
                        ki újra a dokumentumot. */}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void hivas("/ujrafeldolgozas", { mod: "javaslat" })}
                      title="Újra megpróbálja megtalálni a számla helyét a mostani adatok alapján (új TIG/kiadás/projektkód után) - a dokumentumot nem olvassa ki újra"
                      className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                    >
                      <RefreshCw size={11} className="mr-1 inline" />
                      Hely újrakeresése
                    </button>
                    {(adat.allapot === "hiba" || adat.allapot === "feldolgozas") && (
                      <button type="button" disabled={busy} onClick={() => void hivas("/ujrafeldolgozas", { mod: "teljes" })} className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                        Feldolgozás újrapróbálása
                      </button>
                    )}
                  </div>
                </section>
              )}

              {/* Levél / utasítás. */}
              {(adat.email_targy || adat.felhasznaloi_utasitas) && (
                <section>
                  <h3 className="mb-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">Levél / utasítás</h3>
                  {adat.email_felado && (
                    <p className="text-[12px] text-text-muted">
                      Feladó: {adat.email_felado} · tárgy: {adat.email_targy} — a levél küldője nem azonos a számla kibocsátójával.
                    </p>
                  )}
                  {adat.email_szoveg && <p className="mt-1 max-h-[80px] overflow-y-auto whitespace-pre-line text-[12px] text-text-secondary">{adat.email_szoveg}</p>}
                  {adat.felhasznaloi_utasitas && (
                    <p className="mt-1 text-[12px] text-text-secondary">
                      <b>Utasítás:</b> {adat.felhasznaloi_utasitas}
                    </p>
                  )}
                </section>
              )}
            </div>

            {/* 4) MŰVELETSÁV - mindig látható (sticky), nem vész el görgetésnél. */}
            <div className="border-t border-border bg-surface-1 px-4 py-2.5">
              {!lezart ? (
                <>
                  {hianyLista.length > 0 && (
                    <p className="mb-1.5 text-[12px] text-text-warning">A rögzítéshez még hiányzik: {hianyLista.join("; ")}.</p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {canCreate && (
                      <button
                        type="button"
                        disabled={busy || hianyLista.length > 0}
                        onClick={jovahagyas}
                        className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent hover:opacity-90 disabled:opacity-50"
                      >
                        {busy ? "Folyamatban…" : gombFelirat(adat)}
                      </button>
                    )}
                    {canEdit && (
                      <>
                        <button type="button" disabled={busy || (Object.keys(draft).length === 0 && !(cel === "bontas" && bontas !== null))} onClick={() => void piszkozatMentes()} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                          Piszkozat mentése
                        </button>
                        <button type="button" disabled={busy} onClick={() => void hivas("/duplikatum", {})} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                          Duplikátum
                        </button>
                        <button type="button" disabled={busy} onClick={() => void hivas("/nem-szamla", {})} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                          Nem számla
                        </button>
                      </>
                    )}
                    {canDelete && <TorlesGomb adat={adat} busy={busy} setBusy={setBusy} setHiba={setHiba} onZaras={onZaras} />}
                  </div>
                </>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {canDelete && <TorlesGomb adat={adat} busy={busy} setBusy={setBusy} setHiba={setHiba} onZaras={onZaras} />}
                  <button type="button" onClick={onZaras} className="ml-auto rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
                    Bezárás
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** KÉTFÁZISÚ törlés gomb - szándékosan NEM a böngésző confirm() ablakával:
 * azt a böngésző el tudja némítani („további párbeszédablakok tiltása"),
 * és onnantól a gomb látszólag nem csinál semmit (a felhasználó hibajelzése).
 * Az első kattintás élesíti, a második töröl; pár másodperc után visszaáll. */
function TorlesGomb({
  adat,
  busy,
  setBusy,
  setHiba,
  onZaras,
}: {
  adat: BejovoSzamlaReszlet;
  busy: boolean;
  setBusy: (b: boolean) => void;
  setHiba: (h: string | null) => void;
  onZaras: () => void;
}) {
  const [elesitve, setElesitve] = useState(false);
  useEffect(() => {
    if (!elesitve) return;
    const t = setTimeout(() => setElesitve(false), 6000);
    return () => clearTimeout(t);
  }, [elesitve]);

  async function torles() {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/bejovo-szamlak/${adat.id}`, { method: "DELETE" });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setHiba(d?.detail ?? `Sikertelen törlés (${res.status})`);
        return;
      }
      onZaras();
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
      setElesitve(false);
    }
  }

  if (!elesitve) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => setElesitve(true)}
        className="rounded-[var(--radius)] border border-text-danger/50 px-3 py-1.5 text-[13px] text-text-danger hover:bg-text-danger/10 disabled:opacity-50"
      >
        Törlés
      </button>
    );
  }
  return (
    <span className="flex items-center gap-1.5">
      <button
        type="button"
        disabled={busy}
        onClick={() => void torles()}
        className="rounded-[var(--radius)] border border-text-danger bg-text-danger/15 px-3 py-1.5 text-[13px] font-medium text-text-danger hover:bg-text-danger/25 disabled:opacity-50"
      >
        {busy ? "Törlés…" : "Biztos? Törlés végleg"}
      </button>
      <button type="button" onClick={() => setElesitve(false)} className="text-[12px] text-text-muted hover:underline">
        mégse
      </button>
      <span className="text-[11.5px] text-text-muted">
        A piszkozat és a fájl törlődik{adat.allapot === "jovahagyva" ? "; a már rögzített tételeket nem érinti" : ""}.
      </span>
    </span>
  );
}
