"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Paperclip, Plus, Square, Trash2, X } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { formatSzam } from "@/lib/penz";

/** A MŰVELETI ASSZISZTENS felülete (a felhasználó kérése): tartós,
 * folytatható beszélgetések; a kérésből az asszisztens megkeresi az adatokat,
 * elvégzi a műveletet a rendszer saját folyamatain, ellenőrzi, és linkelt
 * összefoglalót ad. A folyamat lépései élőben látszanak (polling), a
 * megerősítendő műveletek (törlés, pénzügyi felvezetés) kártyán várják a
 * jóváhagyást - a végrehajtás pontosan a kártyán mutatott, tárolt kéréssel
 * történik. Oldalfrissítés után minden a szerverről áll vissza. */

type Beszelgetes = { id: number; cim: string | null; fut: boolean };
type Uzenet = {
  id: number;
  szerep: "felhasznalo" | "asszisztens" | "esemeny";
  szoveg: string | null;
  adat: Record<string, unknown> | null;
};
type NaploSor = { id: number; allapot: string; osszefoglalo: string | null; method: string; path: string; status: number | null };

/** Egyszerű markdown-link renderelés: [cím](/utvonal) → kattintható link. */
function Szoveg({ szoveg }: { szoveg: string }) {
  const reszek = useMemo(() => {
    const t: (string | { cim: string; href: string })[] = [];
    let utolso = 0;
    const minta = /\[([^\]]+)\]\(([^)\s]+)\)/g;
    let m: RegExpExecArray | null;
    while ((m = minta.exec(szoveg)) !== null) {
      if (m.index > utolso) t.push(szoveg.slice(utolso, m.index));
      t.push({ cim: m[1], href: m[2] });
      utolso = m.index + m[0].length;
    }
    if (utolso < szoveg.length) t.push(szoveg.slice(utolso));
    return t;
  }, [szoveg]);
  return (
    <p className="whitespace-pre-line">
      {reszek.map((r, i) =>
        typeof r === "string" ? (
          <span key={i}>{r}</span>
        ) : r.href.startsWith("/") ? (
          <Link key={i} href={r.href} className="text-text-accent hover:underline">
            {r.cim}
          </Link>
        ) : (
          <a key={i} href={r.href} target="_blank" rel="noreferrer" className="text-text-accent hover:underline">
            {r.cim}
          </a>
        ),
      )}
    </p>
  );
}

export function AiAssistantChat() {
  const searchParams = useSearchParams();
  const [beszelgetesek, setBeszelgetesek] = useState<Beszelgetes[]>([]);
  const [aktiv, setAktiv] = useState<number | null>(null);
  const [uzenetek, setUzenetek] = useState<Uzenet[]>([]);
  const [naplo, setNaplo] = useState<Record<number, NaploSor>>({});
  const [szoveg, setSzoveg] = useState("");
  const [fajlok, setFajlok] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [fut, setFut] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const utolsoIdRef = useRef(0);

  // Oldal-kontextus, ha másik oldalról nyitották az asszisztenst
  // (?entity=deliverable&rekord=123&cim=...): az „ez"/„ennél" erre mutat.
  const kontextus = useMemo(() => {
    const entity = searchParams.get("entity");
    const rekord = searchParams.get("rekord");
    const cim = searchParams.get("cim");
    const utvonal = searchParams.get("honnan");
    if (!entity && !rekord && !cim && !utvonal) return null;
    return {
      ...(utvonal ? { utvonal } : {}),
      ...(cim ? { cim } : {}),
      ...(entity ? { entity_type: entity } : {}),
      ...(rekord ? { entity_id: Number(rekord) } : {}),
    };
  }, [searchParams]);

  function gorgetes() {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  const uzenetBeolvaszt = useCallback((ujak: Uzenet[]) => {
    if (ujak.length === 0) return;
    setUzenetek((prev) => {
      const megvan = new Set(prev.map((u) => u.id));
      const hozzaad = ujak.filter((u) => !megvan.has(u.id));
      if (hozzaad.length === 0) return prev;
      const t = [...prev, ...hozzaad].sort((a, b) => a.id - b.id);
      utolsoIdRef.current = t[t.length - 1]?.id ?? 0;
      return t;
    });
    gorgetes();
  }, []);

  const naploFrissit = useCallback(async (bid: number) => {
    try {
      const r = await authFetch(`/api/v1/ai-assistant/beszelgetesek/${bid}/naplo`);
      if (r.ok) {
        const sorok: NaploSor[] = await r.json();
        setNaplo(Object.fromEntries(sorok.map((s) => [s.id, s])));
      }
    } catch {
      /* nem kritikus */
    }
  }, []);

  const beszelgetesValt = useCallback(
    async (bid: number) => {
      setAktiv(bid);
      setUzenetek([]);
      utolsoIdRef.current = 0;
      try {
        localStorage.setItem("ai_beszelgetes", String(bid));
      } catch {
        /* privát mód */
      }
      const r = await authFetch(`/api/v1/ai-assistant/beszelgetesek/${bid}/uzenetek`);
      if (r.ok) {
        const d = await r.json();
        uzenetBeolvaszt(d.uzenetek);
        setFut(Boolean(d.fut));
      }
      void naploFrissit(bid);
    },
    [uzenetBeolvaszt, naploFrissit],
  );

  useEffect(() => {
    (async () => {
      const r = await authFetch("/api/v1/ai-assistant/beszelgetesek");
      if (!r.ok) return;
      const lista: Beszelgetes[] = await r.json();
      setBeszelgetesek(lista);
      let mentett: number | null = null;
      try {
        mentett = Number(localStorage.getItem("ai_beszelgetes")) || null;
      } catch {
        /* privát mód */
      }
      const cel = lista.find((b) => b.id === mentett) ?? lista[0];
      if (cel) void beszelgetesValt(cel.id);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // FOLYAMATJELZÉS: futó kör alatt 1,5 mp-enként lehúzzuk az új eseményeket -
  // a lépések („Megkerestem a projektet…") élőben jelennek meg, és
  // oldalfrissítés után is a valós állapot áll vissza.
  useEffect(() => {
    if (!aktiv || (!fut && !busy)) return;
    const t = setInterval(async () => {
      try {
        const r = await authFetch(`/api/v1/ai-assistant/beszelgetesek/${aktiv}/uzenetek?utani=${utolsoIdRef.current}`);
        if (r.ok) {
          const d = await r.json();
          uzenetBeolvaszt(d.uzenetek);
          setFut(Boolean(d.fut));
        }
      } catch {
        /* következő kör */
      }
    }, 1500);
    return () => clearInterval(t);
  }, [aktiv, fut, busy, uzenetBeolvaszt]);

  async function ujBeszelgetes(): Promise<number | null> {
    const r = await authFetch("/api/v1/ai-assistant/beszelgetesek", { method: "POST" });
    if (!r.ok) return null;
    const b: Beszelgetes = await r.json();
    setBeszelgetesek((prev) => [b, ...prev]);
    await beszelgetesValt(b.id);
    return b.id;
  }

  async function kuldes() {
    const t = szoveg.trim();
    if (!t || busy) return;
    setBusy(true);
    setHiba(null);
    try {
      let bid = aktiv;
      if (bid === null) bid = await ujBeszelgetes();
      if (bid === null) {
        setHiba("Nem sikerült beszélgetést nyitni.");
        return;
      }
      // Előbb a fájlok mennek fel a beszélgetéshez - az asszisztens fajl_id
      // alapján használja őket (számla-érkeztetés, csatolás).
      const kuldendo = [...fajlok];
      setFajlok([]);
      for (const f of kuldendo) {
        const fd = new FormData();
        fd.append("file", f);
        const r = await authFetch(`/api/v1/ai-assistant/beszelgetesek/${bid}/fajl`, { method: "POST", body: fd });
        if (!r.ok) {
          const d = await r.json().catch(() => null);
          setHiba(`A(z) ${f.name} feltöltése nem sikerült: ${d?.detail ?? r.status}`);
        }
      }
      setSzoveg("");
      const r = await authFetch(`/api/v1/ai-assistant/beszelgetesek/${bid}/uzenet`, {
        method: "POST",
        body: JSON.stringify({ szoveg: t, kontextus }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => null);
        setHiba(`Sikertelen: ${d?.detail ?? r.status}`);
        return;
      }
      const d = await r.json();
      uzenetBeolvaszt(d.uzenetek);
      setBeszelgetesek((prev) => prev.map((b) => (b.id === bid && !b.cim ? { ...b, cim: t.slice(0, 120) } : b)));
      void naploFrissit(bid);
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
      setFut(false);
      gorgetes();
    }
  }

  async function leallitas() {
    if (!aktiv) return;
    await authFetch(`/api/v1/ai-assistant/beszelgetesek/${aktiv}/leallitas`, { method: "POST" }).catch(() => null);
  }

  async function dontes(muveletId: number, jovahagyva: boolean) {
    if (!aktiv) return;
    setBusy(true);
    try {
      const r = await authFetch(`/api/v1/ai-assistant/muveletek/${muveletId}/dontes`, {
        method: "POST",
        body: JSON.stringify({ jovahagyva }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) setHiba(`A döntés nem sikerült: ${d?.detail ?? r.status}`);
      // A determinista eredmény-üzenet a szerveren jött létre - lehúzzuk.
      const ru = await authFetch(`/api/v1/ai-assistant/beszelgetesek/${aktiv}/uzenetek?utani=${utolsoIdRef.current}`);
      if (ru.ok) uzenetBeolvaszt((await ru.json()).uzenetek);
      void naploFrissit(aktiv);
    } finally {
      setBusy(false);
    }
  }

  // Kétfázisú törlés (nem böngésző-confirm, mert az némítható): az első
  // kattintás élesít, a második töröl.
  const [torlendo, setTorlendo] = useState<number | null>(null);
  useEffect(() => {
    if (torlendo === null) return;
    const t = setTimeout(() => setTorlendo(null), 5000);
    return () => clearTimeout(t);
  }, [torlendo]);

  async function beszelgetesTorles(bid: number) {
    if (torlendo !== bid) {
      setTorlendo(bid);
      return;
    }
    setTorlendo(null);
    await authFetch(`/api/v1/ai-assistant/beszelgetesek/${bid}`, { method: "DELETE" }).catch(() => null);
    setBeszelgetesek((prev) => prev.filter((b) => b.id !== bid));
    if (aktiv === bid) {
      setAktiv(null);
      setUzenetek([]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void kuldes();
    }
  }

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* Beszélgetés-lista */}
      <div className="hidden w-[220px] shrink-0 flex-col gap-1 overflow-y-auto border-r border-border pr-2 md:flex">
        <button
          type="button"
          onClick={() => void ujBeszelgetes()}
          className="flex items-center gap-1 rounded-[var(--radius)] border border-border px-2 py-1.5 text-[12.5px] text-text-accent hover:bg-surface-3"
        >
          <Plus size={13} /> Új beszélgetés
        </button>
        {beszelgetesek.map((b) => (
          <div
            key={b.id}
            className={`group flex items-center gap-1 rounded-[var(--radius)] px-2 py-1.5 text-[12.5px] ${aktiv === b.id ? "bg-bg-accent text-text-accent" : "text-text-secondary hover:bg-surface-3"}`}
          >
            <button type="button" onClick={() => void beszelgetesValt(b.id)} className="min-w-0 flex-1 truncate text-left">
              {b.cim ?? `Beszélgetés #${b.id}`}
            </button>
            <button
              type="button"
              title={torlendo === b.id ? "Még egy kattintás a végleges törléshez" : "Beszélgetés törlése (két kattintás)"}
              onClick={() => void beszelgetesTorles(b.id)}
              className={torlendo === b.id ? "block text-text-danger" : "hidden text-text-muted hover:text-text-danger group-hover:block"}
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>

      {/* Chat */}
      <div className="flex min-h-0 flex-1 flex-col">
        {kontextus && (
          <p className="mb-1.5 rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1 text-[12px] text-text-secondary">
            Erre hivatkozol: <b className="text-text-primary">{String(kontextus.cim ?? kontextus.entity_type ?? kontextus.utvonal)}</b>
            {kontextus.entity_id ? ` (#${kontextus.entity_id})` : ""} — az „ez"/„ennél" ezt jelenti.
          </p>
        )}
        <div className="mb-3 flex-1 space-y-2 overflow-y-auto pr-1">
          {uzenetek.length === 0 && (
            <p className="text-[13px] text-text-muted">
              Írd le, mit szeretnél a rendszerben - az asszisztens megkeresi az adatokat, elvégzi a műveletet a
              megszokott folyamatokon, ellenőrzi, és linkelt összefoglalót ad. Példák: „Keresd meg XY szeptemberi
              elszámolását az utókövetésben." · „Ehhez az utómunkához írd oda kommentben: …" · „Hozz létre egy
              feladatot Martinnak ehhez a projekthez." · Számlát is bedobhatsz (📎 vagy húzd ide), írd mellé, hová
              tartozik. A törlések és a pénzügyi felvezetések előbb jóváhagyás-kártyán jelennek meg.
            </p>
          )}
          {uzenetek.map((u) => (
            <UzenetSor key={u.id} u={u} naplo={naplo} busy={busy} onDontes={dontes} />
          ))}
          {(busy || fut) && (
            <p className="flex items-center gap-2 text-[12.5px] text-text-muted">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-text-accent" />
              Az asszisztens dolgozik…
              <button type="button" onClick={() => void leallitas()} className="flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[11.5px] text-text-secondary hover:bg-surface-3">
                <Square size={10} /> Leállítás
              </button>
            </p>
          )}
          <div ref={bottomRef} />
        </div>

        {hiba && <p className="mb-1.5 text-[12.5px] text-text-danger">{hiba}</p>}
        {fajlok.length > 0 && (
          <div className="mb-1.5 flex flex-wrap gap-1.5">
            {fajlok.map((f, i) => (
              <span key={i} className="flex items-center gap-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-0.5 text-[12px] text-text-secondary">
                📎 {f.name}
                <button type="button" onClick={() => setFajlok(fajlok.filter((_, j) => j !== i))}>
                  <X size={11} />
                </button>
              </span>
            ))}
          </div>
        )}

        <div
          className="flex gap-2"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const ujak = Array.from(e.dataTransfer.files || []);
            if (ujak.length) setFajlok((prev) => [...prev, ...ujak]);
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              const ujak = Array.from(e.target.files || []);
              if (ujak.length) setFajlok((prev) => [...prev, ...ujak]);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            title="Fájl csatolása (számla, Excel-részletező, dokumentum) - vagy húzd ide"
            onClick={() => fileInputRef.current?.click()}
            className="rounded-[var(--radius)] border border-border px-2.5 text-text-secondary hover:bg-surface-3"
          >
            <Paperclip size={15} />
          </button>
          <textarea
            rows={2}
            value={szoveg}
            onChange={(e) => setSzoveg(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              fajlok.length > 0
                ? "Írd le, mi legyen a fájlokkal… (pl. Ezt a számlát a HYPE26-0291-hez, XY utókövetési tételéhez)"
                : "Írd le, mit szeretnél… (Enter a küldéshez, Shift+Enter új sor)"
            }
            className="flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
          <button
            type="button"
            disabled={busy || !szoveg.trim()}
            onClick={() => void kuldes()}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Küldés
          </button>
        </div>
      </div>
    </div>
  );
}

function UzenetSor({
  u,
  naplo,
  busy,
  onDontes,
}: {
  u: Uzenet;
  naplo: Record<number, NaploSor>;
  busy: boolean;
  onDontes: (muveletId: number, jovahagyva: boolean) => void;
}) {
  const adat = u.adat ?? {};
  if (u.szerep === "esemeny") {
    if (adat.tipus === "megerosites") {
      const mid = Number(adat.muvelet_id);
      const allapot = naplo[mid]?.allapot ?? "fuggo";
      return (
        <div className="mr-auto w-full max-w-[560px] rounded-[var(--radius)] border border-text-warning/50 bg-bg-warning/40 p-3 text-[13px]">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-warning">Jóváhagyásra vár</p>
          <p className="text-text-primary">{String(adat.osszefoglalo ?? "")}</p>
          <p className="mt-0.5 text-[11.5px] text-text-muted">
            {String(adat.method)} {String(adat.path)}
          </p>
          {adat.keres != null && (
            <details className="mt-1">
              <summary className="cursor-pointer text-[11.5px] text-text-accent">A művelet pontos tartalma</summary>
              <pre className="mt-1 max-h-[140px] overflow-auto rounded bg-surface-2 p-2 text-[11px] text-text-secondary">
                {JSON.stringify(adat.keres, null, 2)}
              </pre>
            </details>
          )}
          {allapot === "fuggo" ? (
            <div className="mt-2 flex gap-1.5">
              <button
                type="button"
                disabled={busy}
                onClick={() => onDontes(mid, true)}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-2.5 py-1 text-[12.5px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                Jóváhagyás
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onDontes(mid, false)}
                className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Elvetés
              </button>
            </div>
          ) : (
            <p className="mt-1.5 text-[12px] text-text-secondary">
              {allapot === "vegrehajtva" ? "✓ Jóváhagyva és végrehajtva." : allapot === "elutasitva" ? "Elvetve - nem történt módosítás." : `Állapot: ${allapot}`}
            </p>
          )}
        </div>
      );
    }
    if (adat.tipus === "bejovo_szamla") {
      return (
        <div className="mr-auto w-full max-w-[520px] rounded-[var(--radius)] border border-border bg-surface-1 p-3 text-[13px]">
          <p className="mb-1 text-[11px] font-medium text-text-muted">SZÁMLA-PISZKOZAT #{String(adat.bejovo_id)}</p>
          <p className="text-text-primary">
            <b>{String(adat.kibocsato_nev ?? "Ismeretlen kibocsátó")}</b>
            {adat.szamlaszam ? ` · ${adat.szamlaszam}` : ""}
          </p>
          <p className="text-text-secondary">
            {adat.netto != null ? `${formatSzam(Number(adat.netto))} ${String(adat.penznem ?? "")} nettó · ` : ""}
            állapot: {String(adat.allapot ?? "?")}
            {adat.cel_cimke ? ` · cél: ${adat.cel_cimke}` : ""}
          </p>
          {adat.javaslat_indoklas ? <p className="mt-0.5 text-[12px] text-text-muted">{String(adat.javaslat_indoklas)}</p> : null}
          <Link
            href={`/penzugyek/bejovo-szamlak?id=${adat.bejovo_id}`}
            className="mt-1.5 inline-block rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-accent hover:bg-surface-3"
          >
            Megnyitás az ellenőrzőben →
          </Link>
        </div>
      );
    }
    if (!u.szoveg) return null;
    return <p className="pl-1 text-[12px] text-text-muted">· {u.szoveg}</p>;
  }
  return (
    <div
      className={`rounded-[var(--radius)] p-3 text-[13px] ${
        u.szerep === "felhasznalo" ? "ml-auto max-w-[80%] bg-surface-3 text-text-primary" : "mr-auto max-w-[85%] bg-surface-1 text-text-primary"
      }`}
    >
      <p className="mb-1 text-[11px] font-medium text-text-muted">{u.szerep === "felhasznalo" ? "Te" : "AI Assistant"}</p>
      <Szoveg szoveg={u.szoveg ?? ""} />
      {u.szerep === "felhasznalo" && Array.isArray(adat.fajlok) && adat.fajlok.length > 0 && (
        <p className="mt-1 text-[11.5px] text-text-muted">📎 {(adat.fajlok as string[]).join(", ")}</p>
      )}
    </div>
  );
}
