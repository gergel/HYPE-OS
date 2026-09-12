"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Inbox, RefreshCw } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { formatHuf, formatSzam } from "@/lib/penz";
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
  jovahagyva: { cimke: "Jóváhagyva / rögzítve", tone: "success" },
  duplikatum: { cimke: "Duplikátum", tone: "neutral" },
  nem_szamla: { cimke: "Nem számla / elutasítva", tone: "neutral" },
  hiba: { cimke: "Feldolgozási hiba", tone: "danger" },
};

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
  egyeb: "Tisztázandó / egyéb",
};

type Valasztek = { projektkodok: { id: number; kod: string }[]; emberek: { id: number; nev: string }[]; autok: { id: number; nev: string }[] };

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
  const [szuro, setSzuro] = useState<string | null>(null);
  const [nyitottId, setNyitottId] = useState<number | null>(null);
  useEffect(() => setLista(kezdoLista), [kezdoLista]);
  // Mély-link az asszisztensből: ?id=123 rögtön a részletest nyitja.
  useEffect(() => {
    const id = searchParams.get("id");
    if (id) setNyitottId(Number(id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const darabok = useMemo(() => {
    const t: Record<string, number> = {};
    for (const b of lista) t[b.allapot] = (t[b.allapot] ?? 0) + 1;
    return t;
  }, [lista]);

  const szurt = szuro ? lista.filter((b) => b.allapot === szuro) : lista;

  return (
    <div className="space-y-4">
      <EmailSav canEdit={canEdit} onFrissul={() => router.refresh()} />

      {/* Állapot-szűrő chipek darabszámmal. */}
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setSzuro(null)}
          className={`rounded-[var(--radius)] px-2.5 py-1 text-[12px] ${szuro === null ? "bg-bg-accent text-text-accent" : "border border-border text-text-secondary hover:bg-surface-3"}`}
        >
          Mind ({lista.length})
        </button>
        {Object.entries(ALLAPOTOK).map(([kulcs, a]) => (
          <button
            key={kulcs}
            type="button"
            onClick={() => setSzuro(szuro === kulcs ? null : kulcs)}
            className={`rounded-[var(--radius)] px-2.5 py-1 text-[12px] ${szuro === kulcs ? "bg-bg-accent text-text-accent" : "border border-border text-text-secondary hover:bg-surface-3"}`}
          >
            {a.cimke} ({darabok[kulcs] ?? 0})
          </button>
        ))}
      </div>

      {szurt.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-text-secondary">
          <Inbox size={16} className="mr-1 inline" />
          Nincs ilyen állapotú beérkező számla. A szamla@ címre érkező levelek ide futnak be - és az AI
          Assistantba is bedobhatsz számlát.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b border-border text-left text-text-secondary">
                <th className="py-1.5 pr-3 font-medium">Forrás</th>
                <th className="py-1.5 pr-3 font-medium">Beérkezés</th>
                <th className="py-1.5 pr-3 font-medium">Kibocsátó</th>
                <th className="py-1.5 pr-3 font-medium">Számlaszám</th>
                <th className="py-1.5 pr-3 text-right font-medium">Összeg</th>
                <th className="py-1.5 pr-3 font-medium">Határidő</th>
                <th className="py-1.5 pr-3 font-medium">Javasolt cél</th>
                <th className="py-1.5 pr-3 font-medium">Állapot</th>
                <th className="py-1.5 font-medium">Felelős</th>
              </tr>
            </thead>
            <tbody>
              {szurt.map((b) => (
                <tr
                  key={b.id}
                  onClick={() => setNyitottId(b.id)}
                  className="cursor-pointer border-b border-border last:border-0 hover:bg-surface-3"
                >
                  <td className="py-2 pr-3 text-text-muted">
                    {b.forras === "email" ? "E-mail" : b.forras === "asszisztens" ? "Asszisztens" : "Kézi"}
                    {b.email_felado ? <span className="block max-w-[160px] truncate text-[11px]">{b.email_felado}</span> : null}
                  </td>
                  <td className="py-2 pr-3 text-text-secondary">
                    {huDatum((b.email_beerkezes ?? b.created_at).slice(0, 10))}
                  </td>
                  <td className="py-2 pr-3 text-text-primary">{b.kibocsato_nev ?? <span className="text-text-muted">–</span>}</td>
                  <td className="py-2 pr-3 text-text-secondary">{b.szamlaszam ?? "–"}</td>
                  <td className="py-2 pr-3 text-right tabular-nums text-text-primary">
                    {b.netto != null ? `${formatSzam(b.netto)} ${b.penznem}` : "–"}
                  </td>
                  <td className="py-2 pr-3 text-text-secondary">{b.fizetesi_hatarido ? huDatum(b.fizetesi_hatarido) : "–"}</td>
                  <td className="max-w-[220px] truncate py-2 pr-3 text-text-secondary" title={b.cel_cimke ?? undefined}>
                    {b.cel_cimke ?? (b.cel_tipus ? CEL_CIMKEK[b.cel_tipus] : "–")}
                  </td>
                  <td className="py-2 pr-3">
                    <StatusBadge label={ALLAPOTOK[b.allapot]?.cimke ?? b.allapot} tone={ALLAPOTOK[b.allapot]?.tone ?? "neutral"} />
                  </td>
                  <td className="py-2 text-text-secondary">{b.jovahagyo_nev ?? "–"}</td>
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
            router.refresh();
          }}
        />
      )}
    </div>
  );
}

/** Az e-mailes bekötés sávja: célcím, automatikus figyelés, kézi lehúzás
 * kezdődátummal és előnézettel (régi levelek visszamenőleges feldolgozása). */
function EmailSav({ canEdit, onFrissul }: { canEdit: boolean; onFrissul: () => void }) {
  const [adat, setAdat] = useState<{ cel_cim: string } | null>(null);
  const [kezdoDatum, setKezdoDatum] = useState("");
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [elonezet, setElonezet] = useState<{ felado: string; targy: string; csatolmanyok: string[] }[] | null>(null);

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
      const res = await authFetch("/api/v1/bejovo-szamlak/email-lehuzas", {
        method: "POST",
        body: JSON.stringify({ kezdo_datum: kezdoDatum || null, limit: 100, elonezet: csakElonezet }),
      });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        setUzenet(`Sikertelen: ${d?.detail ?? res.status}`);
        return;
      }
      if (csakElonezet) {
        setElonezet(d.elonezet ?? []);
        setUzenet(`${d.talalt_level} levél a keresésben - lent az előnézet (semmi nem jött létre).`);
      } else {
        setUzenet(`Kész: ${d.uj_level} új levél, ${d.uj_szamla} új dokumentum.`);
        onFrissul();
      }
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
            · csak kézi lehúzás, és csak az OLVASATLAN leveleket hozza be - magától semmit nem hoz át
          </span>
        </span>
        {canEdit && (
          <span className="ml-auto flex flex-wrap items-center gap-1.5">
            <label className="text-[11.5px] text-text-muted">Régi levelek ettől:</label>
            <input
              type="date"
              value={kezdoDatum}
              onChange={(e) => setKezdoDatum(e.target.value)}
              className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12px] text-text-primary focus:outline-none"
            />
            <button
              type="button"
              disabled={busy}
              onClick={() => lehuzas(true)}
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
              Lehúzás most
            </button>
          </span>
        )}
      </div>
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

/** A RÉSZLETES ELLENŐRZŐ: bal oldalon a számla előnézete, jobb oldalon a
 * kinyert (szerkeszthető) adatok, a kapcsolatok és a műveletek. */
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

  async function hivas(ut: string, body: unknown, method = "POST"): Promise<boolean> {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/bejovo-szamlak/${bejovoId}${ut}`, {
        method,
        body: JSON.stringify(body),
      });
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
    if (Object.keys(draft).length === 0) return true;
    return hivas("", mentendoMezok(), "PATCH");
  }

  async function jovahagyas() {
    // Előbb a függő mező-javítások, aztán a rögzítés - így a szerver a
    // felülvizsgált adatokkal dolgozik.
    if (!(await piszkozatMentes())) return;
    const body: Record<string, unknown> = {};
    if (arfolyam.trim()) body.arfolyam = Number(arfolyam.replace(",", "."));
    if (felosztas && felosztas.length > 0) {
      body.felosztas = felosztas.map((f) => ({
        project_code_id: f.project_code_id ? Number(f.project_code_id) : null,
        netto: Number((f.netto || "0").replace(/[  ]/g, "").replace(",", ".")),
      }));
    }
    await hivas("/jovahagyas", body);
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
  const lezart = adat.allapot === "jovahagyva" || adat.allapot === "nem_szamla";
  const cel = (draft.cel_tipus as string) ?? adat.cel_tipus ?? "";
  const devizas = (draft.penznem ?? adat.penznem) !== "HUF";
  const ujKoltseg = ["kiadas_uj", "mukodesi", "auto"].includes(cel);

  function mezo(nev: keyof BejovoSzamlaReszlet & string, cimke: string, tipus: "text" | "date" | "szam" = "text") {
    const ertek = draft[nev] ?? (adat![nev] != null ? String(adat![nev]) : "");
    const gyanus = bizonytalan.has(nev) || bizonytalan.has(nev.replace("_datuma", "")) || (nev === "netto" && bizonytalan.has("netto"));
    // A mező FORRÁSA: dokumentumból jött, vagy kézzel javított - az
    // ellenőrzésnél nem mindegy (a felhasználó előírása).
    const forras = draft[nev] !== undefined ? "felhasznalo" : forrasok[nev] ?? forrasok[nev.replace("kibocsato_nev", "kibocsato")];
    return (
      <div className="flex flex-col gap-0.5">
        <label className="flex items-center gap-1 text-[11px] text-text-muted">
          {cimke}
          {gyanus && <span className="rounded bg-bg-warning px-1 text-[10px] text-text-warning" title="A kiolvasás bizonytalan - ellenőrizd a dokumentumon">bizonytalan</span>}
          {forras === "felhasznalo" && <span className="text-[10px] text-text-accent" title="Kézzel javított érték">✎</span>}
        </label>
        <input
          type={tipus === "date" ? "date" : "text"}
          value={ertek}
          disabled={lezart || !canEdit}
          onChange={(e) => setDraft((p) => ({ ...p, [nev]: e.target.value }))}
          className={`rounded-[var(--radius)] border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none disabled:opacity-60 ${
            gyanus ? "border-text-warning/60" : "border-border"
          }`}
        />
      </div>
    );
  }

  const kep = (adat.content_type ?? "").startsWith("image/");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3" onMouseDown={onZaras}>
      <div
        onMouseDown={(e) => e.stopPropagation()}
        className="flex h-[92vh] w-full max-w-[1200px] flex-col overflow-hidden rounded-[var(--radius)] border border-border bg-surface-1"
      >
        <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
          <h2 className="text-[14px] font-medium text-text-primary">
            Beérkező számla #{adat.id} – {adat.kibocsato_nev ?? adat.fajl_nev ?? "?"}
          </h2>
          <StatusBadge label={ALLAPOTOK[adat.allapot]?.cimke ?? adat.allapot} tone={ALLAPOTOK[adat.allapot]?.tone ?? "neutral"} />
          {adat.dokumentum_tipus && adat.dokumentum_tipus !== "szamla" && (
            <StatusBadge label={adat.dokumentum_tipus} tone="warning" />
          )}
          <button type="button" onClick={onZaras} className="ml-auto rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3">
            Bezárás
          </button>
        </div>

        <div className="flex min-h-0 flex-1">
          {/* BAL: a számla előnézete. */}
          <div className="hidden w-1/2 border-r border-border bg-surface-2 md:block">
            {adat.url ? (
              kep ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={adat.url} alt="Számla" className="h-full w-full object-contain" />
              ) : (
                <iframe src={adat.url} title="Számla előnézet" className="h-full w-full" />
              )
            ) : (
              <div className="flex h-full items-center justify-center p-6 text-center text-[13px] text-text-muted">
                Nincs fájl - a levél csak letöltési linket tartalmazott. Az eredeti levél szövege jobbra, a
                „Levél” szakaszban olvasható; a számlát kézzel kell letölteni és az AI Assistantba bedobni.
              </div>
            )}
          </div>

          {/* JOBB: kinyert adatok + kapcsolatok + műveletek. */}
          <div className="w-full space-y-4 overflow-y-auto p-4 md:w-1/2">
            {hiba && <p className="rounded-[var(--radius)] border border-text-danger/50 bg-text-danger/10 px-3 py-2 text-[12.5px] text-text-danger">{hiba}</p>}
            {adat.hiba_uzenet && <p className="text-[12.5px] text-text-danger">Feldolgozási hiba: {adat.hiba_uzenet}</p>}
            {adat.javaslat?.figyelmeztetesek?.map((f, i) => (
              <p key={i} className="rounded-[var(--radius)] border border-text-warning/50 bg-bg-warning px-3 py-2 text-[12.5px] text-text-warning">
                {f}
              </p>
            ))}
            {adat.duplikatum_megjegyzes && <p className="text-[12.5px] text-text-warning">{adat.duplikatum_megjegyzes}</p>}

            {/* Kinyert adatok - szerkeszthetően, a bizonytalanok kiemelve. */}
            <section>
              <h3 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-text-muted">Számlaadatok</h3>
              <div className="grid grid-cols-2 gap-2">
                {mezo("kibocsato_nev", "Kibocsátó")}
                {mezo("kibocsato_adoszam", "Kibocsátó adószáma")}
                {mezo("szamlaszam", "Számlaszám")}
                {mezo("penznem", "Pénznem")}
                {mezo("netto", "Nettó", "szam")}
                {mezo("brutto", "Bruttó", "szam")}
                {mezo("kiallitas_datuma", "Kiállítás", "date")}
                {mezo("teljesites_datuma", "Teljesítés", "date")}
                {mezo("fizetesi_hatarido", "Fizetési határidő", "date")}
              </div>
              <p className="mt-1.5 text-[11px] text-text-muted">
                Vevő a számlán: {adat.vevo_nev ?? "–"} · irány: {adat.irany === "kimeno" ? "KIMENŐ (mi állítottuk ki)" : adat.irany === "bejovo" ? "bejövő" : "ismeretlen"}
                {" · "}a ✎ jel a kézzel javított mezőt jelöli, a többi a dokumentumból jött
              </p>
            </section>

            {/* A javaslat és az alternatívák. */}
            {adat.javaslat && !lezart && (
              <section>
                <h3 className="mb-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">Javaslat</h3>
                <p className="text-[12.5px] text-text-secondary">{adat.javaslat.indoklas}</p>
                {adat.javaslat.alternativak.length > 0 && (
                  <ul className="mt-1.5 space-y-1">
                    {adat.javaslat.alternativak.map((a, i) => (
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
                            void hivas("", { cel_tipus: a.tipus === "kiadas_uj" ? "kiadas_uj" : a.tipus, [mezoNev]: a.cel_id }, "PATCH");
                          }}
                          title={a.indoklas}
                          className="w-full rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-left text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                        >
                          <span className="text-text-primary">{a.cimke}</span>
                          <span className="block text-[11px] text-text-muted">{a.indoklas}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {/* A kiválasztott cél. */}
            <section>
              <h3 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-text-muted">Hová kerüljön</h3>
              <div className="space-y-2">
                <select
                  value={cel}
                  disabled={lezart || !canEdit}
                  onChange={(e) => void hivas("", { cel_tipus: e.target.value || null }, "PATCH")}
                  className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[12.5px] text-text-primary focus:outline-none disabled:opacity-60"
                >
                  <option value="">– válassz célt –</option>
                  {Object.entries(CEL_CIMKEK).map(([k, c]) => (
                    <option key={k} value={k}>
                      {c}
                    </option>
                  ))}
                </select>

                {ujKoltseg && cel !== "mukodesi" && (
                  <KeresosSelect
                    value={adat.cel_project_code_id != null ? String(adat.cel_project_code_id) : ""}
                    options={[
                      { value: "", label: "– nincs projektkód –" },
                      ...valasztek.projektkodok.map((p) => ({ value: String(p.id), label: p.kod })),
                    ]}
                    disabled={lezart || !canEdit || busy}
                    onChange={(v) => void hivas("", { cel_project_code_id: v ? Number(v) : null }, "PATCH")}
                  />
                )}
                {ujKoltseg && (
                  <KeresosSelect
                    value={adat.cel_employee_id != null ? String(adat.cel_employee_id) : ""}
                    options={[
                      { value: "", label: "– nincs számlázó fél (alvállalkozó) –" },
                      ...valasztek.emberek.map((e) => ({ value: String(e.id), label: e.nev })),
                    ]}
                    disabled={lezart || !canEdit || busy}
                    onChange={(v) => void hivas("", { cel_employee_id: v ? Number(v) : null }, "PATCH")}
                  />
                )}
                {cel === "auto" && (
                  <KeresosSelect
                    value={adat.cel_auto_id != null ? String(adat.cel_auto_id) : ""}
                    options={[
                      { value: "", label: "– válassz autót –" },
                      ...valasztek.autok.map((a) => ({ value: String(a.id), label: a.nev })),
                    ]}
                    disabled={lezart || !canEdit || busy}
                    onChange={(v) => void hivas("", { cel_auto_id: v ? Number(v) : null }, "PATCH")}
                  />
                )}
                {adat.cel_cimke && <p className="text-[12px] text-text-secondary">Kiválasztva: {adat.cel_cimke}</p>}

                {/* Egyértelmű jelzés + várható pénzügyi hatás. */}
                {cel && (
                  <p className="rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[12px] text-text-secondary">
                    {ujKoltseg ? (
                      <>
                        <b className="text-text-primary">ÚJ KÖLTSÉG készül</b> – jóváhagyás után{" "}
                        {adat.netto != null ? `${formatSzam(adat.netto)} ${adat.penznem} nettó` : "a megadott összegű"} kiadás
                        jön létre <b>nem kifizetett</b> állapotban{cel === "mukodesi" ? ", projektkód nélkül (tudatosan általános)" : ""}.
                        A kifizetés és a fedezet külön lépés marad.
                      </>
                    ) : (
                      <>
                        <b className="text-text-primary">MEGLÉVŐ tételhez csatolás</b> – új költség NEM jön létre, csak a
                        számla fájlja kerül a kiválasztott {CEL_CIMKEK[cel]} alá. A kifizetési állapot nem változik.
                      </>
                    )}
                  </p>
                )}

                {/* Felosztás több projekt közt - az összegeknek ki kell adniuk a nettót. */}
                {ujKoltseg && !lezart && canEdit && (
                  <div>
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
                          Felosztás - a rész-összegeknek pontosan ki kell adniuk a számla nettóját (
                          {adat.netto != null ? formatSzam(adat.netto) : "?"} {adat.penznem}). A számla egyetlen dokumentum
                          marad, az első tételhez csatolva.
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

                {devizas && ujKoltseg && !lezart && (
                  <div className="flex items-center gap-2">
                    <label className="text-[12px] text-text-muted">Árfolyam ({adat.penznem}→HUF), forrással a megjegyzésben:</label>
                    <input
                      value={arfolyam}
                      onChange={(e) => setArfolyam(e.target.value)}
                      placeholder="pl. 395,5"
                      className="w-24 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary"
                    />
                  </div>
                )}
              </div>
            </section>

            {/* A levél és az utasítás. */}
            {(adat.email_targy || adat.email_szoveg || adat.felhasznaloi_utasitas) && (
              <section>
                <h3 className="mb-1 text-[12px] font-medium uppercase tracking-wide text-text-muted">Levél / utasítás</h3>
                {adat.email_felado && (
                  <p className="text-[12px] text-text-muted">
                    Feladó: {adat.email_felado} · tárgy: {adat.email_targy} — a levél KÜLDŐJE nem azonos a számla
                    kibocsátójával.
                  </p>
                )}
                {adat.email_szoveg && <p className="mt-1 max-h-[90px] overflow-y-auto whitespace-pre-line text-[12px] text-text-secondary">{adat.email_szoveg}</p>}
                {adat.felhasznaloi_utasitas && (
                  <p className="mt-1 text-[12px] text-text-secondary">
                    <b>Utasítás:</b> {adat.felhasznaloi_utasitas}
                  </p>
                )}
              </section>
            )}

            {/* Jóváhagyás utáni napló + link. */}
            {adat.allapot === "jovahagyva" && adat.rogzites_naplo && (
              <section className="rounded-[var(--radius)] border border-border bg-surface-3 p-3 text-[12.5px] text-text-secondary">
                <p className="mb-1 font-medium text-text-primary">Rögzítve {adat.jovahagyo_nev ? `(${adat.jovahagyo_nev})` : ""}</p>
                {(adat.rogzites_naplo.letrejott ?? []).map((l, i) => (
                  <p key={i}>
                    Új {l.tipus === "expense" ? "kiadás" : l.tipus}: #{l.id}
                    {l.tipus === "expense" && (
                      <a href="/penzugyek" className="ml-2 text-text-accent hover:underline">
                        Megnyitás a Pénzügyekben →
                      </a>
                    )}
                  </p>
                ))}
                {(adat.rogzites_naplo.csatolt ?? []).length > 0 && <p>Csatolások: {JSON.stringify(adat.rogzites_naplo.csatolt)}</p>}
              </section>
            )}

            {/* MŰVELETEK. */}
            {!lezart && (
              <div className="flex flex-wrap gap-2 border-t border-border pt-3">
                {canCreate && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={jovahagyas}
                    className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
                  >
                    {busy ? "Folyamatban…" : "Jóváhagyás és rögzítés"}
                  </button>
                )}
                {canEdit && (
                  <>
                    <button type="button" disabled={busy || Object.keys(draft).length === 0} onClick={() => void piszkozatMentes()} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                      Piszkozat mentése
                    </button>
                    <button type="button" disabled={busy} onClick={() => void hivas("/duplikatum", {})} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                      Duplikátum
                    </button>
                    <button type="button" disabled={busy} onClick={() => void hivas("/nem-szamla", {})} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                      Nem számla
                    </button>
                    {(adat.allapot === "hiba" || adat.allapot === "feldolgozas") && (
                      <button type="button" disabled={busy} onClick={() => void hivas("/ujrafeldolgozas", {})} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50">
                        Újrafeldolgozás
                      </button>
                    )}
                  </>
                )}
              </div>
            )}

            {/* TÖRLÉS: bármelyik állapotban (a felhasználó kérése) - a
                piszkozat és a tárolt fájl végleg eltűnik. A jóváhagyáskor már
                létrejött kiadást/TIG-számlát NEM érinti: azok a saját
                felületükön élnek tovább. */}
            {canDelete && (
              <div className={lezart ? "border-t border-border pt-3" : ""}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    if (!confirm(`Törlöd ezt a beérkező számlát (#${adat.id})? A piszkozat és a tárolt fájl végleg törlődik.${adat.allapot === "jovahagyva" ? " A már rögzített kiadást/TIG-számlát ez nem érinti." : ""}`)) return;
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
                    }
                  }}
                  className="rounded-[var(--radius)] border border-text-danger/50 px-3 py-1.5 text-[13px] text-text-danger hover:bg-text-danger/10 disabled:opacity-50"
                >
                  Törlés
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
