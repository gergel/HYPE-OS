"use client";

import { useMemo, useRef, useState } from "react";
import { authFetch } from "@/lib/authFetch";
import { useLiveTopic } from "@/lib/live";
import type { DeliverableComment } from "@/lib/api";

const MENTION_PATTERN = /@[^\s@]*$/;

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("hu-HU", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Egy hozzászólás szövegében a "@Név" részeket kiemeli - egyszerű, tag-szerű
 * megjelenítés (nem küld értesítést, csak vizuálisan jelöli a taggelést). */
function BodyWithMentions({ body }: { body: string }) {
  const parts = body.split(/(@[^\s@]+(?:\s[^\s@]+)?)/g);
  return (
    <p className="whitespace-pre-line text-[13px] text-text-primary">
      {parts.map((part, i) =>
        part.startsWith("@") ? (
          <span key={i} className="text-text-accent">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </p>
  );
}

/** Chat-szerű hozzászólás-lista egy Utómunka oldal alján - a résztvevők
 * névvel beszélgetnek, és "@" beírásával egymást is meg tudják taggelni
 * (a csatolt Notion Comments minta alapján, egyszerűsített - lapos lista,
 * nem szálakba rendezett válaszok). */
export function CommentsSection({
  deliverableId,
  initialComments,
  mentionableEmployees,
}: {
  deliverableId: number;
  initialComments: DeliverableComment[];
  mentionableEmployees: { id: number; full_name: string }[];
}) {
  const [comments, setComments] = useState(initialComments);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Ha valaki MÁS ír ide, az oldal újratöltése nélkül is megjelenjen: a
  // háttérfigyelő szól, ha ennek az anyagnak a hozzászólásai változtak, és
  // csak akkor kérjük le újra a listát. A félig megírt saját szöveg (body)
  // érintetlen marad, mert az külön állapot.
  useLiveTopic(`comments:${deliverableId}`, () => {
    authFetch(`/api/v1/deliverables/${deliverableId}/comments`)
      .then((res) => (res.ok ? res.json() : null))
      .then((fresh: DeliverableComment[] | null) => fresh && setComments(fresh))
      .catch(() => {});
  });

  const mentionMatches = useMemo(() => {
    if (mentionQuery === null) return [];
    const q = mentionQuery.toLowerCase();
    return mentionableEmployees.filter((e) => e.full_name.toLowerCase().includes(q)).slice(0, 6);
  }, [mentionQuery, mentionableEmployees]);

  function handleChange(value: string) {
    setBody(value);
    const cursor = textareaRef.current?.selectionStart ?? value.length;
    const uptoCursor = value.slice(0, cursor);
    const match = uptoCursor.match(MENTION_PATTERN);
    setMentionQuery(match ? match[0].slice(1) : null);
  }

  function insertMention(name: string) {
    const cursor = textareaRef.current?.selectionStart ?? body.length;
    const uptoCursor = body.slice(0, cursor);
    const replaced = uptoCursor.replace(MENTION_PATTERN, `@${name} `);
    const next = replaced + body.slice(cursor);
    setBody(next);
    setMentionQuery(null);
    textareaRef.current?.focus();
  }

  async function send() {
    const trimmed = body.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/comments`, {
        method: "POST",
        body: JSON.stringify({ body: trimmed }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const created: DeliverableComment = await res.json();
      setComments((prev) => [...prev, created]);
      setBody("");
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-4 space-y-3">
        {comments.length === 0 && <p className="text-[13px] text-text-muted">Még nincs hozzászólás.</p>}
        {comments.map((c) => (
          <div key={c.id} className="rounded-[var(--radius)] bg-surface-1 p-3">
            <div className="mb-1 flex items-center gap-2">
              <span className="text-[13px] font-medium text-text-primary">{c.employee_name}</span>
              <span className="text-[11px] text-text-muted">{formatTimestamp(c.created_at)}</span>
            </div>
            <BodyWithMentions body={c.body} />
          </div>
        ))}
      </div>

      <div className="relative">
        {mentionQuery !== null && mentionMatches.length > 0 && (
          <div className="absolute bottom-full left-0 z-10 mb-1 w-56 rounded-[var(--radius)] border border-border bg-surface-2 shadow-lg">
            {mentionMatches.map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => insertMention(e.full_name)}
                className="block w-full px-3 py-1.5 text-left text-[13px] text-text-primary hover:bg-surface-3"
              >
                {e.full_name}
              </button>
            ))}
          </div>
        )}
        <textarea
          ref={textareaRef}
          rows={2}
          value={body}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Írj hozzászólást… (@ a taggeléshez)"
          className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
        />
      </div>
      <button
        type="button"
        disabled={busy || !body.trim()}
        onClick={send}
        className="mt-2 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        Küldés
      </button>
    </div>
  );
}
