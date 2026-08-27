"use client";

import { useMemo, useRef, useState } from "react";
import { Paperclip, X } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import { useLiveTopic } from "@/lib/live";
import type { DeliverableComment, DocumentAttachment } from "@/lib/api";

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
  canUpload,
}: {
  deliverableId: number;
  initialComments: DeliverableComment[];
  mentionableEmployees: { id: number; full_name: string }[];
  /** Csatolhat-e fájlt egy hozzászóláshoz - a Fájlok/csatolmányok végpont
   * ugyanazt a jogosultságot kéri, mint az Utómunka oldal szerkesztése (lásd
   * backend services/attachments.ENTITAS_OLDALAK "deliverableComment"). */
  canUpload: boolean;
}) {
  const [comments, setComments] = useState(initialComments);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploadingCommentId, setUploadingCommentId] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const confirm = useConfirm();

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

  /** Fájlokat tölt fel EGY hozzászóláshoz, egyenként (mint DokumentumFeltoltes-
   * nél): egy hibás fájl csak magát bukja, a többi felmegy. A sikeresen
   * felkerült csatolmányokat adja vissza, hogy a hívó a helyi állapotba
   * tehesse - nincs router.refresh(), mert ez a komponens saját state-ben
   * tartja a hozzászólásokat, azt egy szerver-oldali frissítés nem érné el. */
  async function toltsFel(commentId: number, files: File[]): Promise<DocumentAttachment[]> {
    const feltoltottek: DocumentAttachment[] = [];
    const hibak: string[] = [];
    for (const file of files) {
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await authFetch(`/api/v1/csatolmanyok/deliverableComment/${commentId}?kategoria=egyeb`, {
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
          prev.map((c) => (c.id === commentId ? { ...c, attachments: [...c.attachments, ...csatolt] } : c)),
        );
      }
    } finally {
      setUploadingCommentId(null);
    }
  }

  async function csatolmanyTorlese(commentId: number, attachment: DocumentAttachment) {
    if (!(await confirm(`Törlöd a(z) "${attachment.filename}" fájlt?`))) return;
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${attachment.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      setComments((prev) =>
        prev.map((c) =>
          c.id === commentId ? { ...c, attachments: c.attachments.filter((a) => a.id !== attachment.id) } : c,
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
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/comments`, {
        method: "POST",
        body: JSON.stringify({ body: trimmed }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      let created: DeliverableComment = await res.json();
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
            {(c.attachments.length > 0 || canUpload) && (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                {c.attachments.map((a) => (
                  <span key={a.id} className="flex items-center gap-1 text-[12px]">
                    <Paperclip size={12} className="shrink-0 text-text-muted" />
                    <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                      {a.filename}
                    </a>
                    {canUpload && (
                      <button
                        type="button"
                        onClick={() => csatolmanyTorlese(c.id, a)}
                        title="Csatolmány törlése"
                        className="text-text-muted hover:text-text-danger"
                      >
                        <X size={12} />
                      </button>
                    )}
                  </span>
                ))}
                {canUpload && (
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
                )}
              </div>
            )}
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
        {canUpload && (
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
        )}
      </div>
    </div>
  );
}
