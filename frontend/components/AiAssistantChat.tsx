"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Paperclip, X } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { formatSzam } from "@/lib/penz";
import type { BejovoSzamlaReszlet } from "@/lib/api";

type ChatMessage =
  | { role: "user" | "assistant"; text: string }
  | { role: "kartya"; adat: BejovoSzamlaReszlet };

const CEL_CIMKEK: Record<string, string> = {
  kiadas_uj: "Új kiadás",
  kiadas_csatolas: "Számla meglévő kiadáshoz",
  kulsos_tig: "Meglévő külsős TIG számlája",
  belsos_tig: "Meglévő belsős TIG számlája",
  erezsi: "E-Rezsi előfizetés számlája",
  auto: "Autó költsége",
  kp: "KP-bizonylat pótlása",
  mukodesi: "Általános működési költség",
  kimeno: "Kimenő számla",
  egyeb: "Tisztázandó",
};

/** Kérdés/válasz chat + SZÁMLA-BEDOBÁS (a felhasználó kérése): PDF-et vagy
 * fotót csatolva, a szöveggel együtt („ezt a HYPE26-0291-hez, catering") a
 * rendszer a KÖZÖS érkeztető-folyamaton kiolvassa, megkeresi a helyét, és
 * MENTETT piszkozatot készít - a chatben ellenőrzőkártya jelenik meg, a
 * folytató üzenetek („mégis a másik projekthez") ugyanazt a piszkozatot
 * módosítják. A tényleges rögzítés csak a Jóváhagyás gombbal történik, és
 * csak sikeres szerver-mentés után mondjuk, hogy megtörtént. */
export function AiAssistantChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [fajlok, setFajlok] = useState<File[]>([]);
  // A legutóbb létrejött/módosított piszkozat - a folytató üzenetek ezt
  // pontosítják, amíg a felhasználó vissza nem vált kérdezésre.
  const [aktivPiszkozat, setAktivPiszkozat] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function gorgetes() {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  function kartyaCsere(adat: BejovoSzamlaReszlet) {
    setMessages((prev) => {
      const t = [...prev];
      for (let i = t.length - 1; i >= 0; i--) {
        const m = t[i];
        if (m.role === "kartya" && m.adat.id === adat.id) {
          t[i] = { role: "kartya", adat };
          return t;
        }
      }
      return [...t, { role: "kartya", adat }];
    });
  }

  async function send() {
    const trimmed = question.trim();
    if ((!trimmed && fajlok.length === 0) || busy) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", text: trimmed + (fajlok.length ? `\n📎 ${fajlok.map((f) => f.name).join(", ")}` : "") },
    ]);
    setQuestion("");
    setBusy(true);
    try {
      if (fajlok.length > 0) {
        // SZÁMLA-BEDOBÁS: minden fájlból közös érkeztető-piszkozat készül, a
        // beírt szöveg a besorolási utasítás.
        const kuldendo = [...fajlok];
        setFajlok([]);
        for (const fajl of kuldendo) {
          const fd = new FormData();
          fd.append("file", fajl);
          fd.append("utasitas", trimmed);
          const res = await authFetch("/api/v1/bejovo-szamlak/feltoltes", { method: "POST", body: fd });
          if (!res.ok) {
            const d = await res.json().catch(() => null);
            setMessages((prev) => [
              ...prev,
              { role: "assistant", text: `Nem sikerült feldolgozni a(z) ${fajl.name} fájlt: ${d?.detail ?? res.status}` },
            ]);
            continue;
          }
          const adat: BejovoSzamlaReszlet = await res.json();
          setMessages((prev) => [...prev, { role: "kartya", adat }]);
          setAktivPiszkozat(adat.id);
        }
      } else if (aktivPiszkozat !== null) {
        // FOLYTATÁS: a szöveg UGYANAZT a piszkozatot pontosítja - a szerver
        // az utasítással újrajavasol, és a kártya frissül.
        const res = await authFetch(`/api/v1/bejovo-szamlak/${aktivPiszkozat}`, {
          method: "PATCH",
          body: JSON.stringify({ felhasznaloi_utasitas: trimmed }),
        });
        if (!res.ok) {
          const d = await res.json().catch(() => null);
          setMessages((prev) => [...prev, { role: "assistant", text: `Nem sikerült módosítani a piszkozatot: ${d?.detail ?? res.status}` }]);
        } else {
          const adat: BejovoSzamlaReszlet = await res.json();
          kartyaCsere(adat);
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: `Frissítettem a piszkozatot az utasításod szerint - nézd meg a kártyát fent. (${adat.javaslat?.indoklas ?? ""})` },
          ]);
        }
      } else {
        const res = await authFetch("/api/v1/ai-assistant/ask", {
          method: "POST",
          body: JSON.stringify({ question: trimmed }),
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          setMessages((prev) => [...prev, { role: "assistant", text: `Hiba: ${detail?.detail ?? res.status}` }]);
          return;
        }
        const data: { answer: string } = await res.json();
        setMessages((prev) => [...prev, { role: "assistant", text: data.answer }]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", text: `Hálózati hiba: ${err}` }]);
    } finally {
      setBusy(false);
      gorgetes();
    }
  }

  async function jovahagyas(id: number) {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/bejovo-szamlak/${id}/jovahagyas`, { method: "POST", body: JSON.stringify({}) });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        // NEM állítjuk, hogy mentettünk - a hibát mondjuk el.
        setMessages((prev) => [...prev, { role: "assistant", text: `A rögzítés nem sikerült: ${d?.detail ?? res.status}` }]);
        return;
      }
      const adat: BejovoSzamlaReszlet = d;
      kartyaCsere(adat);
      const letrejott = (adat.rogzites_naplo?.letrejott ?? []).map((l) => `#${l.id}`).join(", ");
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text:
            `Rögzítve. ${letrejott ? `Létrejött kiadás: ${letrejott} (nem kifizetettként). ` : "A számla a meglévő tételhez került. "}` +
            `A tételt a Beérkező számlák oldalon és a megfelelő pénzügyi nézetben találod.`,
        },
      ]);
      if (aktivPiszkozat === id) setAktivPiszkozat(null);
    } finally {
      setBusy(false);
      gorgetes();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div
      className="flex h-full flex-col"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const ujak = Array.from(e.dataTransfer.files || []);
        if (ujak.length) setFajlok((prev) => [...prev, ...ujak]);
      }}
    >
      <div className="mb-4 flex-1 space-y-3 overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-[13px] text-text-muted">
            Kérdezz bármit a projektekről, ügyfelekről, csapatról, felszerelésről, feladatokról vagy
            pénzügyekről - csak azokból az adatokból válaszol, amikhez neked hozzáférésed van. ÚJ: dobj be egy
            számlát (PDF vagy fotó, húzd ide vagy 📎), írd mellé, hová tartozik (pl. „Ezt a HYPE26-0291-hez,
            catering"), és előkészítem a rögzítést - neked csak jóváhagyni kell.
          </p>
        )}
        {messages.map((m, i) =>
          m.role === "kartya" ? (
            <SzamlaKartya key={i} adat={m.adat} busy={busy} onJovahagyas={jovahagyas} />
          ) : (
            <div
              key={i}
              className={`rounded-[var(--radius)] p-3 text-[13px] ${
                m.role === "user"
                  ? "ml-auto max-w-[80%] bg-surface-3 text-text-primary"
                  : "mr-auto max-w-[80%] bg-surface-1 text-text-primary"
              }`}
            >
              <p className="mb-1 text-[11px] font-medium text-text-muted">{m.role === "user" ? "Te" : "AI Assistant"}</p>
              <p className="whitespace-pre-line">{m.text}</p>
            </div>
          ),
        )}
        {busy && <p className="text-[13px] text-text-muted">AI Assistant dolgozik…</p>}
        <div ref={bottomRef} />
      </div>

      {aktivPiszkozat !== null && (
        <p className="mb-1.5 flex items-center gap-2 text-[12px] text-text-accent">
          A következő üzenetek a #{aktivPiszkozat} számla-piszkozatot pontosítják.
          <button type="button" onClick={() => setAktivPiszkozat(null)} className="text-text-muted hover:underline">
            Vissza a kérdezéshez
          </button>
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

      <div className="flex gap-2">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="application/pdf,image/jpeg,image/png,image/webp,image/heic"
          className="hidden"
          onChange={(e) => {
            const ujak = Array.from(e.target.files || []);
            if (ujak.length) setFajlok((prev) => [...prev, ...ujak]);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          title="Számla csatolása (PDF vagy fotó) - vagy húzd ide a fájlt"
          onClick={() => fileInputRef.current?.click()}
          className="rounded-[var(--radius)] border border-border px-2.5 text-text-secondary hover:bg-surface-3"
        >
          <Paperclip size={15} />
        </button>
        <textarea
          rows={2}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            fajlok.length > 0
              ? "Írd le, hová tartozik a számla… (pl. Ezt a HYPE26-0291-hez, catering)"
              : aktivPiszkozat !== null
                ? "Pontosítsd a piszkozatot… (pl. mégis a másik projekthez / ne hozz létre új kiadást)"
                : "Kérdezz valamit… (Enter a küldéshez, Shift+Enter új sorhoz)"
          }
          className="flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
        />
        <button
          type="button"
          disabled={busy || (!question.trim() && fajlok.length === 0)}
          onClick={send}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          Küldés
        </button>
      </div>
    </div>
  );
}

/** Az interaktív ELLENŐRZŐKÁRTYA: a felismert számla, a javasolt cél, a
 * hiányzó/bizonytalan adatok és a műveletek. */
function SzamlaKartya({
  adat,
  busy,
  onJovahagyas,
}: {
  adat: BejovoSzamlaReszlet;
  busy: boolean;
  onJovahagyas: (id: number) => void;
}) {
  const bizonytalan = adat.kinyert?.bizonytalan ?? [];
  const figyelmeztetesek = adat.javaslat?.figyelmeztetesek ?? [];
  const jovahagyva = adat.allapot === "jovahagyva";
  const jovahagyhato = ["ellenorzendo", "pontositas"].includes(adat.allapot) && adat.cel_tipus && adat.cel_tipus !== "kimeno";

  return (
    <div className="mr-auto w-full max-w-[520px] rounded-[var(--radius)] border border-border bg-surface-1 p-3 text-[13px]">
      <p className="mb-1.5 flex items-center gap-2 text-[11px] font-medium text-text-muted">
        SZÁMLA-PISZKOZAT #{adat.id}
        <span
          className={`rounded px-1.5 py-0.5 text-[10.5px] ${
            jovahagyva ? "bg-bg-success text-text-success" : adat.allapot === "duplikatum" ? "bg-surface-3 text-text-secondary" : "bg-bg-warning text-text-warning"
          }`}
        >
          {jovahagyva
            ? "Rögzítve"
            : adat.allapot === "duplikatum"
              ? "Duplikátum"
              : adat.allapot === "hiba"
                ? "Feldolgozási hiba"
                : adat.allapot === "pontositas"
                  ? "Pontosítás szükséges"
                  : "Ellenőrizendő"}
        </span>
      </p>
      <p className="text-text-primary">
        <b>{adat.kibocsato_nev ?? "Ismeretlen kibocsátó"}</b>
        {adat.szamlaszam ? ` · ${adat.szamlaszam}` : ""}
        {adat.dokumentum_tipus && adat.dokumentum_tipus !== "szamla" ? ` · ${adat.dokumentum_tipus.toUpperCase()}` : ""}
      </p>
      <p className="text-text-secondary">
        {adat.netto != null ? `${formatSzam(adat.netto)} ${adat.penznem} nettó` : "összeg nélkül"}
        {adat.brutto != null ? ` · ${formatSzam(adat.brutto)} ${adat.penznem} bruttó` : ""}
        {adat.fizetesi_hatarido ? ` · határidő: ${adat.fizetesi_hatarido}` : ""}
      </p>
      <p className="mt-1 text-text-secondary">
        Cél: <b className="text-text-primary">{adat.cel_cimke ?? (adat.cel_tipus ? CEL_CIMKEK[adat.cel_tipus] : "még nincs kiválasztva")}</b>
        {adat.cel_tipus && ["kiadas_uj", "mukodesi", "auto"].includes(adat.cel_tipus) ? " (ÚJ tétel készül, nem kifizetettként)" : adat.cel_tipus ? " (meglévő tételhez csatolás)" : ""}
      </p>
      {adat.javaslat_indoklas && <p className="mt-1 text-[12px] text-text-muted">{adat.javaslat_indoklas}</p>}
      {(adat.javaslat?.alternativak?.length ?? 0) > 0 && !jovahagyva && (
        <p className="mt-1 text-[12px] text-text-muted">
          További lehetőségek: {adat.javaslat!.alternativak.slice(0, 3).map((a) => a.cimke).join(" · ")} — írd meg,
          melyik legyen, vagy nyisd meg az ellenőrzőt.
        </p>
      )}
      {bizonytalan.length > 0 && (
        <p className="mt-1 text-[12px] text-text-warning">Bizonytalan mezők: {bizonytalan.join(", ")} - ellenőrizd.</p>
      )}
      {figyelmeztetesek.map((f, i) => (
        <p key={i} className="mt-1 text-[12px] text-text-warning">
          ⚠ {f}
        </p>
      ))}
      {adat.duplikatum_megjegyzes && <p className="mt-1 text-[12px] text-text-warning">{adat.duplikatum_megjegyzes}</p>}
      {adat.hiba_uzenet && <p className="mt-1 text-[12px] text-text-danger">{adat.hiba_uzenet}</p>}

      <div className="mt-2 flex flex-wrap gap-1.5">
        {jovahagyhato && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onJovahagyas(adat.id)}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-2.5 py-1 text-[12.5px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Jóváhagyás
          </button>
        )}
        <Link
          href={`/penzugyek/bejovo-szamlak?id=${adat.id}`}
          className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3"
        >
          Megnyitás az ellenőrzőben
        </Link>
      </div>
    </div>
  );
}
