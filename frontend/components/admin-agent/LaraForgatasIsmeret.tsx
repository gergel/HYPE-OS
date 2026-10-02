"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { authFetch } from "@/lib/authFetch";
import { FeladatBlokk, type FeladatTapasztalat, type FelismertFeladat } from "@/components/admin-agent/LaraDiszpoGomb";

type Szotar = { tipusok: Record<string, string>; kimenetek: Record<string, string>; jellemzok: Record<string, string> };

type Sor = FelismertFeladat & {
  id: number;
  nev: string;
  datum: string | null;
  technika_db: number;
  technika_forras: string | null;
};

type Hatter = {
  bekapcsolva: boolean;
  modell: boolean;
  utolso_siker: string | null;
  utolso_hiba: { ido: string; hiba: string } | null;
  tanulhato: number;
  kesz: number;
  hatralevo: number;
};

type Attekintes = {
  hatter: Hatter;
  forgatasok: number;
  technikas: number;
  tech_forrasok: Record<string, number>;
  tipusok: { tipus: string; cimke: string; forgatasok: number; technikas: number; briefes: number }[];
  forrasok: Record<string, number>;
  szotar: Szotar;
  lista: Sor[];
};

type Reszlet = {
  id: number;
  nev: string;
  datum: string | null;
  profil: FelismertFeladat;
  technika: { equipment_id: number; nev: string; db: number }[];
  technika_forras: string | null;
  tipus_tapasztalat: FeladatTapasztalat;
};

const FORRAS: Record<string, { cimke: string; osztaly: string }> = {
  szabaly: { cimke: "kulcsszó", osztaly: "bg-surface-3 text-text-secondary" },
  modell: { cimke: "AI", osztaly: "bg-bg-accent text-text-accent" },
  ember: { cimke: "javítva", osztaly: "bg-bg-success text-text-success" },
};

const TECH_FORRAS: Record<string, string> = {
  kivitel: "eszközkivitel",
  foglalas: "foglalás",
  technika_lista: "régi technika lista",
  "foglalas+lista": "foglalás + technika lista",
};

function idopont(iso: string | null): string {
  if (!iso) return "még nem futott";
  return new Date(iso).toLocaleString("hu-HU", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** A háttér-tanulás állapota: Lara magától, 10 percenként olvassa végig a
 * korábbi forgatásokat, amíg mind kész - itt csak követni kell. */
function HatterSav({ h }: { h: Hatter }) {
  const arany = h.tanulhato ? h.kesz / h.tanulhato : 1;
  const allapot = !h.bekapcsolva
    ? "Kikapcsolva (Beállítások) - most csak a kulcsszavas felismerés működik."
    : !h.modell
      ? "Nincs beállítva a modell-kulcs - most csak a kulcsszavas felismerés működik."
      : h.hatralevo === 0
        ? "Minden forgatást végigolvastam; az újakat és a megváltozottakat 10 percen belül megtanulom."
        : `A háttérben tanulok: 10 percenként 50 forgatás, még kb. ${Math.ceil(h.hatralevo / 50) * 10} perc.`;
  return (
    <div className="rounded-[var(--radius)] border border-border px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-medium text-text-primary">Háttér-tanulás</p>
        <p className="tabular-nums text-text-secondary">
          {h.kesz} / {h.tanulhato} forgatás végigolvasva ({Math.round(arany * 100)}%)
        </p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-3" role="progressbar" aria-valuenow={h.kesz} aria-valuemax={h.tanulhato}>
        <div className="h-full rounded-full bg-bg-accent" style={{ width: `${Math.round(arany * 100)}%` }} />
      </div>
      <p className="mt-1.5 text-[12px] text-text-muted">
        {allapot} Utolsó futás: {idopont(h.utolso_siker)}.
        {h.utolso_hiba && (!h.utolso_siker || h.utolso_hiba.ido > h.utolso_siker) ? ` Utolsó hiba: ${h.utolso_hiba.hiba}` : ""}
      </p>
    </div>
  );
}

async function lekeres(tipus: string, q: string): Promise<Attekintes | string> {
  const p = new URLSearchParams();
  if (tipus) p.set("tipus", tipus);
  if (q.trim()) p.set("q", q.trim());
  const res = await authFetch(`/api/v1/admin-agent/forgatasok/ismeret?${p.toString()}`);
  const d = await res.json().catch(() => ({}));
  if (!res.ok) return typeof d.detail === "string" ? d.detail : `Nem sikerült betölteni (${res.status}).`;
  return d as Attekintes;
}

type Szerk = { tipus: string; kimenetek: string[]; jellemzok: string[]; feladat_leiras: string };

/** Lara forgatás-ismerete: melyik korábbi forgatáson mi volt pontosan a
 * feladat, mi ment ki rá ténylegesen, és ebből mit tanult az ilyen feladatokhoz
 * (technikai lista, brief). A felismerés kulcsszó alapú; az AI visszamenőleg
 * pontosíthatja, a te javításod a legerősebb. */
export function LaraForgatasIsmeret({ canEdit, kezdoForgatas }: { canEdit: boolean; kezdoForgatas: number | null }) {
  const [tipus, setTipus] = useState("");
  const [q, setQ] = useState("");
  const [adat, setAdat] = useState<Attekintes | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [nyitott, setNyitott] = useState<Reszlet | null>(null);
  const [szerk, setSzerk] = useState<Szerk | null>(null);
  const [busy, setBusy] = useState(false);

  const frissit = useCallback(() => {
    lekeres(tipus, q).then((d) => {
      if (typeof d === "string") setHiba(d);
      else setAdat(d);
    });
  }, [tipus, q]);

  useEffect(() => {
    let elve = false;
    const idozito = setTimeout(() => {
      lekeres(tipus, q).then((d) => {
        if (elve) return;
        if (typeof d === "string") setHiba(d);
        else setAdat(d);
      });
    }, 250);
    return () => {
      elve = true;
      clearTimeout(idozito);
    };
  }, [tipus, q]);

  const megnyit = useCallback(async (id: number) => {
    const res = await authFetch(`/api/v1/admin-agent/forgatasok/${id}/ismeret`);
    const d = await res.json().catch(() => ({}));
    if (!res.ok) {
      setHiba(typeof d.detail === "string" ? d.detail : "Nem sikerült betölteni.");
      return;
    }
    const r = d as Reszlet;
    setNyitott(r);
    setSzerk({
      tipus: r.profil.tipus,
      kimenetek: r.profil.kimenetek,
      jellemzok: r.profil.jellemzok,
      feladat_leiras: r.profil.feladat_leiras ?? "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (kezdoForgatas == null) return;
    const idozito = setTimeout(() => void megnyit(kezdoForgatas), 0);
    return () => clearTimeout(idozito);
  }, [kezdoForgatas, megnyit]);

  async function javitasMentes() {
    if (!nyitott || !szerk) return;
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/admin-agent/forgatasok/${nyitott.id}/feladat`, {
        method: "PATCH",
        body: JSON.stringify({
          tipus: szerk.tipus,
          tipusok: [szerk.tipus],
          kimenetek: szerk.kimenetek,
          jellemzok: szerk.jellemzok,
          feladat_leiras: szerk.feladat_leiras.trim() || null,
        }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A javítás nem sikerült.");
        return;
      }
      setUzenet(`Megtanultam: ${nyitott.nev} — mostantól így ismerem a feladatát.`);
      frissit();
      void megnyit(nyitott.id);
    } finally {
      setBusy(false);
    }
  }

  async function visszaallitas() {
    if (!nyitott) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/forgatasok/${nyitott.id}/feladat`, { method: "DELETE" });
      if (!res.ok) {
        setHiba("A visszaállítás nem sikerült.");
        return;
      }
      setUzenet("Visszaállítva: újra a kulcsszavak szerinti felismerés érvényes.");
      frissit();
      void megnyit(nyitott.id);
    } finally {
      setBusy(false);
    }
  }

  async function aiTanulas() {
    setBusy(true);
    setHiba(null);
    setUzenet(null);
    try {
      const res = await authFetch("/api/v1/admin-agent/forgatasok/ai-tanulas", {
        method: "POST",
        body: JSON.stringify({ limit: 20 }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "Az AI-tanulás nem sikerült.");
        return;
      }
      setUzenet(
        d.allapot === "nincs_teendo"
          ? "Minden korábbi forgatást végigolvastam már."
          : `Végigolvastam ${d.profilozva} forgatást${d.elutasitva ? ` (${d.elutasitva} válasz nem volt érvényes, kihagytam)` : ""}. ` +
              `Még ${d.hatralevo} van hátra.${d.hiba ? ` A modell közben hibát adott: ${d.hiba}` : ""}`,
      );
      frissit();
    } finally {
      setBusy(false);
    }
  }

  function kapcsol(mezo: "kimenetek" | "jellemzok", kulcs: string) {
    setSzerk((s) =>
      s ? { ...s, [mezo]: s[mezo].includes(kulcs) ? s[mezo].filter((x) => x !== kulcs) : [...s[mezo], kulcs] } : s,
    );
  }

  return (
    <div className="flex flex-col gap-4 text-[13px]">
      <div className="rounded-[var(--radius)] border border-border px-4 py-3">
        <p className="font-medium text-text-primary">Mit tud Lara a korábbi forgatásokról?</p>
        <p className="mt-0.5 text-text-muted">
          Minden forgatásnál felismeri, mi volt pontosan a feladat (konferencia, esküvő, interjú, élő közvetítés …), milyen
          kimenetre (aftermovie, social, teljes felvétel) és milyen körülmények között (drón, kültér, sötét helyszín, több
          kamera). Megnézi, mi ment ki rá ténylegesen (eszközkivitel, foglalás, régi technika lista), és ebből tanulja meg,
          hogy az ilyen feladatokhoz milyen technika és milyen brief kell. Az AI a háttérben, magától végigolvassa az
          összes forgatást; a megszerzett tudás a Tudástárban és a Tudáshálóban is látszik. A te javításod a legerősebb.
        </p>
        {adat && (
          <p className="mt-1 text-[12px] text-text-muted">
            {adat.forgatasok} forgatás, ebből {adat.technikas} ismert technikával (
            {Object.entries(adat.tech_forrasok)
              .map(([k, v]) => `${TECH_FORRAS[k] ?? k}: ${v}`)
              .join(", ")}
            ) · felismerés: {adat.forrasok.szabaly ?? 0} kulcsszó · {adat.forrasok.modell ?? 0} AI ·{" "}
            {adat.forrasok.ember ?? 0} javított
          </p>
        )}
      </div>

      {adat && <HatterSav h={adat.hatter} />}

      {adat && (
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setTipus("")}
            className={`rounded-full border px-2.5 py-0.5 ${tipus === "" ? "border-border bg-surface-3 text-text-primary" : "border-transparent text-text-secondary hover:bg-surface-2"}`}
          >
            Mind
          </button>
          {adat.tipusok.map((t) => (
            <button
              key={t.tipus}
              type="button"
              onClick={() => setTipus(t.tipus === tipus ? "" : t.tipus)}
              title={`${t.technikas} ismert technikával, ${t.briefes} briefes`}
              className={`rounded-full border px-2.5 py-0.5 ${tipus === t.tipus ? "border-border bg-surface-3 text-text-primary" : "border-transparent text-text-secondary hover:bg-surface-2"}`}
            >
              {t.cimke} <span className="tabular-nums text-text-muted">{t.forgatasok}</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Keresés a forgatás nevében…"
          className="w-[260px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-text-primary focus:outline-none"
        />
        {canEdit && (
          <button
            type="button"
            disabled={busy}
            onClick={aiTanulas}
            className="ml-auto rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 font-medium text-text-accent disabled:opacity-50"
          >
            {busy ? "Dolgozom…" : "Gyorsítás: 20 forgatás most"}
          </button>
        )}
      </div>
      {hiba && <p className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-text-danger">{hiba}</p>}
      {uzenet && <p className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-text-success">{uzenet}</p>}

      {nyitott && szerk && adat && (
        <div className="flex flex-col gap-3 rounded-[var(--radius)] border border-border bg-surface-2 p-3">
          <div className="flex flex-wrap items-baseline gap-2">
            <Link href={`/projektek/${nyitott.id}`} className="font-medium text-text-primary underline">
              {nyitott.nev}
            </Link>
            <span className="text-text-muted">{nyitott.datum}</span>
            <button type="button" onClick={() => setNyitott(null)} className="ml-auto text-text-secondary hover:text-text-primary">
              Bezárás ✕
            </button>
          </div>
          <FeladatBlokk f={nyitott.profil} t={nyitott.tipus_tapasztalat} />
          <div>
            <p className="font-medium text-text-primary">
              Kivitt technika{nyitott.technika_forras ? ` (${TECH_FORRAS[nyitott.technika_forras] ?? nyitott.technika_forras})` : ""}
            </p>
            {nyitott.technika.length === 0 ? (
              <p className="text-text-muted">Ehhez a forgatáshoz nincs rögzített technika.</p>
            ) : (
              <p className="text-text-secondary">
                {nyitott.technika.map((t) => (t.db > 1 ? `${t.db} db ${t.nev}` : t.nev)).join(" · ")}
              </p>
            )}
          </div>
          {canEdit && (
            <div className="flex flex-col gap-2">
              <p className="font-medium text-text-primary">Javítás (Lara ebből tanul)</p>
              <select
                value={szerk.tipus}
                onChange={(e) => setSzerk({ ...szerk, tipus: e.target.value })}
                className="self-start rounded border border-border bg-surface-3 px-2 py-1"
              >
                {Object.entries(adat.szotar.tipusok).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-text-secondary">
                <span className="text-text-muted">Kimenet:</span>
                {Object.entries(adat.szotar.kimenetek).map(([k, v]) => (
                  <label key={k} className="flex items-center gap-1">
                    <input type="checkbox" checked={szerk.kimenetek.includes(k)} onChange={() => kapcsol("kimenetek", k)} /> {v}
                  </label>
                ))}
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-text-secondary">
                <span className="text-text-muted">Jellemző:</span>
                {Object.entries(adat.szotar.jellemzok).map(([k, v]) => (
                  <label key={k} className="flex items-center gap-1">
                    <input type="checkbox" checked={szerk.jellemzok.includes(k)} onChange={() => kapcsol("jellemzok", k)} /> {v}
                  </label>
                ))}
              </div>
              <textarea
                value={szerk.feladat_leiras}
                onChange={(e) => setSzerk({ ...szerk, feladat_leiras: e.target.value })}
                placeholder="Mi volt pontosan a feladat? (1-2 mondat: mit kellett felvenni, milyen kimenetre)"
                rows={2}
                maxLength={400}
                className="rounded border border-border bg-surface-3 px-2 py-1"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={javitasMentes}
                  className="rounded-[var(--radius)] bg-bg-success px-3 py-1 font-medium text-text-success disabled:opacity-50"
                >
                  Mentés
                </button>
                {nyitott.profil.forras !== "szabaly" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={visszaallitas}
                    className="rounded-[var(--radius)] border border-border px-3 py-1 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                  >
                    Visszaállítás kulcsszó alapúra
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {!adat ? (
        <p className="text-text-muted">Betöltés…</p>
      ) : adat.lista.length === 0 ? (
        <p className="text-text-muted">Nincs találat.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border rounded-[var(--radius)] border border-border">
          {adat.lista.map((s) => (
            <li key={s.id} className="px-3 py-2">
              <button type="button" onClick={() => void megnyit(s.id)} className="flex w-full flex-wrap items-baseline gap-2 text-left">
                <span className="w-[84px] tabular-nums text-text-muted">{s.datum}</span>
                <span className="font-medium text-text-primary">{s.nev}</span>
                <span className="text-text-secondary">{s.tipus_cimke}</span>
                <span className={`rounded px-1.5 text-[11px] ${FORRAS[s.forras]?.osztaly ?? ""}`}>{FORRAS[s.forras]?.cimke ?? s.forras}</span>
                {s.technika_db > 0 && <span className="text-[12px] text-text-muted">{s.technika_db} eszköz</span>}
                <span className="w-full pl-[92px] text-[12px] text-text-muted">{s.feladat_leiras || s.osszegzes}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
