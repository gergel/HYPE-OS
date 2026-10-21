"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Mic, Paperclip, Plus, Square, Trash2, X } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { formatSzam } from "@/lib/penz";
import { Markdown } from "@/components/Markdown";

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

// A chat-üzenetek (a sajátjaid és az asszisztensé is) teljes markdown-
// formázással jelennek meg - címsor, félkövér, felsorolás, kód, link (lásd
// components/Markdown.tsx).

/** `kompakt`: keskeny panelben (TopBar-ról nyitott oldalsáv) - a
 * beszélgetés-lista helyett mindig a legördülő váltó látszik.
 * `oldalKontextus`: a panelt nyitó oldal (útvonal + cím) - ilyenkor ez a
 * kontextus az URL-paraméterek helyett. */
export function AiAssistantChat({
  kompakt = false,
  oldalKontextus = null,
}: {
  kompakt?: boolean;
  oldalKontextus?: { utvonal: string; cim?: string } | null;
} = {}) {
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
  const listaRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const utolsoIdRef = useRef(0);
  //: DIKTÁLÁS (a felhasználó kérése: ne csak gépelni lehessen). Elsődlegesen
  //: a böngésző beépített beszédfelismerése (Web Speech API, hu-HU) megy -
  //: élőben írja a mezőbe; ahol az nincs, hangfelvétel készül és a szerver
  //: írja át (Gemini). Az eredmény MINDIG csak a beviteli mezőbe kerül - a
  //: küldés a felhasználó döntése marad.
  const [diktalas, setDiktalas] = useState<"inaktiv" | "hallgat" | "felvesz" | "atir">("inaktiv");
  const felismeroRef = useRef<{ stop: () => void } | null>(null);
  const felvevoRef = useRef<MediaRecorder | null>(null);
  const diktalasBazisRef = useRef("");

  // Oldal-kontextus, ha másik oldalról nyitották az asszisztenst
  // (?entity=deliverable&rekord=123&cim=...): az „ez"/„ennél" erre mutat.
  const kontextus = useMemo(() => {
    if (oldalKontextus) return { utvonal: oldalKontextus.utvonal, ...(oldalKontextus.cim ? { cim: oldalKontextus.cim } : {}) };
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
  }, [searchParams, oldalKontextus]);

  /** Az üzenetlista aljára görgetés - CSAK a lista dobozát mozgatja, sosem az
   * egész oldalt (a felhasználó hibajelzése: az oldal "mindig letekert és
   * ugrált"). Alapból csak akkor görget, ha az olvasó amúgy is az alján áll -
   * aki feljebb tekert olvasni, azt egy közben érkező lépés-üzenet nem
   * rángatja le. A `mindenkepp` a saját küldésnél / beszélgetés-váltásnál
   * igaz: olyankor tényleg az alja kell. */
  function gorgetes(mindenkepp = false) {
    const doboz = listaRef.current;
    if (!doboz) return;
    // A mérés MOST történik (az új tartalom renderelése előtt): azt mondja
    // meg, az olvasó eddig lent állt-e.
    const lentVolt = doboz.scrollHeight - doboz.scrollTop - doboz.clientHeight < 160;
    if (!mindenkepp && !lentVolt) return;
    setTimeout(() => {
      const d = listaRef.current;
      if (d) d.scrollTop = d.scrollHeight;
    }, 50);
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

  //: A kezdeti beszélgetés-lista KÉSEI válasza ne írja felül a közben már
  //: (pl. az „Új beszélgetés" gombbal) megnyitott szálat - a ref a state
  //: zárvány-problémája nélkül mondja meg, van-e már aktív választás.
  const aktivRef = useRef<number | null>(null);

  const beszelgetesValt = useCallback(
    async (bid: number) => {
      aktivRef.current = bid;
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
      // Beszélgetés-váltásnál mindig az aljára ugrunk (ott a friss rész).
      gorgetes(true);
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
      if (cel && aktivRef.current === null) void beszelgetesValt(cel.id);
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
    } catch {
      // HOSSZÚ futásnál (sok lépés) a kapcsolat megszakadhat, miközben a
      // munka a szerveren rendben fut tovább - a polling hozza az
      // eredményt, nem hibaként kezeljük. Ha valójában nem fut semmi, az
      // első lekérdezés jelzi (fut=false), és a jelzés eltűnik.
      setFut(true);
      setHiba("A kapcsolat megszakadt - ha a munka a szerveren fut, a lépések és az eredmény itt jelennek meg.");
    } finally {
      setBusy(false);
      setFut(false);
      gorgetes(true);
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

  function diktalasLeallitas() {
    felismeroRef.current?.stop();
    felismeroRef.current = null;
    if (felvevoRef.current && felvevoRef.current.state !== "inactive") felvevoRef.current.stop();
  }

  /** iPhone/iPad felismerése. iOS-en a webkitSpeechRecognition LÉTEZIK, de
   * hibás: az indítása lefagyaszthatja az egész oldalt - főleg a
   * kezdőképernyőre kitett, "appként" megnyitott felületen. Ott ezért eleve
   * a felvétel + szerveri átírás megy, ami iOS-en megbízható. (Az újabb
   * iPadek Macnek hazudják magukat, ezért a maxTouchPoints-ellenőrzés is.) */
  function iosEszkoz(): boolean {
    const ua = navigator.userAgent;
    return /iPhone|iPad|iPod/.test(ua) || (ua.includes("Mac") && navigator.maxTouchPoints > 1);
  }

  /** TARTALÉK diktálás: hangfelvétel, a szöveget a szerver írja le (Gemini). */
  async function felvetelInditas() {
    try {
      // Zajszűrés + visszhang-elnyomás + automatikus erősítés: telefonon ez
      // érezhetően pontosabb átírást ad (a felhasználó hibajelzése: a
      // diktálás hibázott); a mono sáv pedig kisebb fájl - gyorsabb feltöltés.
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
      // iOS/Safari nem tud webm-et rögzíteni, ott mp4 készül - a szerver a
      // valódi mime-típust kapja meg, a Gemini mindkettőt átírja.
      const tamogatott = ["audio/webm", "audio/mp4"].find(
        (t) => typeof MediaRecorder.isTypeSupported !== "function" || MediaRecorder.isTypeSupported(t),
      );
      // 64 kbit/s beszédhez bőven elég - a kisebb felvétel hamarabb ér fel a
      // szerverre, így hamarabb jön a szöveg (a felhasználó kérése: gyorsabban).
      const opciok: MediaRecorderOptions = { audioBitsPerSecond: 64_000, ...(tamogatott ? { mimeType: tamogatott } : {}) };
      let felvevo: MediaRecorder;
      try {
        felvevo = new MediaRecorder(stream, opciok);
      } catch {
        felvevo = new MediaRecorder(stream);
      }
      const darabok: Blob[] = [];
      felvevo.ondataavailable = (e) => {
        if (e.data.size > 0) darabok.push(e.data);
      };
      felvevo.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        felvevoRef.current = null;
        setDiktalas("atir");
        try {
          const tipus = felvevo.mimeType || tamogatott || "audio/webm";
          const blob = new Blob(darabok, { type: tipus });
          const fd = new FormData();
          fd.append("file", blob, tipus.includes("mp4") ? "diktalas.m4a" : "diktalas.webm");
          const res = await authFetch("/api/v1/ai-assistant/atiras", { method: "POST", body: fd });
          const d = await res.json().catch(() => null);
          if (!res.ok) {
            setHiba(`Az átírás nem sikerült: ${d?.detail ?? res.status}`);
          } else if (d?.szoveg) {
            setSzoveg((elozo) => (elozo ? elozo.replace(/\s+$/, "") + " " + d.szoveg : d.szoveg));
          } else {
            setHiba("A felvételen nem hallatszott beszéd.");
          }
        } catch (err) {
          setHiba(`Hálózati hiba az átírásnál: ${err}`);
        } finally {
          setDiktalas("inaktiv");
        }
      };
      felvevoRef.current = felvevo;
      felvevo.start();
      setDiktalas("felvesz");
    } catch {
      setHiba("A mikrofon nem érhető el - engedélyezd a böngészőben a diktáláshoz.");
      setDiktalas("inaktiv");
    }
  }

  async function diktalasValt() {
    if (diktalas !== "inaktiv") {
      diktalasLeallitas();
      return;
    }
    setHiba(null);
    const w = window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
    const FelismeroOsztaly = (w.SpeechRecognition ?? w.webkitSpeechRecognition) as
      | (new () => {
          lang: string;
          continuous: boolean;
          interimResults: boolean;
          onstart: (() => void) | null;
          onaudiostart: (() => void) | null;
          onresult: ((e: { resultIndex: number; results: { length: number; [i: number]: { isFinal: boolean; [j: number]: { transcript: string } } } }) => void) | null;
          onerror: ((e: { error?: string }) => void) | null;
          onend: (() => void) | null;
          start: () => void;
          stop: () => void;
          abort?: () => void;
        })
      | undefined;

    if (FelismeroOsztaly && !iosEszkoz()) {
      // ÉLŐ diktálás a böngésző beszédfelismerésével.
      try {
        const felismero = new FelismeroOsztaly();
        felismero.lang = "hu-HU";
        felismero.continuous = true;
        felismero.interimResults = true;
        diktalasBazisRef.current = szoveg ? szoveg.replace(/\s+$/, "") + " " : "";
        // ŐRIDŐ: néhány böngésző (pl. Brave, régebbi Edge) kirakja az
        // osztályt, de a felismerés sosem indul el - hibajelzés sem jön,
        // csak "hallgat" állapotban ragadna a gomb. Ha pár másodpercen
        // belül nincs életjel, csendben átváltunk a felvétel-útra.
        let eletjel = false;
        const jelez = () => {
          eletjel = true;
        };
        const ora = window.setTimeout(() => {
          if (eletjel || felismeroRef.current !== felismero) return;
          felismero.onend = null;
          felismeroRef.current = null;
          try {
            (felismero.abort ?? felismero.stop).call(felismero);
          } catch {
            // az elakadt felismerő leállítása is dobhat - nem érdekes
          }
          void felvetelInditas();
        }, 4000);
        felismero.onstart = jelez;
        felismero.onaudiostart = jelez;
        felismero.onresult = (e) => {
          jelez();
          let vegleges = "";
          let koztes = "";
          for (let i = 0; i < e.results.length; i++) {
            const r = e.results[i];
            if (r.isFinal) vegleges += r[0].transcript;
            else koztes += r[0].transcript;
          }
          setSzoveg((diktalasBazisRef.current + vegleges + koztes).replace(/^\s+/, ""));
        };
        felismero.onerror = (e) => {
          jelez();
          if (e.error === "not-allowed" || e.error === "service-not-allowed") {
            setHiba("A mikrofon-hozzáférés le van tiltva - engedélyezd a böngészőben a diktáláshoz.");
          }
        };
        felismero.onend = () => {
          window.clearTimeout(ora);
          felismeroRef.current = null;
          setDiktalas("inaktiv");
        };
        felismeroRef.current = felismero;
        felismero.start();
        setDiktalas("hallgat");
        return;
      } catch {
        // Nem sikerült elindítani - jön a felvétel + szerveri átírás.
      }
    }

    await felvetelInditas();
  }

  return (
    // flex-1 (nem h-full): a szülő Card flex-oszlop, benne a cím UTÁN maradó
    // helyet kell kitölteni - a h-full a cím magasságával túllógott volna.
    <div className="flex min-h-0 flex-1 gap-3">
      {/* Beszélgetés-lista */}
      <div className={`hidden w-[220px] shrink-0 flex-col gap-1 overflow-y-auto border-r border-border pr-2 ${kompakt ? "" : "md:flex"}`}>
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
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* MOBIL beszélgetés-váltó (a felhasználó hibajelzése: telefonon
            szétesett az oldal, és váltani sem lehetett): a bal oldali lista
            kis képernyőn el van rejtve, helyette legördülő + Új gomb. */}
        <div className={`mb-2 flex items-center gap-1.5 ${kompakt ? "" : "md:hidden"}`}>
          <select
            value={aktiv ?? ""}
            onChange={(e) => e.target.value && void beszelgetesValt(Number(e.target.value))}
            className="min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
          >
            {beszelgetesek.length === 0 && <option value="">Még nincs beszélgetés</option>}
            {beszelgetesek.map((b) => (
              <option key={b.id} value={b.id}>
                {b.cim ?? `Beszélgetés #${b.id}`}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void ujBeszelgetes()}
            title="Új beszélgetés"
            className="flex items-center gap-1 rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[12.5px] text-text-accent hover:bg-surface-3"
          >
            <Plus size={14} /> Új
          </button>
        </div>
        {kontextus && (
          <p className="mb-1.5 rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1 text-[12px] text-text-secondary">
            Erre hivatkozol: <b className="text-text-primary">{String(kontextus.cim ?? kontextus.entity_type ?? kontextus.utvonal)}</b>
            {kontextus.entity_id ? ` (#${kontextus.entity_id})` : ""} — az „ez"/„ennél" ezt jelenti.
          </p>
        )}
        <div ref={listaRef} className="mb-3 flex-1 space-y-2 overflow-y-auto pr-1">
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
        </div>

        {hiba && <p className="mb-1.5 text-[12.5px] text-text-danger">{hiba}</p>}
        {diktalas !== "inaktiv" && (
          <p className="mb-1.5 flex items-center gap-1.5 text-[12.5px] text-text-danger">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-text-danger" />
            {diktalas === "atir" ? "A felvételt írom le…" : "Diktálás folyamatban - kattints a mikrofonra a befejezéshez."}
          </p>
        )}
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
          <button
            type="button"
            disabled={diktalas === "atir"}
            title={
              diktalas === "hallgat" || diktalas === "felvesz"
                ? "Diktálás leállítása"
                : "Diktálás - mondd el, mit szeretnél; a szöveg a mezőbe kerül, a küldés a tiéd"
            }
            onClick={() => void diktalasValt()}
            className={`rounded-[var(--radius)] border px-2.5 disabled:opacity-50 ${
              diktalas === "hallgat" || diktalas === "felvesz"
                ? "border-text-danger bg-text-danger/15 text-text-danger"
                : "border-border text-text-secondary hover:bg-surface-3"
            }`}
          >
            <Mic size={15} className={diktalas === "hallgat" || diktalas === "felvesz" ? "animate-pulse" : ""} />
          </button>
          <textarea
            rows={2}
            value={szoveg}
            onChange={(e) => setSzoveg(e.target.value)}
            title="Formázhatsz: **félkövér**, *dőlt*, # címsor, - felsorolás, 1. számozott lista, `kód`"
            placeholder={
              fajlok.length > 0
                ? "Írd le, mi legyen a fájlokkal… (pl. Ezt a számlát a HYPE26-0291-hez, XY utókövetési tételéhez)"
                : "Írd le, mit szeretnél… (a Küldés gombbal küldöd el · formázás: **félkövér**, - felsorolás, # címsor)"
            }
            className="min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
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
      className={`rounded-[var(--radius)] p-3 text-[13px] [overflow-wrap:anywhere] ${
        u.szerep === "felhasznalo" ? "ml-auto max-w-[80%] bg-surface-3 text-text-primary" : "mr-auto max-w-[85%] bg-surface-1 text-text-primary"
      }`}
    >
      <p className="mb-1 text-[11px] font-medium text-text-muted">{u.szerep === "felhasznalo" ? "Te" : "AI Assistant"}</p>
      <Markdown szoveg={u.szoveg ?? ""} />
      {u.szerep === "felhasznalo" && Array.isArray(adat.fajlok) && adat.fajlok.length > 0 && (
        <p className="mt-1 text-[11.5px] text-text-muted">📎 {(adat.fajlok as string[]).join(", ")}</p>
      )}
    </div>
  );
}
