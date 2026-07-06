"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/Card";
import { authFetch } from "@/lib/authFetch";
import type { PortalDetailData, PortalFolderItem, PortalImageItem, PortalVideoItem } from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "draft", label: "Vázlat" },
  { value: "live", label: "Élő" },
  { value: "archived", label: "Archivált" },
];
const BRAND_OPTIONS = [
  { value: "hype", label: "HYPE" },
  { value: "contentbee", label: "ContentBee" },
];
const PAYMENT_MODE_OPTIONS = [
  { value: "contact", label: "Kapcsolatfelvétel (nincs fizetés)" },
  { value: "paid", label: "Fizetős hosszabbítás" },
];

async function patchPortal(portalId: number, data: Record<string, unknown>) {
  const res = await authFetch(`/api/v1/portal-admin/${portalId}`, { method: "PATCH", body: JSON.stringify(data) });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Sikertelen (${res.status})`);
  }
  return res.json();
}

export function MediaPortalDetail({ portal: initial }: { portal: PortalDetailData }) {
  const router = useRouter();
  const [portal, setPortal] = useState(initial);
  const [saving, setSaving] = useState(false);

  async function save(data: Record<string, unknown>) {
    setSaving(true);
    try {
      const updated = await patchPortal(portal.id, data);
      setPortal((prev) => ({ ...prev, ...updated }));
    } catch (err) {
      alert(`Sikertelen mentés: ${err}`);
    } finally {
      setSaving(false);
    }
  }

  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const publicUrl = `${origin}/p/${portal.slug}`;

  return (
    <div className="space-y-4">
      <Card title={`Portál: ${portal.title}`}>
        <div className="mb-4 flex flex-wrap items-center gap-3 text-[13px]">
          <a href={publicUrl} target="_blank" rel="noreferrer" className="text-text-accent hover:underline">
            {publicUrl}
          </a>
          {saving && <span className="text-text-muted">Mentés…</span>}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Állapot">
            <select
              value={portal.status}
              onChange={(e) => save({ status: e.target.value })}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Márka">
            <select
              value={portal.brand}
              onChange={(e) => save({ brand: e.target.value })}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
            >
              {BRAND_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Fizetési mód">
            <select
              value={portal.payment_mode}
              onChange={(e) => save({ payment_mode: e.target.value })}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
            >
              {PAYMENT_MODE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Lejárat">
            <input
              type="date"
              defaultValue={portal.expires_at ?? ""}
              onBlur={(e) => save({ expires_at: e.target.value || null })}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
            />
          </Field>
          <Field label="Cím felülírás (üresen a projekt neve)">
            <input
              type="text"
              defaultValue={portal.title_override ?? ""}
              placeholder={portal.title}
              onBlur={(e) => save({ title_override: e.target.value || null })}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
            />
          </Field>
          <Field label="Ügyfélnév felülírás (üresen a projekt ügyfele)">
            <input
              type="text"
              defaultValue={portal.client_name_override ?? ""}
              placeholder={portal.client_name}
              onBlur={(e) => save({ client_name_override: e.target.value || null })}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
            />
          </Field>
          <Field label="Slug">
            <input
              type="text"
              defaultValue={portal.slug}
              onBlur={(e) => save({ slug: e.target.value })}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
            />
          </Field>
          <Field label={portal.has_password ? "Jelszó (kitöltve = csere, üresen hagyva = törlés gomb kell)" : "Jelszó beállítása"}>
            <PasswordField hasPassword={portal.has_password} onSave={(pw) => save({ password: pw })} />
          </Field>
        </div>

        <div className="mt-4">
          <Field label="Leírás (az ügyfél-portál oldalán jelenik meg)">
            <textarea
              rows={3}
              defaultValue={portal.description}
              onBlur={(e) => save({ description: e.target.value })}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
            />
          </Field>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <ShareLinkButton portalId={portal.id} onLink={(url) => alert(`Share link: ${url}`)} />
          <CoverUploadButton portal={portal} onChange={(url) => setPortal((p) => ({ ...p, cover_image_url: url }))} />
        </div>
      </Card>

      <Card title="Mappák">
        <FoldersSection portalId={portal.id} folders={portal.folders} onChange={(folders) => setPortal((p) => ({ ...p, folders }))} />
      </Card>

      <Card title={`Videók (${portal.videos.length})`}>
        <VideosSection
          portalId={portal.id}
          videos={portal.videos}
          folders={portal.folders}
          onChange={(videos) => setPortal((p) => ({ ...p, videos }))}
        />
      </Card>

      <Card title={`Képek (${portal.images.length})`}>
        <ImagesSection
          portalId={portal.id}
          images={portal.images}
          folders={portal.folders}
          onChange={(images) => setPortal((p) => ({ ...p, images }))}
        />
      </Card>

      <button
        type="button"
        onClick={() => router.refresh()}
        className="text-[12px] text-text-muted hover:text-text-secondary"
      >
        Frissítés (pl. videó feldolgozás állapotához)
      </button>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12px] text-text-muted">{label}</span>
      {children}
    </label>
  );
}

function PasswordField({ hasPassword, onSave }: { hasPassword: boolean; onSave: (pw: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={hasPassword ? "Új jelszó…" : "Jelszó…"}
        className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
      />
      <button
        type="button"
        onClick={() => {
          onSave(value);
          setValue("");
        }}
        disabled={!value}
        className="shrink-0 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        Beállít
      </button>
      {hasPassword && (
        <button
          type="button"
          onClick={() => onSave("")}
          className="shrink-0 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-danger hover:bg-surface-3"
        >
          Törlés
        </button>
      )}
    </div>
  );
}

function ShareLinkButton({ portalId, onLink }: { portalId: number; onLink: (url: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function regen() {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/portal-admin/${portalId}/share`, { method: "POST" });
      if (!res.ok) throw new Error(String(res.status));
      const data: { url: string } = await res.json();
      onLink(data.url);
    } catch (err) {
      alert(`Sikertelen: ${err}`);
    } finally {
      setBusy(false);
    }
  }
  return (
    <button
      type="button"
      onClick={regen}
      disabled={busy}
      className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
    >
      {busy ? "…" : "Megosztási link generálása"}
    </button>
  );
}

function CoverUploadButton({
  portal,
  onChange,
}: {
  portal: PortalDetailData;
  onChange: (url: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(file: File) {
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await authFetch(`/api/v1/portal-admin/${portal.id}/cover`, { method: "POST", body: form });
      if (!res.ok) throw new Error(String(res.status));
      const data: { cover_image_url: string } = await res.json();
      onChange(data.cover_image_url);
    } catch (err) {
      alert(`Sikertelen borítókép feltöltés: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {portal.cover_image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={portal.cover_image_url} alt="Borítókép" className="h-10 w-16 rounded object-cover" />
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        {busy ? "Feltöltés…" : "Borítókép feltöltése"}
      </button>
    </div>
  );
}

function FoldersSection({
  portalId,
  folders,
  onChange,
}: {
  portalId: number;
  folders: PortalFolderItem[];
  onChange: (folders: PortalFolderItem[]) => void;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/portal-admin/${portalId}/folders`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const created: PortalFolderItem = await res.json();
      onChange([...folders, created]);
      setName("");
    } catch (err) {
      alert(`Sikertelen: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function rename(folder: PortalFolderItem, newName: string) {
    const res = await authFetch(`/api/v1/portal-admin/folders/${folder.id}`, {
      method: "PATCH",
      body: JSON.stringify({ name: newName }),
    });
    if (res.ok) onChange(folders.map((f) => (f.id === folder.id ? { ...f, name: newName } : f)));
  }

  async function remove(folder: PortalFolderItem) {
    if (!confirm(`Biztosan törlöd a "${folder.name}" mappát? A benne lévő videók/képek is törlődnek.`)) return;
    const res = await authFetch(`/api/v1/portal-admin/folders/${folder.id}`, { method: "DELETE" });
    if (res.ok) onChange(folders.filter((f) => f.id !== folder.id));
  }

  return (
    <div>
      {folders.length === 0 && <p className="mb-3 text-[13px] text-text-muted">Nincs mappa - a videók/képek egy közös listában jelennek meg.</p>}
      <ul className="mb-3 space-y-1.5">
        {folders.map((f) => (
          <li key={f.id} className="flex items-center gap-2">
            <input
              defaultValue={f.name}
              onBlur={(e) => e.target.value !== f.name && rename(f, e.target.value)}
              className="flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary"
            />
            <button type="button" onClick={() => remove(f)} className="text-[12px] text-text-danger hover:underline">
              Törlés
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Új mappa neve…"
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
        />
        <button
          type="button"
          onClick={create}
          disabled={busy || !name.trim()}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          + Mappa
        </button>
      </div>
    </div>
  );
}

const VIDEO_STATUS_LABEL: Record<string, string> = {
  uploading: "Feltöltés…",
  processing: "Feldolgozás…",
  ready: "Kész",
  failed: "Hiba",
};

function VideosSection({
  portalId,
  videos,
  folders,
  onChange,
}: {
  portalId: number;
  videos: PortalVideoItem[];
  folders: PortalFolderItem[];
  onChange: (videos: PortalVideoItem[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);
  const [replacingId, setReplacingId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);

  async function upload(file: File) {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await authFetch(`/api/v1/portal-admin/${portalId}/videos`, { method: "POST", body: form });
      if (!res.ok) throw new Error(String(res.status));
      const created: PortalVideoItem = await res.json();
      onChange([...videos, created]);
    } catch (err) {
      alert(`Sikertelen videó feltöltés: ${err}`);
    } finally {
      setUploading(false);
    }
  }

  async function replace(video: PortalVideoItem, file: File) {
    const form = new FormData();
    form.append("file", file);
    const res = await authFetch(`/api/v1/portal-admin/videos/${video.id}/replace`, { method: "POST", body: form });
    if (res.ok) {
      const updated: PortalVideoItem = await res.json();
      onChange(videos.map((v) => (v.id === video.id ? updated : v)));
    }
  }

  async function rename(video: PortalVideoItem, title: string) {
    const res = await authFetch(`/api/v1/portal-admin/videos/${video.id}`, { method: "PATCH", body: JSON.stringify({ title }) });
    if (res.ok) onChange(videos.map((v) => (v.id === video.id ? { ...v, title } : v)));
  }

  async function setFolder(video: PortalVideoItem, folderId: number | null) {
    const res = await authFetch(`/api/v1/portal-admin/videos/${video.id}`, {
      method: "PATCH",
      body: JSON.stringify({ folder_id: folderId }),
    });
    if (res.ok) onChange(videos.map((v) => (v.id === video.id ? { ...v, folder_id: folderId } : v)));
  }

  async function remove(video: PortalVideoItem) {
    if (!confirm(`Biztosan törlöd a(z) "${video.title}" videót?`)) return;
    const res = await authFetch(`/api/v1/portal-admin/videos/${video.id}`, { method: "DELETE" });
    if (res.ok) onChange(videos.filter((v) => v.id !== video.id));
  }

  async function move(video: PortalVideoItem, direction: -1 | 1) {
    const sorted = [...videos].sort((a, b) => a.sort_order - b.sort_order);
    const idx = sorted.findIndex((v) => v.id === video.id);
    const swapIdx = idx + direction;
    if (swapIdx < 0 || swapIdx >= sorted.length) return;
    [sorted[idx], sorted[swapIdx]] = [sorted[swapIdx], sorted[idx]];
    const orderedIds = sorted.map((v) => v.id);
    const res = await authFetch(`/api/v1/portal-admin/${portalId}/videos/reorder`, {
      method: "POST",
      body: JSON.stringify({ ordered_ids: orderedIds }),
    });
    if (res.ok) {
      onChange(sorted.map((v, i) => ({ ...v, sort_order: i })));
    }
  }

  async function downloadUrl(video: PortalVideoItem) {
    const res = await authFetch(`/api/v1/portal-admin/videos/${video.id}/download-url`);
    if (!res.ok) return;
    const data: { url: string } = await res.json();
    window.open(data.url, "_blank");
  }

  const sorted = [...videos].sort((a, b) => a.sort_order - b.sort_order);

  return (
    <div>
      <ul className="mb-3 space-y-2">
        {sorted.map((v, i) => (
          <li key={v.id} className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] bg-surface-1 p-2">
            {v.thumbnail_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={v.thumbnail_url} alt={v.title} className="h-12 w-20 shrink-0 rounded object-cover" />
            ) : (
              <div className="h-12 w-20 shrink-0 rounded bg-surface-3" />
            )}
            <input
              defaultValue={v.title}
              onBlur={(e) => e.target.value !== v.title && rename(v, e.target.value)}
              className="min-w-[10rem] flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary"
            />
            <select
              value={v.folder_id ?? ""}
              onChange={(e) => setFolder(v, e.target.value ? Number(e.target.value) : null)}
              className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12px] text-text-primary"
            >
              <option value="">(nincs mappa)</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
            <span className="text-[12px] text-text-muted">{VIDEO_STATUS_LABEL[v.status] ?? v.status}</span>
            <div className="flex gap-1">
              <button type="button" onClick={() => move(v, -1)} disabled={i === 0} className="text-[12px] text-text-secondary hover:text-text-primary disabled:opacity-30">
                ↑
              </button>
              <button type="button" onClick={() => move(v, 1)} disabled={i === sorted.length - 1} className="text-[12px] text-text-secondary hover:text-text-primary disabled:opacity-30">
                ↓
              </button>
            </div>
            <button type="button" onClick={() => downloadUrl(v)} className="text-[12px] text-text-secondary hover:underline">
              Letöltés
            </button>
            <button
              type="button"
              onClick={() => {
                setReplacingId(v.id);
                replaceInputRef.current?.click();
              }}
              className="text-[12px] text-text-secondary hover:underline"
            >
              Csere
            </button>
            <button type="button" onClick={() => remove(v)} className="text-[12px] text-text-danger hover:underline">
              Törlés
            </button>
          </li>
        ))}
      </ul>
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload(file);
          e.target.value = "";
        }}
      />
      <input
        ref={replaceInputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          const video = videos.find((v) => v.id === replacingId);
          if (file && video) replace(video, file);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        {uploading ? "Feltöltés…" : "+ Videó feltöltése"}
      </button>
    </div>
  );
}

function ImagesSection({
  portalId,
  images,
  folders,
  onChange,
}: {
  portalId: number;
  images: PortalImageItem[];
  folders: PortalFolderItem[];
  onChange: (images: PortalImageItem[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  async function upload(file: File) {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await authFetch(`/api/v1/portal-admin/${portalId}/images`, { method: "POST", body: form });
      if (!res.ok) throw new Error(String(res.status));
      const created: PortalImageItem = await res.json();
      onChange([...images, created]);
    } catch (err) {
      alert(`Sikertelen kép feltöltés: ${err}`);
    } finally {
      setUploading(false);
    }
  }

  async function setFolder(image: PortalImageItem, folderId: number | null) {
    const res = await authFetch(`/api/v1/portal-admin/images/${image.id}`, {
      method: "PATCH",
      body: JSON.stringify({ folder_id: folderId, set_folder: true }),
    });
    if (res.ok) onChange(images.map((i) => (i.id === image.id ? { ...i, folder_id: folderId } : i)));
  }

  async function remove(image: PortalImageItem) {
    if (!confirm(`Biztosan törlöd a(z) "${image.title}" képet?`)) return;
    const res = await authFetch(`/api/v1/portal-admin/images/${image.id}`, { method: "DELETE" });
    if (res.ok) onChange(images.filter((i) => i.id !== image.id));
  }

  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-3">
        {images.map((img) => (
          <li key={img.id} className="w-40 rounded-[var(--radius)] bg-surface-1 p-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img.thumbnail_url || img.url} alt={img.title} className="mb-2 h-24 w-full rounded object-cover" />
            <select
              value={img.folder_id ?? ""}
              onChange={(e) => setFolder(img, e.target.value ? Number(e.target.value) : null)}
              className="mb-2 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-1.5 py-1 text-[11px] text-text-primary"
            >
              <option value="">(nincs mappa)</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
            <button type="button" onClick={() => remove(img)} className="text-[12px] text-text-danger hover:underline">
              Törlés
            </button>
          </li>
        ))}
      </ul>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload(file);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        {uploading ? "Feltöltés…" : "+ Kép feltöltése"}
      </button>
    </div>
  );
}
