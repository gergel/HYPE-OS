"use client";

import { useMemo, useRef, useState } from "react";
import { Paperclip, X } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { useLiveTopic } from "@/lib/live";
import type { DocumentAttachment, FloraKomment } from "@/lib/api";

const MENTION_PATTERN = /@[^\s@]*$/;

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("hu-HU", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Egy hozzászólás szövegében a "@Név" részeket kiemeli - egyszerű, tag-szerű
 * megjelenítés (az értesítést a szerver küldi, lásd backend routes/flora.py). */
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

/** Chat-szerű hozzászólás-lista egy FLÓRA feladat oldalán - ugyanaz a minta,
 * mint az Utómunkánál és a Project Code-nál (lásd
 * components/projektkod/CommentsSection.tsx). A Notion-import a kártya
 * Notion-beli kommentjeit is ide hozza, tehát a régi beszélgetések sem
 * vesznek el. Fájl is csatolható a hozzászólásokhoz (a felhasználó kérése) -
 * aki az oldalt látja, az tölthet, mint az Utómunkánál (lásd backend
 * routes/attachments.KOMMENT_ENTITASOK "floraComment"). */
export function FloraCommentsSection({
  floraId,
  initialComments,
  mentionableEmployees,
}: {
  floraId: number;
  initialComments: FloraKomment[];
  mentionableEmployees: { id: number; full_name: string }[];
}) {
  const [comments, setComments] = useState(initialComments);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploadingCommentId, setUploadingCommentId] = useState<number | null>(null);
  // Csatolmány-törlés kétfázisúan (nem böngésző-confirm, mert az némítható).
  const [torlendoCsatolmany, setTorlendoCsatolmany] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Ha valaki más ír ide, az oldal újratöltése nélkül is megjelenjen (lásd
  // backend routes/realtime.py "floraComments" témája).
  useLiveTopic(`floraComments:${floraId}`, () => {
    authFetch(`/api/v1/flora/${floraId}/comments`)
      .then((res) => (res.ok ? res.json() : null))
      .then((fresh: FloraKomment[] | null) => fresh && setComments(fresh))
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

  /** Fájlokat tölt fel EGY hozzászóláshoz, egyenként (mint az Utómunkánál):
   * egy hibás fájl csak magát bukja, a többi felmegy. */
  async function toltsFel(commentId: number, files: File[]): Promise<DocumentAttachment[]> {
    const feltoltottek: DocumentAttachment[] = [];
    const hibak: string[] = [];
    for (const file of files) {
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await authFetch(`/api/v1/csatolmanyok/floraComment/${commentId}?kategoria=egyeb`, {
          method: "POST",
          body: fd,
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          hibak.push(`${file.name}: ${detail?.detail ?? res.status}`);
        } else {
          feltoltottek.push(await res.json());
        }
      } catch (err) {
        hibak.push(`${file.name}: ${err}`);
      }
    }
    if (hibak.length > 0) alert(`Sikertelen feltöltés:\n${hibak.join("\n")}`);
    return feltoltottek;
  }

  async function csatolmanyFeltoltese(commentId: number, fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setUploadingCommentId(commentId);
    try {
      const csatolt = await toltsFel(commentId, Array.from(fileList));
      if (csatolt.length > 0) {
        setComments((prev) =>
          prev.map((c) => (c.id === commentId ? { ...c, attachments: [...(c.attachments ?? []), ...csatolt] } : c)),
        );
      }
    } finally {
      setUploadingCommentId(null);
    }
  }

  async function csatolmanyTorlese(commentId: number, attachment: DocumentAttachment) {
    if (torlendoCsatolmany !== attachment.id) {
      setTorlendoCsatolmany(attachment.id);
      setTimeout(() => setTorlendoCsatolmany((elozo) => (elozo === attachment.id ? null : elozo)), 5000);
      return;
    }
    setTorlendoCsatolmany(null);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${attachment.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      setComments((prev) =>
        prev.map((c) =>
          c.id === commentId ? { ...c, attachments: (c.attachments ?? []).filter((a) => a.id !== attachment.id) } : c,
        ),
      );
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    }
  }

  async function send() {
    const trimmed = body.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/flora/${floraId}/comments`, {
        method: "POST",
        body: JSON.stringify({ body: trimmed }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      let created: FloraKomment = await res.json();
      // A küldés előtt kiválasztott fájlok az új hozzászóláshoz kerülnek.
      if (pendingFiles.length > 0) {
        const csatolt = await toltsFel(created.id, pendingFiles);
        created = { ...created, attachments: csatolt };
      }
      setComments((prev) => [...prev, created]);
      setBody("");
      setPendingFiles([]);
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
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
              {(c.attachments ?? []).map((a) => (
                <span key={a.id} className="flex items-center gap-1 text-[12px]">
                  <Paperclip size={12} className="shrink-0 text-text-muted" />
                  <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                    {a.filename}
                  </a>
                  <button
                    type="button"
                    onClick={() => void csatolmanyTorlese(c.id, a)}
                    title={torlendoCsatolmany === a.id ? "Még egy kattintás a törléshez" : "Csatolmány törlése (két kattintás)"}
                    className={torlendoCsatolmany === a.id ? "text-text-danger" : "text-text-muted hover:text-text-danger"}
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
              <label className="cursor-pointer text-[12px] text-text-muted hover:text-text-secondary">
                {uploadingCommentId === c.id ? "Feltöltés…" : "+ Fájl"}
                <input
                  type="file"
                  multiple
                  className="hidden"
                  disabled={uploadingCommentId === c.id}
                  onChange={(e) => {
                    void csatolmanyFeltoltese(c.id, e.target.files);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
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
      {pendingFiles.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-2">
          {pendingFiles.map((f, i) => (
            <span
              key={`${f.name}-${i}`}
              className="flex items-center gap-1 rounded-[var(--radius)] bg-surface-2 px-2 py-0.5 text-[12px] text-text-secondary"
            >
              <Paperclip size={11} className="shrink-0 text-text-muted" />
              {f.name}
              <button
                type="button"
                onClick={() => setPendingFiles((prev) => prev.filter((_, j) => j !== i))}
                className="text-text-muted hover:text-text-danger"
              >
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          disabled={busy || !body.trim()}
          onClick={send}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          Küldés
        </button>
        <label className="cursor-pointer text-[13px] text-text-muted hover:text-text-secondary">
          + Fájl csatolása
          <input
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              setPendingFiles((prev) => [...prev, ...Array.from(e.target.files ?? [])]);
              e.target.value = "";
            }}
          />
        </label>
      </div>
    </div>
  );
}
