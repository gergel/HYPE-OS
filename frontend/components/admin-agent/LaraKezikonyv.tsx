"use client";

import { useCallback, useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";

/** Lara RENDSZERKÉZIKÖNYVE (kliens).
 *
 * - Technikai leírás: gépi TERVEZET a kódból (adatmodellek, mezők) és a
 *   docs/kezikonyv fájlokból. Jóváhagyásig Lara nem használja.
 * - Jóváhagyott üzleti eljárás: csak ember írja; külön jelölve.
 * Új forrásból új verzió lesz (tervezet), a korábbi jóváhagyott addig érvényes.
 * Lara a kérdésekhez mindig csak a releváns, jóváhagyott szakaszokat kapja meg.
 * Lásd backend admin_agent/kezikonyv.py. */

type Szakasz = {
  id: number;
  fajta: "kezikonyv_technikai" | "kezikonyv_uzleti";
  cim: string | null;
  forras_tipus: string | null;
  oldal: string | null;
  tartalom: string;
  verzio: number;
  elozo_verzio_id: number | null;
  allapot: "tervezet" | "jovahagyva" | "elvetve";
  ervenyes_ig: string | null;
  jovahagyva_at: string | null;
};

type Lista = { elemek: Szakasz[]; osszesito: { tervezet: number; jovahagyva: number; elvetve: number } };

const ALLAPOT: Record<string, string> = { tervezet: "Tervezet", jovahagyva: "Jóváhagyva", elvetve: "Elvetve" };

async function kezikonyvLekeres(allapot: string, fajta: string, q: string): Promise<Lista | null> {
  const p = new URLSearchParams();
  if (allapot) p.set("allapot", allapot);
  if (fajta) p.set("fajta", fajta);
  if (q.trim()) p.set("q", q.trim());
  const r = await authFetch(`/api/v1/admin-agent/kezikonyv?${p.toString()}`);
  return r.ok ? ((await r.json()) as Lista) : null;
}

export function LaraKezikonyv({ canEdit, canApprove }: { canEdit: boolean; canApprove: boolean }) {
  const [allapot, setAllapot] = useState<string>("tervezet");
  const [fajta, setFajta] = useState<string>("");
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<Lista | null>(null);
  const [nyitott, setNyitott] = useState<number | null>(null);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [fut, setFut] = useState(false);
  const [uj, setUj] = useState<{ cim: string; tartalom: string } | null>(null);

  const betolt = useCallback(async () => {
    const r = await kezikonyvLekeres(allapot, fajta, q);
    if (r) setLista(r);
    else setHiba("A kézikönyv nem tölthető be.");
  }, [allapot, fajta, q]);

  useEffect(() => {
    let el = false;
    void kezikonyvLekeres(allapot, fajta, q).then((r) => {
      if (el) return;
      if (r) setLista(r);
      else setHiba("A kézikönyv nem tölthető be.");
    });
    return () => {
      el = true;
    };
  }, [allapot, fajta, q]);

  async function hivas(url: string, method: string, body?: unknown, siker?: string) {
    setFut(true);
    setHiba(null);
    setUzenet(null);
    try {
      const r = await authFetch(url, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const d = (await r.json().catch(() => ({}))) as Record<string, unknown>;
      if (!r.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A művelet nem sikerült.");
        return null;
      }
      if (siker) setUzenet(siker);
      await betolt();
      return d;
    } finally {
      setFut(false);
    }
  }

  const gomb = "rounded-[var(--radius)] px-2.5 py-1 text-[12px] font-medium disabled:opacity-50";
  return (
    <div className="flex flex-col gap-3 text-[13px]">
      <p className="text-[12px] text-text-muted">
        A technikai leírás gépi tervezet a kódból és a kézikönyv-fájlokból — jóváhagyásig Lara nem használja. Az üzleti
        eljárást csak ember írja; a technikai leírásból sosem lesz magától üzleti szabály. Lara egy kérdéshez mindig csak a
        releváns, jóváhagyott szakaszokat kapja meg.
      </p>
      {lista && (
        <p className="text-[12px] text-text-secondary">
          {lista.osszesito.jovahagyva} jóváhagyott · {lista.osszesito.tervezet} tervezet · {lista.osszesito.elvetve} elvetett
        </p>
      )}
      {uzenet && <div className="rounded-[var(--radius)] bg-bg-success px-3 py-2 text-text-success">{uzenet}</div>}
      {hiba && <div className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-text-danger">{hiba}</div>}
      <div className="flex flex-wrap items-center gap-2">
        <select value={allapot} onChange={(e) => setAllapot(e.target.value)} className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1">
          <option value="tervezet">Tervezetek</option>
          <option value="jovahagyva">Jóváhagyottak</option>
          <option value="elvetve">Elvetettek</option>
          <option value="">Mind</option>
        </select>
        <select value={fajta} onChange={(e) => setFajta(e.target.value)} className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1">
          <option value="">Technikai + üzleti</option>
          <option value="kezikonyv_technikai">Technikai leírás</option>
          <option value="kezikonyv_uzleti">Üzleti eljárás</option>
        </select>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Keresés…"
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1"
        />
        {canEdit && (
          <>
            <button
              type="button"
              disabled={fut}
              onClick={() =>
                void hivas("/api/v1/admin-agent/kezikonyv/generalas", "POST", undefined).then((d) => {
                  if (d) setUzenet(`Tervezetek frissítve: ${d.uj} új, ${d.uj_verzio} új verzió, ${d.valtozatlan} változatlan.`);
                })
              }
              className={`${gomb} border border-border bg-surface-3 text-text-primary hover:bg-surface-4`}
            >
              Tervezetek frissítése a kódból
            </button>
            <button type="button" onClick={() => setUj({ cim: "", tartalom: "" })} className={`${gomb} bg-bg-accent text-text-accent`}>
              Új üzleti eljárás
            </button>
          </>
        )}
      </div>
      {uj && (
        <div className="flex flex-col gap-2 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
          <input
            value={uj.cim}
            onChange={(e) => setUj({ ...uj, cim: e.target.value })}
            placeholder="Cím (pl. KP-s kiadás rögzítése)"
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1"
          />
          <textarea
            value={uj.tartalom}
            onChange={(e) => setUj({ ...uj, tartalom: e.target.value })}
            rows={4}
            placeholder="Hogyan csináljuk a HYPE-nál — lépések, kivételek."
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={fut || !uj.cim.trim() || !uj.tartalom.trim()}
              onClick={() =>
                void hivas("/api/v1/admin-agent/kezikonyv", "POST", uj, "Tervezetként mentve — jóváhagyás után használja Lara.").then(
                  (d) => d && setUj(null),
                )
              }
              className={`${gomb} bg-bg-accent text-text-accent`}
            >
              Mentés tervezetként
            </button>
            <button type="button" onClick={() => setUj(null)} className={`${gomb} text-text-secondary`}>
              Mégse
            </button>
          </div>
        </div>
      )}
      {!lista ? (
        <p className="text-text-muted">Betöltés…</p>
      ) : lista.elemek.length === 0 ? (
        <p className="text-text-secondary">Nincs ilyen szakasz.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {lista.elemek.slice(0, 100).map((s) => (
            <li key={s.id} className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button type="button" onClick={() => setNyitott(nyitott === s.id ? null : s.id)} className="text-left text-text-primary hover:underline">
                  {s.cim ?? `#${s.id}`}
                </button>
                <span className="flex flex-wrap items-center gap-1.5 text-[11px] text-text-muted">
                  <span className="rounded-[var(--radius)] bg-surface-2 px-1.5 py-0.5">
                    {s.fajta === "kezikonyv_uzleti" ? "Üzleti eljárás" : "Technikai leírás"}
                  </span>
                  <span>
                    {ALLAPOT[s.allapot]} · v{s.verzio}
                    {s.ervenyes_ig ? " · lecserélve" : ""}
                  </span>
                  {s.oldal && <span>jogosultság: {s.oldal}</span>}
                </span>
              </div>
              {nyitott === s.id && (
                <div className="mt-2">
                  <pre className="max-h-[320px] overflow-auto whitespace-pre-wrap rounded-[var(--radius)] bg-surface-2 p-2 text-[12px] text-text-secondary">
                    {s.tartalom}
                  </pre>
                  {s.allapot === "tervezet" && (
                    <div className="mt-2 flex gap-2">
                      {canApprove && (
                        <button
                          type="button"
                          disabled={fut}
                          onClick={() => void hivas(`/api/v1/admin-agent/kezikonyv/${s.id}/jovahagyas`, "POST", undefined, "Jóváhagyva — Lara mostantól használja.")}
                          className={`${gomb} bg-bg-success text-text-success`}
                        >
                          Jóváhagyás
                        </button>
                      )}
                      {canEdit && (
                        <button
                          type="button"
                          disabled={fut}
                          onClick={() => void hivas(`/api/v1/admin-agent/kezikonyv/${s.id}/elvetes`, "POST", undefined, "Elvetve.")}
                          className={`${gomb} border border-border text-text-secondary hover:bg-surface-4`}
                        >
                          Elvetés
                        </button>
                      )}
                    </div>
                  )}
                  {s.allapot === "jovahagyva" && canEdit && (
                    <button
                      type="button"
                      disabled={fut}
                      onClick={() => void hivas(`/api/v1/admin-agent/kezikonyv/${s.id}/elvetes`, "POST", undefined, "Visszavonva — Lara többé nem használja.")}
                      className={`${gomb} mt-2 border border-border text-text-secondary hover:bg-surface-4`}
                    >
                      Visszavonás
                    </button>
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
