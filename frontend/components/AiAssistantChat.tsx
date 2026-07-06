"use client";

import { useRef, useState } from "react";
import { authFetch } from "@/lib/authFetch";

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
};

/** Egyszerű kérdés/válasz chat UI az AI Assistant-hoz (/api/v1/ai-assistant/ask) -
 * a backend tool-calling-gal, a bejelentkezett felhasználó saját
 * oldal/mező-jogosultsága szerint szűrve dolgozza fel a kérdést, ezért itt a
 * frontend oldalon nincs is szükség külön jogosultság-kezelésre. */
export function AiAssistantChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function send() {
    const trimmed = question.trim();
    if (!trimmed || busy) return;
    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setQuestion("");
    setBusy(true);
    try {
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
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", text: `Hálózati hiba: ${err}` }]);
    } finally {
      setBusy(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex-1 space-y-3 overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-[13px] text-text-muted">
            Kérdezz bármit a projektekről, ügyfelekről, csapatról, felszerelésről, feladatokról vagy
            pénzügyekről - csak azokból az adatokból válaszol, amikhez neked hozzáférésed van.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded-[var(--radius)] p-3 text-[13px] ${
              m.role === "user"
                ? "ml-auto max-w-[80%] bg-surface-3 text-text-primary"
                : "mr-auto max-w-[80%] bg-surface-1 text-text-primary"
            }`}
          >
            <p className="mb-1 text-[11px] font-medium text-text-muted">
              {m.role === "user" ? "Te" : "AI Assistant"}
            </p>
            <p className="whitespace-pre-line">{m.text}</p>
          </div>
        ))}
        {busy && <p className="text-[13px] text-text-muted">AI Assistant gondolkodik…</p>}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2">
        <textarea
          rows={2}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Kérdezz valamit… (Enter a küldéshez, Shift+Enter új sorhoz)"
          className="flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
        />
        <button
          type="button"
          disabled={busy || !question.trim()}
          onClick={send}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          Küldés
        </button>
      </div>
    </div>
  );
}
