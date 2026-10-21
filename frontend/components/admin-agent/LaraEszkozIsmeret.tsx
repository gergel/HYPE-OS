"use client";

import { useCallback, useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";

type Profil = {
  funkcio: string;
  altipus: string | null;
  marka: string | null;
  gyujto_min: number | null;
  gyujto_max: number | null;
  fenyero: number | null;
  bajonett: string | null;
  mire_jo: string | null;
  csoport: string;
  forras: "szabaly" | "modell" | "ember";
};

type Elem = Profil & { id: number; nev: string; kategoria: string | null; hasznalhato: boolean; szerep: string };

type Lista = { funkciok: Record<string, string>; elemek: Elem[]; forrasok: Record<string, number> };

type Reszlet = {
  id: number;
  nev: string;
  szerep: string;
  profil: Profil;
  hasonlok: { equipment_id: number; nev: string; hasonlosag: number; szerep: string }[];
};

const FORRAS: Record<string, { cimke: string; osztaly: string }> = {
  szabaly: { cimke: "szabály", osztaly: "bg-surface-3 text-text-secondary" },
  modell: { cimke: "AI", osztaly: "bg-bg-accent text-text-accent" },
  ember: { cimke: "javítva", osztaly: "bg-bg-success text-text-success" },
};

async function listaLekeres(q: string, funkcio: string): Promise<Lista | string> {
  const p = new URLSearchParams();
  if (q.trim()) p.set("q", q.trim());
  if (funkcio) p.set("funkcio", funkcio);
  const res = await authFetch(`/api/v1/admin-agent/eszkozok/ismeret?${p.toString()}`);
  const d = await res.json().catch(() => ({}));
  if (!res.ok) return typeof d.detail === "string" ? d.detail : `Nem sikerült betölteni (${res.status}).`;
  return d as Lista;
}

/** Lara eszköz-ismerete: mi micsoda a technikai listán és mire jó. Ebből
 * tudja Lara a diszpó technikájánál, hogy egy foglalt kamera vagy optika helyett
 * melyik másik jó ugyanarra a szerepre (pl. 24-70 helyett 28-75). */
export function LaraEszkozIsmeret({ canEdit }: { canEdit: boolean }) {
  const [q, setQ] = useState("");
  const [funkcio, setFunkcio] = useState("");
  const [lista, setLista] = useState<Lista | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [nyitott, setNyitott] = useState<Reszlet | null>(null);
  const [szerk, setSzerk] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const frissit = useCallback(() => {
    listaLekeres(q, funkcio).then((d) => {
      if (typeof d === "string") setHiba(d);
      else setLista(d);
    });
  }, [q, funkcio]);

  useEffect(() => {
    let elve = false;
    const idozito = setTimeout(() => {
      listaLekeres(q, funkcio).then((d) => {
        if (elve) return;
        if (typeof d === "string") setHiba(d);
        else setLista(d);
      });
    }, 250);
    return () => {
      elve = true;
      clearTimeout(idozito);
    };
  }, [q, funkcio]);

  async function megnyit(id: number) {
    if (nyitott?.id === id) {
      setNyitott(null);
      return;
    }
    const res = await authFetch(`/api/v1/admin-agent/eszkozok/${id}/ismeret`);
    const d = await res.json().catch(() => ({}));
    if (!res.ok) {
      setHiba(typeof d.detail === "string" ? d.detail : "Nem sikerült betölteni.");
      return;
    }
    const r = d as Reszlet;
    setNyitott(r);
    setSzerk({
      funkcio: r.profil.funkcio,
      altipus: r.profil.altipus ?? "",
      gyujto_min: r.profil.gyujto_min?.toString() ?? "",
      gyujto_max: r.profil.gyujto_max?.toString() ?? "",
      fenyero: r.profil.fenyero?.toString() ?? "",
      mire_jo: r.profil.mire_jo ?? "",
    });
  }

  async function javitasMentes() {
    if (!nyitott) return;
    setBusy(true);
    setHiba(null);
    const szam = (v: string) => (v.trim() === "" ? null : Number(v.replace(",", ".")));
    try {
      const res = await authFetch(`/api/v1/admin-agent/eszkozok/${nyitott.id}/profil`, {
        method: "PATCH",
        body: JSON.stringify({
          funkcio: szerk.funkcio,
          altipus: szerk.altipus.trim() || null,
          gyujto_min: szam(szerk.gyujto_min),
          gyujto_max: szam(szerk.gyujto_max),
          fenyero: szam(szerk.fenyero),
          mire_jo: szerk.mire_jo.trim() || null,
        }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A javítás nem sikerült.");
        return;
      }
      setUzenet(`Megtanultam: ${nyitott.nev} — mostantól így ismerem.`);
      const id = nyitott.id;
      setNyitott(null);
      frissit();
      void megnyit(id);
    } finally {
      setBusy(false);
    }
  }

  async function aiPontositas() {
    setBusy(true);
    setHiba(null);
    setUzenet(null);
    try {
      const res = await authFetch("/api/v1/admin-agent/eszkozok/ai-profilozas", {
        method: "POST",
        body: JSON.stringify({ limit: 40 }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "Az AI-pontosítás nem sikerült.");
        return;
      }
      setUzenet(
        d.allapot === "nincs_teendo"
          ? "Nincs pontosítandó eszköz."
          : `AI-pontosítás kész: ${d.profilozva} eszköz${d.elutasitva ? `, ${d.elutasitva} javaslat elutasítva (nem volt valid)` : ""}.`,
      );
      frissit();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 text-[13px]">
      <div className="rounded-[var(--radius)] border border-border px-4 py-3">
        <p className="font-medium text-text-primary">Mit tud Lara az eszközökről?</p>
        <p className="mt-0.5 text-text-muted">
          Minden eszközhöz szerep, altípus, gyújtótáv / fényerő és „mire jó”. Ebből ismeri fel a hasonló eszközöket: a
          diszpó technikájánál egy foglalt kamera vagy optika helyett a leginkább hasonló szabadot javasolja. A profil
          szabály alapú; az AI pontosíthatja, a te javításod a legerősebb.
        </p>
        {lista && (
          <p className="mt-1 text-[12px] text-text-muted">
            Forrás: {lista.forrasok.szabaly ?? 0} szabály · {lista.forrasok.modell ?? 0} AI · {lista.forrasok.ember ?? 0} javított
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Keresés név szerint…"
          className="w-[240px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-text-primary focus:outline-none"
        />
        <select
          value={funkcio}
          onChange={(e) => setFunkcio(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-text-secondary"
        >
          <option value="">Minden szerep</option>
          {Object.entries(lista?.funkciok ?? {}).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        {canEdit && (
          <button
            type="button"
            disabled={busy}
            onClick={aiPontositas}
            className="ml-auto rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 font-medium text-text-accent disabled:opacity-50"
          >
            {busy ? "Dolgozom…" : "AI-pontosítás most (40 eszköz)"}
          </button>
        )}
      </div>
      {hiba && <p className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-text-danger">{hiba}</p>}
      {uzenet && <p className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-text-success">{uzenet}</p>}

      {!lista ? (
        <p className="text-text-muted">Betöltés…</p>
      ) : lista.elemek.length === 0 ? (
        <p className="text-text-muted">Nincs találat.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border rounded-[var(--radius)] border border-border">
          {lista.elemek.map((e) => (
            <li key={e.id} className="px-3 py-2">
              <button type="button" onClick={() => void megnyit(e.id)} className="flex w-full flex-wrap items-baseline gap-2 text-left">
                <span className={`font-medium ${e.hasznalhato ? "text-text-primary" : "text-text-muted line-through"}`}>{e.nev}</span>
                <span className="text-text-secondary">{e.szerep}</span>
                <span className={`rounded px-1.5 text-[11px] ${FORRAS[e.forras]?.osztaly ?? ""}`}>{FORRAS[e.forras]?.cimke ?? e.forras}</span>
                {e.mire_jo && <span className="w-full text-[12px] text-text-muted">{e.mire_jo}</span>}
              </button>
              {nyitott?.id === e.id && (
                <div className="mt-2 flex flex-col gap-3 rounded-[var(--radius)] bg-surface-3 p-3">
                  <div>
                    <p className="font-medium text-text-primary">Hasonló (helyettesítésre alkalmas) eszközök</p>
                    {nyitott.hasonlok.length === 0 ? (
                      <p className="text-text-muted">Nincs elég hasonló eszköz a törzsben.</p>
                    ) : (
                      <ul className="mt-1 flex flex-col gap-0.5">
                        {nyitott.hasonlok.map((h) => (
                          <li key={h.equipment_id} className="flex flex-wrap gap-2">
                            <span className="w-12 text-right tabular-nums text-text-muted">{Math.round(h.hasonlosag * 100)}%</span>
                            <span className="text-text-primary">{h.nev}</span>
                            <span className="text-text-muted">{h.szerep}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {canEdit && (
                    <div className="flex flex-col gap-2">
                      <p className="font-medium text-text-primary">Javítás (Lara ebből tanul)</p>
                      <div className="flex flex-wrap gap-2">
                        <select
                          value={szerk.funkcio}
                          onChange={(ev) => setSzerk((s) => ({ ...s, funkcio: ev.target.value, altipus: "" }))}
                          className="rounded border border-border bg-surface-2 px-2 py-1"
                        >
                          {Object.entries(lista.funkciok).map(([k, v]) => (
                            <option key={k} value={k}>
                              {v}
                            </option>
                          ))}
                        </select>
                        <input
                          value={szerk.altipus}
                          onChange={(ev) => setSzerk((s) => ({ ...s, altipus: ev.target.value }))}
                          placeholder="altípus (pl. cinema, standard_zoom)"
                          className="w-[220px] rounded border border-border bg-surface-2 px-2 py-1"
                        />
                        {szerk.funkcio === "optika" && (
                          <>
                            <input
                              value={szerk.gyujto_min}
                              onChange={(ev) => setSzerk((s) => ({ ...s, gyujto_min: ev.target.value }))}
                              placeholder="min mm"
                              className="w-[80px] rounded border border-border bg-surface-2 px-2 py-1"
                            />
                            <input
                              value={szerk.gyujto_max}
                              onChange={(ev) => setSzerk((s) => ({ ...s, gyujto_max: ev.target.value }))}
                              placeholder="max mm"
                              className="w-[80px] rounded border border-border bg-surface-2 px-2 py-1"
                            />
                            <input
                              value={szerk.fenyero}
                              onChange={(ev) => setSzerk((s) => ({ ...s, fenyero: ev.target.value }))}
                              placeholder="f-szám"
                              className="w-[70px] rounded border border-border bg-surface-2 px-2 py-1"
                            />
                          </>
                        )}
                      </div>
                      <textarea
                        value={szerk.mire_jo}
                        onChange={(ev) => setSzerk((s) => ({ ...s, mire_jo: ev.target.value }))}
                        placeholder="Mire jó a forgatáson?"
                        rows={2}
                        className="rounded border border-border bg-surface-2 px-2 py-1"
                      />
                      <button
                        type="button"
                        disabled={busy}
                        onClick={javitasMentes}
                        className="self-start rounded-[var(--radius)] bg-bg-success px-3 py-1 font-medium text-text-success disabled:opacity-50"
                      >
                        Mentés
                      </button>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
