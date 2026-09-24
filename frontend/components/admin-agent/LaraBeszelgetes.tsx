"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";

/** „Kérdezz Larától” — beszélgetés, tanítás és tudáspróba (kliens).
 *
 * - KÉRDEZZ: Lara a jóváhagyott tudásából és a rendszer csak-olvasó
 *   eszközeivel válaszol, a kérdező jogosultságával. Minden válasz mellett
 *   „Honnan tudom”: a hivatkozott tudás, a megnézett rekordok, a lépések.
 * - TANÍTSD: Lara megmutatja, MIT tanulna meg (fajta, állítás, hatókör,
 *   kivételek, érvényesség) — javítható, és csak mentésre kerül a tudásba.
 *   Általános szabályból csak piszkozat lesz; élesíteni a Tudástárban lehet.
 * - TUDÁSPRÓBA: vak jóslat a vizsgaügyeken (számla), és saját kérdés elvárt
 *   válasszal, amit Lara nem lát.
 * A beszélgetés CSAK OLVAS: Lara itt semmit nem küld, nem rögzít, nem hagy jóvá.
 * Lásd backend admin_agent/beszelgetes.py, tanitas.py, tudasproba.py. */

type Mod = "kerdez" | "tanit" | "proba";

type Forras = {
  cimke: string;
  rovat: string;
  fajta: string;
  id: number | null;
  cim: string | null;
  kivonat: string;
  link: string | null;
  hipotezis?: boolean;
};

type Elonezet = {
  fajta: string;
  allitas: string;
  hatokor: string;
  partner: string | null;
  projektkod: string | null;
  kivetelek: string[];
  ervenyes_tol: string | null;
  ervenyes_ig: string | null;
  tisztazo_kerdes: string | null;
  mi_lesz_belole?: string;
  modell?: boolean;
  meglevo_tudas?: { rovat: string; id: number | null; cim: string | null; kivonat: string }[];
};

type UzenetAdat = {
  tipus?: string;
  allapot?: string;
  modell?: boolean;
  hivatkozott?: string[];
  felhasznalt_tudas?: Forras[];
  lepesek?: { eszkoz: string; cel: string; ok: boolean }[];
  bizonyitekok?: { leiras: string; link: string | null }[];
  bizonyossag?: string | null;
  tisztazo_kerdes?: string | null;
  jelzesek?: string[];
  szemelyiseg_verzio?: string;
  elvart?: string;
  ido_ms?: number;
  elonezet?: Elonezet;
  mentve?: { tudas_id: number; allapot: string; szabaly_id: number | null; uzenet: string };
  tudas_id?: number;
  szabaly_id?: number | null;
};

type Uzenet = {
  id: number;
  szerep: "felhasznalo" | "lara";
  szoveg: string;
  adat: UzenetAdat;
  ertekeles: string | null;
  ertekeles_megjegyzes: string | null;
  letrehozva: string | null;
};

type BeszelgetesSor = { id: number; cim: string; mod: Mod; frissitve: string | null };

type Info = {
  beszelgetesek: BeszelgetesSor[];
  megszolitas: string | null;
  modell_elerheto: boolean;
  szemelyiseg_verzio: string;
  jogok: string[];
};

const MOD_CIMKE: Record<Mod, string> = { kerdez: "Kérdezz", tanit: "Tanítsd", proba: "Tudáspróba" };
const FAJTA_CIMKE: Record<string, string> = {
  eseti_magyarazat: "Eseti magyarázat",
  kivetel: "Kivétel",
  fogalom: "Fogalom",
  altalanos_szabaly: "Általános szabály",
};
const FAJTA_LEIRAS: Record<string, string> = {
  eseti_magyarazat: "Miért volt így EGY adott esetben — nem általánosítom.",
  kivetel: "Egy partnerre / helyzetre szóló eltérés a szokásostól.",
  fogalom: "Mit jelent valami a HYPE-nál.",
  altalanos_szabaly: "Mindig így kell. Ebből szabály-piszkozat is lesz, de nem élesedik magától.",
};
const HATOKOR_CIMKE: Record<string, string> = {
  szamla: "Számla",
  tig: "TIG",
  szerzodes: "Szerződés",
  email: "E-mail",
  kintlevoseg: "Kintlevőség",
  rendszer: "Rendszer / fogalmak",
  egyeb: "Egyéb adminisztráció",
};
const ROVAT_CIMKE: Record<string, string> = {
  szabalyok: "Éles szabály",
  kivetelek: "Kivétel",
  rendszerismeret: "Rendszerismeret",
  hasonlo_esetek: "Korábbi eset",
};
const TUDAS_FAJTA_CIMKE: Record<string, string> = {
  kezikonyv_uzleti: "jóváhagyott üzleti eljárás",
  kezikonyv_technikai: "technikai leírás",
  projektkod_eletut: "projektkód életútja",
  eseti_magyarazat: "eseti magyarázat",
  fogalom: "fogalom",
  kivetel: "kivétel",
  szabaly_allitas: "szabály-állítás",
  teny: "tény",
  tanulsag: "tanulság",
  profil: "partner-profil",
};
const BIZONYOSSAG: Record<string, { cimke: string; osztaly: string }> = {
  biztos: { cimke: "Biztos", osztaly: "bg-bg-success text-text-success" },
  valoszinu: { cimke: "Valószínű", osztaly: "bg-bg-accent text-text-accent" },
  bizonytalan: { cimke: "Bizonytalan", osztaly: "bg-bg-warning text-text-warning" },
};
const JELZES_CIMKE: Record<string, string> = {
  emoji_torolve: "emoji törölve",
  tiltott_nev: "tiltott elnevezés a válaszban",
  ismeretlen_hivatkozas_eldobva: "nem kapott forrásra hivatkozott — eldobva",
};

function jelzesSzoveg(j: string): string {
  if (JELZES_CIMKE[j]) return JELZES_CIMKE[j];
  if (j.startsWith("hamis_vegrehajtas_gyanu:")) return `végrehajtást állított („${j.split(":")[1]}”), pedig itt csak olvashat`;
  if (j.startsWith("sablon_nyitas_torolve:")) return "sablonos nyitás törölve";
  if (j.startsWith("tiltott_fordulat:")) return `kerülendő fordulat: „${j.split(":")[1]}”`;
  return j;
}

async function kuldJson<T>(url: string, method: string, body?: unknown): Promise<{ ok: boolean; adat: T; hiba?: string }> {
  const res = await authFetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const adat = (await res.json().catch(() => ({}))) as T & { detail?: unknown };
  if (!res.ok) {
    const d = (adat as { detail?: unknown }).detail;
    return {
      ok: false,
      adat,
      hiba:
        res.status === 423
          ? "Lara le van állítva (vészleállítás) — most nem válaszol."
          : typeof d === "string"
            ? d
            : "A kérés nem sikerült.",
    };
  }
  return { ok: true, adat };
}

export function LaraBeszelgetes({ canEdit }: { canEdit: boolean }) {
  const [mod, setMod] = useState<Mod>("kerdez");
  const [info, setInfo] = useState<Info | null>(null);
  const [aktivId, setAktivId] = useState<number | null>(null);
  const [uzenetek, setUzenetek] = useState<Uzenet[]>([]);
  const [szoveg, setSzoveg] = useState("");
  const [elvart, setElvart] = useState("");
  const [tanitasHatokor, setTanitasHatokor] = useState("");
  const [tanitasPartner, setTanitasPartner] = useState("");
  const [kapcsolodo, setKapcsolodo] = useState<number | null>(null);
  const [kuld, setKuld] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const aljaRef = useRef<HTMLDivElement | null>(null);

  const listaBetoltes = useCallback(async () => {
    const r = await kuldJson<Info>("/api/v1/admin-agent/chat", "GET");
    if (r.ok) setInfo(r.adat);
  }, []);

  useEffect(() => {
    let el = false;
    void kuldJson<Info>("/api/v1/admin-agent/chat", "GET").then((r) => {
      if (!el && r.ok) setInfo(r.adat);
    });
    return () => {
      el = true;
    };
  }, []);

  const megnyit = useCallback(async (id: number) => {
    setHiba(null);
    const r = await kuldJson<{ uzenetek: Uzenet[] }>(`/api/v1/admin-agent/chat/${id}`, "GET");
    if (!r.ok) {
      setHiba(r.hiba ?? "A beszélgetés nem tölthető be.");
      return;
    }
    setAktivId(id);
    setUzenetek(r.adat.uzenetek);
  }, []);

  useEffect(() => {
    aljaRef.current?.scrollIntoView({ block: "end" });
  }, [uzenetek.length]);

  const sajatLista = (info?.beszelgetesek ?? []).filter((b) => b.mod === mod);

  function modValtas(uj: Mod) {
    setMod(uj);
    setAktivId(null);
    setUzenetek([]);
    setHiba(null);
  }

  async function ujBeszelgetes(): Promise<number | null> {
    const r = await kuldJson<{ id: number }>("/api/v1/admin-agent/chat", "POST", { mod });
    if (!r.ok) {
      setHiba(r.hiba ?? "Nem sikerült új beszélgetést nyitni.");
      return null;
    }
    setAktivId(r.adat.id);
    setUzenetek([]);
    void listaBetoltes();
    return r.adat.id;
  }

  async function kuldes() {
    const s = szoveg.trim();
    if (!s || kuld) return;
    setKuld(true);
    setHiba(null);
    try {
      const id = aktivId ?? (await ujBeszelgetes());
      if (id === null) return;
      if (mod === "tanit") {
        const r = await kuldJson<{ kerdes: Uzenet; valasz: Uzenet }>(`/api/v1/admin-agent/chat/${id}/tanitas`, "POST", {
          szoveg: s,
          hatokor: tanitasHatokor || null,
          partner: tanitasPartner.trim() || null,
          kapcsolodo_uzenet_id: kapcsolodo,
        });
        if (!r.ok) {
          setHiba(r.hiba ?? "Az előnézet nem készült el.");
          return;
        }
        setUzenetek((u) => [...u, r.adat.kerdes, r.adat.valasz]);
        setKapcsolodo(null);
      } else {
        const r = await kuldJson<{ kerdes: Uzenet; valasz: Uzenet }>(`/api/v1/admin-agent/chat/${id}/uzenet`, "POST", {
          szoveg: s,
          elvart: mod === "proba" && elvart.trim() ? elvart.trim() : null,
        });
        if (!r.ok) {
          setHiba(r.hiba ?? "Lara most nem tudott válaszolni.");
          return;
        }
        setUzenetek((u) => [...u, r.adat.kerdes, r.adat.valasz]);
        setElvart("");
      }
      setSzoveg("");
      void listaBetoltes();
    } finally {
      setKuld(false);
    }
  }

  function tanitasbol(u: Uzenet, megjegyzes: string) {
    const kerdes = uzenetek[uzenetek.findIndex((x) => x.id === u.id) - 1];
    setMod("tanit");
    setAktivId(null);
    setUzenetek([]);
    setKapcsolodo(u.id);
    setSzoveg(
      [kerdes ? `Kérdés: ${kerdes.szoveg}` : "", megjegyzes ? `A helyes válasz: ${megjegyzes}` : "A helyes válasz: "]
        .filter(Boolean)
        .join("\n"),
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Fejlec info={info} onMentve={listaBetoltes} />

      <div className="flex flex-wrap gap-1.5">
        {(Object.keys(MOD_CIMKE) as Mod[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => modValtas(m)}
            className={`rounded-[var(--radius)] border px-3 py-1.5 text-[13px] ${
              mod === m
                ? "border-border bg-surface-4 text-text-primary"
                : "border-transparent text-text-secondary hover:bg-surface-3"
            }`}
          >
            {MOD_CIMKE[m]}
          </button>
        ))}
      </div>

      {mod === "proba" && <SzamlaVizsga canRun={canEdit} />}

      {mod === "tanit" && !canEdit ? (
        <p className="text-[13px] text-text-secondary">A tanításhoz szerkesztési jogosultság kell a Lara oldalon.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => {
                setAktivId(null);
                setUzenetek([]);
                setHiba(null);
              }}
              className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent"
            >
              Új {mod === "tanit" ? "tanítás" : mod === "proba" ? "próbakérdés" : "beszélgetés"}
            </button>
            {sajatLista.length === 0 ? (
              <p className="text-[12px] text-text-muted">Még nincs korábbi {MOD_CIMKE[mod].toLowerCase()}-beszélgetés.</p>
            ) : (
              <ul className="flex max-h-[60vh] flex-col gap-1 overflow-y-auto">
                {sajatLista.map((b) => (
                  <li key={b.id}>
                    <button
                      type="button"
                      onClick={() => void megnyit(b.id)}
                      className={`w-full truncate rounded-[var(--radius)] px-2.5 py-1.5 text-left text-[13px] ${
                        aktivId === b.id ? "bg-surface-4 text-text-primary" : "text-text-secondary hover:bg-surface-3"
                      }`}
                      title={b.cim}
                    >
                      {b.cim}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex min-h-[420px] flex-col rounded-[var(--radius-lg)] border border-border bg-surface-2">
            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {uzenetek.length === 0 && <Ures mod={mod} />}
              {uzenetek.map((u) =>
                u.szerep === "felhasznalo" ? (
                  <div key={u.id} className="flex justify-end">
                    <div className="max-w-[85%] whitespace-pre-wrap rounded-[var(--radius)] bg-surface-4 px-3 py-2 text-[13px] text-text-primary">
                      {u.szoveg}
                    </div>
                  </div>
                ) : (
                  <LaraUzenet
                    key={u.id}
                    u={u}
                    beszelgetesId={aktivId}
                    canEdit={canEdit}
                    onFrissult={(uj) => setUzenetek((l) => l.map((x) => (x.id === uj.id ? uj : x)))}
                    onUjUzenet={() => aktivId && void megnyit(aktivId)}
                    onTanitas={tanitasbol}
                  />
                ),
              )}
              {kuld && <p className="text-[12px] text-text-muted">Lara utánanéz…</p>}
              <div ref={aljaRef} />
            </div>

            <div className="border-t border-border p-3">
              {hiba && (
                <div className="mb-2 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>
              )}
              {mod === "tanit" && (
                <div className="mb-2 grid gap-2 sm:grid-cols-2">
                  <select
                    value={tanitasHatokor}
                    onChange={(e) => setTanitasHatokor(e.target.value)}
                    className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary"
                  >
                    <option value="">Terület: Lara döntse el</option>
                    {Object.entries(HATOKOR_CIMKE).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                  <input
                    value={tanitasPartner}
                    onChange={(e) => setTanitasPartner(e.target.value)}
                    placeholder="Partner (ha egy partnerre szól)"
                    className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary"
                  />
                </div>
              )}
              {mod === "proba" && (
                <textarea
                  value={elvart}
                  onChange={(e) => setElvart(e.target.value)}
                  rows={2}
                  placeholder="Elvárt válasz (nem kötelező) — Lara nem látja, csak te veted össze a válaszával."
                  className="mb-2 w-full resize-y rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary"
                />
              )}
              <div className="flex gap-2">
                <textarea
                  value={szoveg}
                  onChange={(e) => setSzoveg(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void kuldes();
                    }
                  }}
                  rows={mod === "tanit" ? 3 : 2}
                  placeholder={
                    mod === "tanit"
                      ? "Mit tanuljon meg Lara? Pl. „A Kovács Kft. számláinál nem kell TIG, mert átalánydíjas.”"
                      : mod === "proba"
                        ? "Próbakérdés Larának…"
                        : "Kérdezz Larától (pl. „Hová szoktuk tenni a Kovács Kft. számláit?”)"
                  }
                  className="flex-1 resize-y rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary"
                />
                <button
                  type="button"
                  disabled={kuld || !szoveg.trim()}
                  onClick={() => void kuldes()}
                  className="self-end rounded-[var(--radius)] bg-bg-accent px-4 py-2 text-[13px] font-medium text-text-accent disabled:opacity-50"
                >
                  {mod === "tanit" ? "Előnézet" : "Küldés"}
                </button>
              </div>
              <p className="mt-1.5 text-[11px] text-text-muted">
                {mod === "tanit"
                  ? "Semmi nem kerül a tudásba, amíg az előnézetet nem mented."
                  : "Lara itt csak olvas: nem küld, nem rögzít, nem hagy jóvá semmit."}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Fejlec({ info, onMentve }: { info: Info | null; onMentve: () => void }) {
  const [szerk, setSzerk] = useState(false);
  const [nev, setNev] = useState("");
  const [hiba, setHiba] = useState<string | null>(null);

  async function ment() {
    const r = await kuldJson<{ megszolitas: string | null }>("/api/v1/admin-agent/chat/preferences", "PATCH", {
      megszolitas: nev.trim() || null,
    });
    if (!r.ok) {
      setHiba(r.hiba ?? "Nem sikerült menteni.");
      return;
    }
    setSzerk(false);
    setHiba(null);
    onMentve();
  }

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-text-muted">
      <span>
        Nyelvi modell:{" "}
        {info === null ? (
          "…"
        ) : info.modell_elerheto ? (
          <span className="text-text-success">elérhető</span>
        ) : (
          <span className="text-text-warning">nincs beállítva — Lara csak a jóváhagyott tudásából idéz</span>
        )}
      </span>
      <span>Személyiség: {info?.szemelyiseg_verzio ?? "…"}</span>
      {szerk ? (
        <span className="flex items-center gap-1.5">
          <input
            value={nev}
            onChange={(e) => setNev(e.target.value)}
            maxLength={40}
            placeholder="pl. Geri (üresen: ne szólítson néven)"
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary"
          />
          <button type="button" onClick={() => void ment()} className="text-text-accent hover:underline">
            Mentés
          </button>
          <button type="button" onClick={() => setSzerk(false)} className="hover:underline">
            Mégse
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={() => {
            setNev(info?.megszolitas ?? "");
            setSzerk(true);
          }}
          className="hover:underline"
        >
          Megszólítás: {info?.megszolitas ? `„${info.megszolitas}”` : "nincs beállítva"} (módosítás)
        </button>
      )}
      {hiba && <span className="text-text-danger">{hiba}</span>}
    </div>
  );
}

function Ures({ mod }: { mod: Mod }) {
  const szoveg: Record<Mod, string> = {
    kerdez:
      "Kérdezz bármit a HYPE OS adminisztrációjáról: partnerek szokásai, számlák, papírok, fogalmak. Lara a jóváhagyott tudásából és a rendszer adataiból válaszol, és megmutatja, honnan tudja.",
    tanit:
      "Írd le, mit tanuljon meg Lara. Mentés előtt megmutatja, hogyan értette: eseti magyarázatnak, kivételnek, fogalomnak vagy általános szabálynak — és mire vonatkozik.",
    proba:
      "Tedd próbára Larát: kérdezz tőle olyat, amire tudod a választ, és add meg az elvárt választ is. Ő nem látja — te veted össze, és értékeled.",
  };
  return <p className="text-[13px] text-text-secondary">{szoveg[mod]}</p>;
}

function LaraUzenet({
  u,
  beszelgetesId,
  canEdit,
  onFrissult,
  onUjUzenet,
  onTanitas,
}: {
  u: Uzenet;
  beszelgetesId: number | null;
  canEdit: boolean;
  onFrissult: (u: Uzenet) => void;
  onUjUzenet: () => void;
  onTanitas: (u: Uzenet, megjegyzes: string) => void;
}) {
  const a = u.adat ?? {};
  if (a.tipus === "tanitas_elonezet" && a.elonezet) {
    return (
      <ElonezetKartya
        u={u}
        beszelgetesId={beszelgetesId}
        canEdit={canEdit}
        onMentve={onUjUzenet}
      />
    );
  }
  if (a.tipus === "tanitas_mentve") {
    return (
      <div className="max-w-[85%] rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">
        {u.szoveg}
        {a.szabaly_id ? (
          <>
            {" "}
            <Link href="/admin-agent/tudastar" className="underline">
              Szabály-piszkozat a Tudástárban
            </Link>
          </>
        ) : null}
      </div>
    );
  }
  const biz = a.bizonyossag ? BIZONYOSSAG[a.bizonyossag] : null;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 text-[11px] text-text-muted">
        <span className="font-medium text-text-secondary">Lara</span>
        {biz && <span className={`rounded-[var(--radius)] px-1.5 py-0.5 ${biz.osztaly}`}>{biz.cimke}</span>}
        {a.allapot === "modell_nelkul" && <span>modell nélkül — csak a jóváhagyott tudás</span>}
        {a.allapot && !["kesz", "modell_nelkul"].includes(a.allapot) && (
          <span className="text-text-warning">a válasz nem készült el teljesen ({a.allapot})</span>
        )}
      </div>
      <div className={a.elvart ? "grid gap-2 md:grid-cols-2" : ""}>
        <div className="max-w-[85%] whitespace-pre-wrap rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary md:max-w-none">
          {u.szoveg}
          {a.tisztazo_kerdes && (
            <p className="mt-2 border-t border-border pt-2 text-text-accent">Kérdésem: {a.tisztazo_kerdes}</p>
          )}
        </div>
        {a.elvart && (
          <div className="whitespace-pre-wrap rounded-[var(--radius)] border border-dashed border-border px-3 py-2 text-[13px] text-text-secondary">
            <span className="mb-1 block text-[11px] text-text-muted">Elvárt válasz (Lara nem látta)</span>
            {a.elvart}
          </div>
        )}
      </div>
      <HonnanTudom a={a} />
      <Ertekeles u={u} canEdit={canEdit} onFrissult={onFrissult} onTanitas={onTanitas} />
    </div>
  );
}

function HonnanTudom({ a }: { a: UzenetAdat }) {
  const [nyitva, setNyitva] = useState(false);
  const tudas = a.felhasznalt_tudas ?? [];
  const hivatkozott = new Set(a.hivatkozott ?? []);
  const lepesek = a.lepesek ?? [];
  const bizonyitekok = a.bizonyitekok ?? [];
  const jelzesek = (a.jelzesek ?? []).filter((j) => !j.startsWith("sablon_nyitas") && j !== "emoji_torolve");
  if (!tudas.length && !lepesek.length && !bizonyitekok.length && !jelzesek.length) {
    return <p className="text-[11px] text-text-muted">Ehhez nem talált jóváhagyott tudást, és nem nézett utána a rendszerben.</p>;
  }
  const sorrend = [...tudas].sort((x, y) => Number(hivatkozott.has(y.cimke)) - Number(hivatkozott.has(x.cimke)));
  return (
    <div className="text-[12px]">
      <button type="button" onClick={() => setNyitva((v) => !v)} className="text-text-accent hover:underline">
        {nyitva ? "Honnan tudom — elrejt" : `Honnan tudom (${hivatkozott.size} hivatkozott forrás, ${lepesek.length} lépés)`}
      </button>
      {nyitva && (
        <div className="mt-1.5 flex flex-col gap-2 rounded-[var(--radius)] border border-border bg-surface-2 p-2.5">
          {jelzesek.length > 0 && (
            <div className="rounded-[var(--radius)] bg-bg-warning px-2 py-1 text-text-warning">
              Figyelem: {jelzesek.map(jelzesSzoveg).join("; ")}
            </div>
          )}
          {sorrend.length > 0 && (
            <ul className="flex flex-col gap-1">
              {sorrend.map((t) => (
                <li key={t.cimke} className={hivatkozott.has(t.cimke) ? "text-text-primary" : "text-text-muted"}>
                  <span className="mr-1.5 rounded bg-surface-4 px-1 font-mono text-[11px]">{t.cimke}</span>
                  <span className="mr-1">{ROVAT_CIMKE[t.rovat] ?? t.rovat}</span>
                  {TUDAS_FAJTA_CIMKE[t.fajta] && !["kivetelek", "szabalyok"].includes(t.rovat) && (
                    <span className="mr-1">({TUDAS_FAJTA_CIMKE[t.fajta]})</span>
                  )}
                  {t.hipotezis && <span className="mr-1 text-text-warning">hipotézis</span>}
                  {t.cim && <span className="mr-1 font-medium">{t.cim}:</span>}
                  <span>{t.kivonat}</span>
                  {t.link && (
                    <Link href={t.link} className="ml-1 text-text-accent hover:underline">
                      megnyit
                    </Link>
                  )}
                  {!hivatkozott.has(t.cimke) && <span className="ml-1 italic">— megkapta, de nem erre épített</span>}
                </li>
              ))}
            </ul>
          )}
          {lepesek.length > 0 && (
            <div>
              <p className="mb-0.5 text-text-muted">Utánanézett a rendszerben (a te jogosultságoddal):</p>
              <ul className="flex flex-col gap-0.5 text-text-secondary">
                {lepesek.map((l, i) => (
                  <li key={i}>
                    {l.ok ? "✓" : "✗"} {l.cel}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {bizonyitekok.length > 0 && (
            <div>
              <p className="mb-0.5 text-text-muted">Amit megnézett:</p>
              <ul className="flex flex-col gap-0.5 text-text-secondary">
                {bizonyitekok.map((b, i) => (
                  <li key={i}>
                    {b.leiras}
                    {b.link && (
                      <Link href={b.link} className="ml-1 text-text-accent hover:underline">
                        megnyit
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {a.ido_ms !== undefined && <p className="text-[11px] text-text-muted">Válaszidő: {(a.ido_ms / 1000).toFixed(1)} mp</p>}
        </div>
      )}
    </div>
  );
}

function Ertekeles({
  u,
  canEdit,
  onFrissult,
  onTanitas,
}: {
  u: Uzenet;
  canEdit: boolean;
  onFrissult: (u: Uzenet) => void;
  onTanitas: (u: Uzenet, megjegyzes: string) => void;
}) {
  const [valasztott, setValasztott] = useState<string | null>(null);
  const [megjegyzes, setMegjegyzes] = useState("");
  const [hiba, setHiba] = useState<string | null>(null);

  async function ment(ertekeles: string, szoveg: string | null) {
    const r = await kuldJson<Uzenet>(`/api/v1/admin-agent/chat/uzenet/${u.id}/ertekeles`, "POST", {
      ertekeles,
      megjegyzes: szoveg,
    });
    if (!r.ok) {
      setHiba(r.hiba ?? "Nem sikerült menteni.");
      return;
    }
    setValasztott(null);
    onFrissult(r.adat);
  }

  if (u.ertekeles) {
    const c = { helyes: "Helyes", reszben: "Részben helyes", hibas: "Hibás" }[u.ertekeles] ?? u.ertekeles;
    return (
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
        <span>
          Értékelésed: <span className="text-text-secondary">{c}</span>
          {u.ertekeles_megjegyzes ? ` — ${u.ertekeles_megjegyzes}` : ""}
        </span>
        {canEdit && u.ertekeles !== "helyes" && (
          <button type="button" onClick={() => onTanitas(u, u.ertekeles_megjegyzes ?? "")} className="text-text-accent hover:underline">
            Tanítsd meg Larának a helyeset
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1 text-[11px]">
      <div className="flex flex-wrap items-center gap-1.5 text-text-muted">
        <span>Jó volt a válasz?</span>
        <button
          type="button"
          onClick={() => void ment("helyes", null)}
          className="rounded-[var(--radius)] border border-border px-2 py-0.5 hover:bg-surface-3"
        >
          Helyes
        </button>
        <button
          type="button"
          onClick={() => setValasztott("reszben")}
          className={`rounded-[var(--radius)] border border-border px-2 py-0.5 hover:bg-surface-3 ${valasztott === "reszben" ? "bg-surface-4" : ""}`}
        >
          Részben
        </button>
        <button
          type="button"
          onClick={() => setValasztott("hibas")}
          className={`rounded-[var(--radius)] border border-border px-2 py-0.5 hover:bg-surface-3 ${valasztott === "hibas" ? "bg-surface-4" : ""}`}
        >
          Hibás
        </button>
      </div>
      {valasztott && (
        <div className="flex flex-wrap items-center gap-1.5">
          <input
            value={megjegyzes}
            onChange={(e) => setMegjegyzes(e.target.value)}
            placeholder="Mi lett volna a helyes? (nem kötelező)"
            className="min-w-[240px] flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary"
          />
          <button type="button" onClick={() => void ment(valasztott, megjegyzes.trim() || null)} className="text-text-accent hover:underline">
            Mentés
          </button>
        </div>
      )}
      {hiba && <span className="text-text-danger">{hiba}</span>}
    </div>
  );
}

function ElonezetKartya({
  u,
  beszelgetesId,
  canEdit,
  onMentve,
}: {
  u: Uzenet;
  beszelgetesId: number | null;
  canEdit: boolean;
  onMentve: () => void;
}) {
  const e0 = u.adat.elonezet as Elonezet;
  const mentve = u.adat.mentve;
  const [e, setE] = useState<Elonezet>(e0);
  const [kivetelek, setKivetelek] = useState((e0.kivetelek ?? []).join("\n"));
  const [fut, setFut] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function ment() {
    if (!beszelgetesId) return;
    setFut(true);
    setHiba(null);
    try {
      const r = await kuldJson<{ uzenet: string }>(
        `/api/v1/admin-agent/chat/${beszelgetesId}/tanitas/${u.id}/mentes`,
        "POST",
        {
          modositott: {
            fajta: e.fajta,
            allitas: e.allitas,
            hatokor: e.hatokor,
            partner: e.partner || null,
            projektkod: e.projektkod || null,
            kivetelek: kivetelek
              .split("\n")
              .map((x) => x.trim())
              .filter(Boolean),
            ervenyes_tol: e.ervenyes_tol || null,
            ervenyes_ig: e.ervenyes_ig || null,
          },
        },
      );
      if (!r.ok) {
        setHiba(r.hiba ?? "Nem sikerült menteni.");
        return;
      }
      onMentve();
    } finally {
      setFut(false);
    }
  }

  const mezo = "rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary disabled:opacity-60";
  const tiltva = !!mentve || !canEdit;
  return (
    <div className="flex flex-col gap-2 rounded-[var(--radius)] border border-border bg-surface-3 p-3 text-[13px]">
      <p className="text-text-primary">{u.szoveg}</p>
      {!e0.modell && (
        <p className="text-[11px] text-text-muted">
          A nyelvi modell most nem érhető el: az előnézet kulcsszavakból készült — nézd át a fajtát.
        </p>
      )}
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Milyen tudás ez?
          <select value={e.fajta} disabled={tiltva} onChange={(x) => setE({ ...e, fajta: x.target.value })} className={mezo}>
            {Object.entries(FAJTA_CIMKE).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <span>{FAJTA_LEIRAS[e.fajta]}</span>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Terület
          <select value={e.hatokor} disabled={tiltva} onChange={(x) => setE({ ...e, hatokor: x.target.value })} className={mezo}>
            {Object.entries(HATOKOR_CIMKE).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted sm:col-span-2">
          Az állítás (egy mondatban)
          <textarea
            value={e.allitas}
            disabled={tiltva}
            rows={2}
            onChange={(x) => setE({ ...e, allitas: x.target.value })}
            className={mezo}
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Partner
          <input value={e.partner ?? ""} disabled={tiltva} onChange={(x) => setE({ ...e, partner: x.target.value })} className={mezo} />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Projektkód
          <input
            value={e.projektkod ?? ""}
            disabled={tiltva}
            onChange={(x) => setE({ ...e, projektkod: x.target.value })}
            className={mezo}
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted sm:col-span-2">
          Kivételek (soronként egy)
          <textarea value={kivetelek} disabled={tiltva} rows={2} onChange={(x) => setKivetelek(x.target.value)} className={mezo} />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Érvényes ettől
          <input
            type="date"
            value={e.ervenyes_tol ?? ""}
            disabled={tiltva}
            onChange={(x) => setE({ ...e, ervenyes_tol: x.target.value })}
            className={mezo}
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Érvényes eddig
          <input
            type="date"
            value={e.ervenyes_ig ?? ""}
            disabled={tiltva}
            onChange={(x) => setE({ ...e, ervenyes_ig: x.target.value })}
            className={mezo}
          />
        </label>
      </div>
      {e0.mi_lesz_belole && <p className="text-[12px] text-text-secondary">{e0.mi_lesz_belole}</p>}
      {(e0.meglevo_tudas ?? []).length > 0 && (
        <div className="text-[12px] text-text-muted">
          <p>Ehhez kapcsolódó, amit már tudok:</p>
          <ul className="ml-4 list-disc">
            {(e0.meglevo_tudas ?? []).map((t, i) => (
              <li key={i}>
                {ROVAT_CIMKE[t.rovat] ?? t.rovat}: {t.cim ? `${t.cim} — ` : ""}
                {t.kivonat}
              </li>
            ))}
          </ul>
        </div>
      )}
      {hiba && <div className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-text-danger">{hiba}</div>}
      {mentve ? (
        <p className="text-[12px] text-text-success">{mentve.uzenet}</p>
      ) : canEdit ? (
        <div>
          <button
            type="button"
            disabled={fut}
            onClick={() => void ment()}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            {fut ? "Mentés…" : "Így tanuld meg"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

type VizsgaEset = {
  bejovo_id: number;
  partner: string | null;
  valosag: string;
  lara: string | null;
  forras: string | null;
  eredmeny: "helyes" | "reszben" | "hibas" | "nem_tudja";
  szennyezett_lehet: boolean;
  link: string;
};

type Vizsga = {
  esetszam: number;
  helyes: number;
  reszben: number;
  hibas: number;
  nem_tudja: number;
  lefedettseg: number | null;
  pontossag: number | null;
  szennyezett: boolean;
  esetek?: VizsgaEset[];
};

const EREDMENY_CIMKE: Record<string, { cimke: string; osztaly: string }> = {
  helyes: { cimke: "Helyes", osztaly: "text-text-success" },
  reszben: { cimke: "Részben", osztaly: "text-text-accent" },
  hibas: { cimke: "Hibás", osztaly: "text-text-danger" },
  nem_tudja: { cimke: "Nem tudta — kérdezett volna", osztaly: "text-text-muted" },
};

function szazalek(x: number | null | undefined): string {
  return x === null || x === undefined ? "nincs adat" : `${Math.round(x * 100)}%`;
}

function probaLekeres() {
  return kuldJson<{ futasok: (Vizsga & { id: number; ido: string | null })[]; vizsgakeszlet: boolean }>(
    "/api/v1/admin-agent/tudasproba",
    "GET",
  );
}

function SzamlaVizsga({ canRun }: { canRun: boolean }) {
  const [esetszam, setEsetszam] = useState(20);
  const [eredmeny, setEredmeny] = useState<Vizsga | null>(null);
  const [korabbiak, setKorabbiak] = useState<(Vizsga & { id: number; ido: string | null })[]>([]);
  const [elkulonitve, setElkulonitve] = useState<boolean | null>(null);
  const [fut, setFut] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(async () => {
    const r = await probaLekeres();
    if (r.ok) {
      setKorabbiak(r.adat.futasok);
      setElkulonitve(r.adat.vizsgakeszlet);
    }
  }, []);

  useEffect(() => {
    let el = false;
    void probaLekeres().then((r) => {
      if (el || !r.ok) return;
      setKorabbiak(r.adat.futasok);
      setElkulonitve(r.adat.vizsgakeszlet);
    });
    return () => {
      el = true;
    };
  }, []);

  async function futtat() {
    setFut(true);
    setHiba(null);
    try {
      const r = await kuldJson<Vizsga>("/api/v1/admin-agent/tudasproba/szamla", "POST", { esetszam });
      if (!r.ok) {
        setHiba(r.hiba ?? "A próba nem futott le.");
        return;
      }
      setEredmeny(r.adat);
      void betolt();
    } finally {
      setFut(false);
    }
  }

  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
      <h3 className="mb-1 text-[14px] font-medium text-text-primary">Számla-vizsga — vak jóslat</h3>
      <p className="mb-3 text-[12px] text-text-muted">
        A jóváhagyott számlák egy állandó része vizsgaeset (üzleti ügyenként). Lara ezekre úgy jósol, hogy a vizsgaügyeket
        kivesszük a tudásából, majd a jóslatot a valós rögzítéssel vetjük össze. Külön látszik, hány esetre mert
        javasolni (lefedettség), és ezekből hány volt helyes (pontosság). Ez nem a Tudásháló százaléka.
      </p>
      {elkulonitve === false && (
        <div className="mb-3 rounded-[var(--radius)] bg-bg-warning px-3 py-2 text-[12px] text-text-warning">
          A vizsgakészlet nincs elkülönítve (Beállítások): a szabályok és a megerősítés láthatták ezeket az ügyeket, ezért az
          eredmény „szennyezett” lehet — felfelé torzíthat.
        </div>
      )}
      {canRun ? (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-[13px]">
          <label className="text-text-secondary">
            Esetek száma{" "}
            <input
              type="number"
              min={1}
              max={200}
              value={esetszam}
              onChange={(e) => setEsetszam(Math.max(1, Math.min(200, Number(e.target.value) || 1)))}
              className="w-20 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-text-primary"
            />
          </label>
          <button
            type="button"
            disabled={fut}
            onClick={() => void futtat()}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 font-medium text-text-accent disabled:opacity-50"
          >
            {fut ? "Próba fut…" : "Próba indítása"}
          </button>
        </div>
      ) : (
        <p className="mb-3 text-[12px] text-text-muted">A próba indításához szerkesztési jogosultság kell.</p>
      )}
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      {eredmeny && (
        <div className="mb-3">
          <div className="mb-2 grid grid-cols-2 gap-2 text-[13px] sm:grid-cols-4">
            <Szam cimke="Vizsgaeset" ertek={String(eredmeny.esetszam)} />
            <Szam cimke="Lefedettség" ertek={szazalek(eredmeny.lefedettseg)} />
            <Szam cimke="Pontosság (javasoltakon)" ertek={szazalek(eredmeny.pontossag)} />
            <Szam cimke="Nem tudta (kérdezett volna)" ertek={String(eredmeny.nem_tudja)} />
          </div>
          {eredmeny.esetszam === 0 ? (
            <p className="text-[13px] text-text-secondary">
              Még nincs vizsgaeset: a visszajátszott, jóváhagyott számlák közül egyik sem esett a vizsgakészletbe.
            </p>
          ) : (
            <div className="max-h-[320px] overflow-auto rounded-[var(--radius)] border border-border">
              <table className="w-full border-collapse text-[12px]">
                <thead>
                  <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                    <th className="px-2 py-1.5 font-medium">Partner</th>
                    <th className="px-2 py-1.5 font-medium">Valóság</th>
                    <th className="px-2 py-1.5 font-medium">Lara jóslata</th>
                    <th className="px-2 py-1.5 font-medium">Eredmény</th>
                  </tr>
                </thead>
                <tbody>
                  {(eredmeny.esetek ?? []).map((s) => (
                    <tr key={s.bejovo_id} className="border-b border-border last:border-0">
                      <td className="px-2 py-1.5">
                        <Link href={s.link} className="text-text-accent hover:underline">
                          {s.partner ?? `#${s.bejovo_id}`}
                        </Link>
                      </td>
                      <td className="px-2 py-1.5 text-text-secondary">{s.valosag}</td>
                      <td className="px-2 py-1.5 text-text-secondary">
                        {s.lara ?? "—"}
                        {s.forras && <span className="block text-[11px] text-text-muted">{s.forras}</span>}
                      </td>
                      <td className={`px-2 py-1.5 ${EREDMENY_CIMKE[s.eredmeny]?.osztaly ?? ""}`}>
                        {EREDMENY_CIMKE[s.eredmeny]?.cimke ?? s.eredmeny}
                        {s.szennyezett_lehet && <span className="block text-[11px] text-text-warning">szennyezett lehet</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {korabbiak.length > 0 && (
        <details className="text-[12px] text-text-muted">
          <summary className="cursor-pointer">Korábbi próbák ({korabbiak.length})</summary>
          <ul className="mt-1 flex flex-col gap-0.5">
            {korabbiak.map((k) => (
              <li key={k.id}>
                {k.ido ? new Date(k.ido).toLocaleString("hu-HU") : "—"}: {k.esetszam} eset · lefedettség{" "}
                {szazalek(k.lefedettseg)} · pontosság {szazalek(k.pontossag)}
                {k.szennyezett ? " · szennyezett" : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Szam({ cimke, ertek }: { cimke: string; ertek: string }) {
  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2">
      <p className="text-[11px] text-text-muted">{cimke}</p>
      <p className="text-[16px] font-medium text-text-primary">{ertek}</p>
    </div>
  );
}
