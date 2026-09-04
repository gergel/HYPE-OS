"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Folder as FolderIcon,
  FolderPlus,
  GripVertical,
  Link2,
  Pencil,
  Replace,
  Save,
  Trash2,
  Upload,
} from "lucide-react";
import {
  createFolder,
  updateFolder,
  deleteFolder,
  setVideoFolder,
  uploadImage,
  deleteImage,
  setImageFolder,
  renameVideo,
  uploadCover,
  deleteCover,
  getPortalDetail,
  updatePortal,
  uploadVideo,
  replaceVideo,
  deleteVideo,
  reorderVideos,
  deletePortal,
  createFeltoltoLink,
  createFolderShareLink,
  createVideoShareLink,
} from "@/lib/portalAdminApi";
import { Card } from "@/components/Card";
import { formatDuration, formatBytes } from "@/lib/portalUtils";
import { portalUrl } from "@/lib/portalUrl";
import type { PortalDetailData, PortalFolderItem, PortalImageItem, PortalVideoItem } from "@/lib/api";

const inputClass =
  "mt-1.5 w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3.5 py-2.5 text-[13px] text-text-primary outline-none focus:border-text-accent/40";
const labelClass = "text-[11px] font-medium uppercase tracking-wide text-text-muted";

/** A Média Portál admin projekt-részletnézete - a megosztott (lila akcentusú,
 * sötét) design rendszerre igazítva, a korábbi különálló "ink/bone/mist/
 * ember" vizuális nyelv helyett. A "title"/"client_name"/"project_date"
 * mezők itt a Portal saját title_override/client_name_override/
 * project_date_override mezőit szerkesztik (nem a mögöttes HYPE OS Project
 * rekordot magát, amit más modulok - diszpó, deliverable-ök stb. - is
 * használnak), de a felhasználó felé pontosan úgy néznek ki, mintha
 * közvetlenül szerkesztené a projekt címét/ügyfelét/dátumát. */
export default function MediaPortalDetail({ initial }: { initial: PortalDetailData }) {
  const router = useRouter();
  const [data, setData] = useState<PortalDetailData>(initial);
  const [videos, setVideos] = useState<PortalVideoItem[]>(initial.videos);
  const [images, setImages] = useState<PortalImageItem[]>(initial.images);
  const [folders, setFolders] = useState<PortalFolderItem[]>(initial.folders);
  const [currentFolder, setCurrentFolder] = useState<number | null>(null);
  const [selectedVideos, setSelectedVideos] = useState<Set<number>>(new Set());
  const [selectedImages, setSelectedImages] = useState<Set<number>>(new Set());
  const [form, setForm] = useState({
    title: initial.title,
    client_name: initial.client_name,
    project_date: initial.project_date,
    description: initial.description,
    cover_image_url: initial.cover_image_url,
    slug: initial.slug,
    password: "",
    brand: initial.brand,
    expires_at: (initial.expires_at || "").slice(0, 10),
    payment_mode: initial.payment_mode,
  });
  const [shareUrl, setShareUrl] = useState("");
  const [saved, setSaved] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploads, setUploads] = useState<{ name: string; percent: number }[]>([]);
  const [batch, setBatch] = useState<{ total: number; done: number; startedAt: number } | null>(null);
  const [videoBatch, setVideoBatch] = useState<{ total: number; done: number; startedAt: number } | null>(null);
  const replaceRef = useRef<HTMLInputElement>(null);
  const replaceId = useRef<number | null>(null);
  const dragId = useRef<number | null>(null);
  const cancelUpload = useRef(false);
  const abortController = useRef<AbortController | null>(null);

  const [prompt, setPrompt] = useState<{ title: string; value: string; onConfirm: (value: string) => void } | null>(
    null,
  );
  const [confirmDialog, setConfirmDialog] = useState<{ message: string; onConfirm: () => void } | null>(null);

  async function refresh() {
    const d = await getPortalDetail(initial.id);
    setData(d);
    setVideos(d.videos);
    setImages(d.images);
    setFolders(d.folders);
    setForm((f) => ({
      ...f,
      title: d.title,
      client_name: d.client_name,
      project_date: d.project_date || "",
      description: d.description,
      cover_image_url: d.cover_image_url,
      slug: d.slug,
      brand: d.brand,
      expires_at: (d.expires_at || "").slice(0, 10),
      payment_mode: d.payment_mode,
    }));
  }
  useEffect(() => {
    const t = setInterval(() => {
      getPortalDetail(initial.id).then((d) => {
        if (d.videos.some((v) => v.status === "processing")) setVideos(d.videos);
      });
    }, 5000);
    return () => clearInterval(t);
  }, [initial.id]);

  async function save() {
    const payload: Record<string, unknown> = {
      title_override: form.title,
      client_name_override: form.client_name,
      project_date_override: form.project_date,
      description: form.description,
      slug: form.slug,
      brand: form.brand,
      payment_mode: form.payment_mode,
    };
    if (form.password) payload.password = form.password;
    await updatePortal(initial.id, payload);
    setForm((f) => ({ ...f, password: "" }));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    refresh();
  }

  async function onChangeExpiry(value: string) {
    setForm((f) => ({ ...f, expires_at: value }));
    await updatePortal(initial.id, { expires_at: value || null });
    refresh();
  }

  function daysLeft(): number | null {
    if (!form.expires_at) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const exp = new Date(form.expires_at + "T00:00:00");
    exp.setHours(0, 0, 0, 0);
    return Math.round((exp.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  }

  async function clearPassword() {
    await updatePortal(initial.id, { password: "" });
    setForm((f) => ({ ...f, password: "" }));
    refresh();
  }

  function cancelUploadNow() {
    cancelUpload.current = true;
    abortController.current?.abort();
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (e.target) e.target.value = "";
    await handleFiles(files, currentFolder);
  }

  async function onDropFiles(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);

    const items = Array.from(e.dataTransfer.items || []);
    const entries = items
      .map((it) => (it.webkitGetAsEntry ? it.webkitGetAsEntry() : null))
      .filter(Boolean) as FileSystemEntry[];

    if (entries.length === 0) {
      const files = Array.from(e.dataTransfer.files || []);
      await handleFiles(files, currentFolder);
      return;
    }

    async function collectAllFiles(entry: FileSystemEntry): Promise<File[]> {
      if (entry.isFile) {
        const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
        return [file];
      }
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      const all: File[] = [];
      let batch: FileSystemEntry[] = [];
      do {
        batch = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
        for (const child of batch) {
          const childFiles = await collectAllFiles(child);
          all.push(...childFiles);
        }
      } while (batch.length > 0);
      return all;
    }

    const looseFiles: File[] = [];

    for (const entry of entries) {
      if (entry.isDirectory) {
        const folderName = entry.name;
        const existing = folders.find((f) => f.name === folderName);
        let folderId: number;
        if (existing) {
          folderId = existing.id;
        } else {
          const created = await createFolder(initial.id, folderName);
          folderId = created.id;
        }
        const allFiles = await collectAllFiles(entry);
        await handleFiles(allFiles, folderId);
      } else {
        const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
        looseFiles.push(file);
      }
    }

    if (looseFiles.length > 0) {
      await handleFiles(looseFiles, currentFolder);
    }

    refresh();
  }

  function isJunkFile(f: File): boolean {
    const n = f.name;
    if (n === ".DS_Store" || n === "Thumbs.db" || n === "desktop.ini") return true;
    if (n.startsWith("._")) return true;
    if (n.startsWith(".")) return true;
    return false;
  }

  async function handleFiles(rawFiles: File[], targetFolder: number | null) {
    const files = rawFiles.filter((f) => !isJunkFile(f));
    const imageFiles = files.filter((f) => f.type.startsWith("image/"));
    const otherFiles = files.filter((f) => !f.type.startsWith("image/"));

    if (imageFiles.length > 0) {
      const CONCURRENCY = 2;
      let done = 0;
      const startedAt = Date.now();
      cancelUpload.current = false;
      abortController.current = new AbortController();
      setBatch({ total: imageFiles.length, done: 0, startedAt });

      let buffer: PortalImageItem[] = [];
      const flushTimer = setInterval(() => {
        if (buffer.length > 0) {
          const toAdd = buffer;
          buffer = [];
          setImages((prev) => [...prev, ...toAdd]);
        }
      }, 1500);

      let cursor = 0;
      let lastError: string | null = null;
      let failCount = 0;
      async function worker() {
        while (cursor < imageFiles.length) {
          if (cancelUpload.current) return;
          const myIndex = cursor++;
          const file = imageFiles[myIndex];
          try {
            const created = await uploadImage(initial.id, file, targetFolder, abortController.current?.signal);
            if (created && created.id) buffer.push(created);
          } catch (err) {
            failCount++;
            lastError = err instanceof Error ? err.message : String(err);
          }
          done++;
          if (done % 5 === 0 || done === imageFiles.length) {
            setBatch((b) => (b ? { ...b, done } : b));
          }
        }
      }
      const workers = Array.from({ length: Math.min(CONCURRENCY, imageFiles.length) }, () => worker());
      await Promise.all(workers);

      clearInterval(flushTimer);
      if (buffer.length > 0) setImages((prev) => [...prev, ...buffer]);
      setBatch(null);
      abortController.current = null;
      if (failCount > 0 && !cancelUpload.current) {
        alert(`${failCount} kép feltöltése sikertelen volt: ${lastError}`);
      }
    }

    const videoStartedAt = Date.now();
    if (otherFiles.length > 0) {
      setVideoBatch({ total: otherFiles.length, done: 0, startedAt: videoStartedAt });
    }
    for (let vi = 0; vi < otherFiles.length; vi++) {
      const file = otherFiles[vi];
      const name = file.name.replace(/\.[^.]+$/, "");
      setVideoBatch({ total: otherFiles.length, done: vi, startedAt: videoStartedAt });
      setUploads((u) => [...u, { name, percent: 0 }]);
      try {
        const result = await uploadVideo(initial.id, file, name, (percent) => {
          setUploads((u) => u.map((item) => (item.name === name ? { ...item, percent } : item)));
        });
        if (targetFolder && result?.id) {
          await setVideoFolder(result.id, targetFolder);
        }
      } catch (err) {
        alert(`Sikertelen videó feltöltés: ${err}`);
      } finally {
        setTimeout(() => {
          setUploads((u) => u.filter((item) => item.name !== name));
        }, 1500);
      }
      refresh();
    }
    setVideoBatch(null);
  }

  async function onCoverUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const { cover_image_url } = await uploadCover(initial.id, file);
      setForm((f) => ({ ...f, cover_image_url }));
      refresh();
    } catch (err) {
      alert(`Borítókép feltöltése sikertelen: ${err instanceof Error ? err.message : err}`);
    }
  }

  async function onDeleteCover() {
    try {
      await deleteCover(initial.id);
      setForm((f) => ({ ...f, cover_image_url: "" }));
      refresh();
    } catch (err) {
      alert(`Borítókép törlése sikertelen: ${err instanceof Error ? err.message : err}`);
    }
  }

  async function onReplace(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file && replaceId.current !== null) {
      try {
        await replaceVideo(replaceId.current, file);
        refresh();
      } catch (err) {
        alert(`Videó cseréje sikertelen: ${err instanceof Error ? err.message : err}`);
      }
    }
  }

  async function onDrop(targetId: number) {
    const from = videos.findIndex((v) => v.id === dragId.current);
    const to = videos.findIndex((v) => v.id === targetId);
    if (from < 0 || to < 0 || from === to) return;
    const next = [...videos];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setVideos(next);
    await reorderVideos(initial.id, next.map((v) => v.id));
  }

  /** Link-generálás a backendtől + vágólapra másolás - a feltöltő és a
   * mappa/videó megosztó linkekhez (a felhasználó kérése). */
  async function linkMasol(keszit: () => Promise<{ url: string }>) {
    try {
      const { url } = await keszit();
      setShareUrl(url);
      await navigator.clipboard?.writeText(url).catch(() => {});
    } catch (e) {
      alert(String((e as Error)?.message ?? e));
    }
  }

  function makeShare() {
    // A PORTÁL domainje, nem az adminé, ahol ez a gomb megnyomódik - ez a link
    // megy ki az ügyfélnek (lásd lib/portalUrl.ts).
    const url = portalUrl(form.slug);
    setShareUrl(url);
    navigator.clipboard?.writeText(url).catch(() => {});
  }

  function onDeletePortal() {
    setConfirmDialog({
      message: "Biztosan törlöd ezt a Portált az összes videójával és képével együtt? Ez nem vonható vissza.",
      onConfirm: async () => {
        try {
          await deletePortal(initial.id);
          router.push("/media-portal");
        } catch (err) {
          alert(`Portál törlése sikertelen: ${err instanceof Error ? err.message : err}`);
        }
      },
    });
  }

  function onCreateFolder() {
    setPrompt({
      title: "Új mappa neve",
      value: "",
      onConfirm: async (name) => {
        if (!name.trim()) return;
        await createFolder(initial.id, name.trim());
        refresh();
      },
    });
  }

  function onRenameFolder(folderId: number) {
    const current = folders.find((f) => f.id === folderId);
    setPrompt({
      title: "Új mappa neve",
      value: current?.name || "",
      onConfirm: async (name) => {
        if (!name.trim()) return;
        await updateFolder(folderId, { name: name.trim() });
        refresh();
      },
    });
  }

  function onRenameVideo(videoId: number) {
    const current = videos.find((v) => v.id === videoId);
    setPrompt({
      title: "Videó átnevezése",
      value: current?.title || "",
      onConfirm: async (name) => {
        if (!name.trim()) return;
        await renameVideo(videoId, name.trim());
        refresh();
      },
    });
  }

  function onDeleteFolder(folderId: number) {
    setConfirmDialog({
      message: "Törlöd ezt a mappát a benne lévő összes videóval és képpel együtt? Ez nem vonható vissza.",
      onConfirm: async () => {
        try {
          await deleteFolder(folderId);
          if (currentFolder === folderId) setCurrentFolder(null);
          refresh();
        } catch (err) {
          alert(`Mappa törlése sikertelen: ${err instanceof Error ? err.message : err}`);
        }
      },
    });
  }

  function onDeleteVideo(videoId: number) {
    setConfirmDialog({
      message: "Törlöd ezt a videót? Ez nem vonható vissza.",
      onConfirm: async () => {
        try {
          await deleteVideo(videoId);
          refresh();
        } catch (err) {
          alert(`Videó törlése sikertelen: ${err instanceof Error ? err.message : err}`);
        }
      },
    });
  }

  function onDeleteImage(imageId: number) {
    setConfirmDialog({
      message: "Törlöd ezt a képet? Ez nem vonható vissza.",
      onConfirm: async () => {
        try {
          await deleteImage(imageId);
          refresh();
        } catch (err) {
          alert(`Kép törlése sikertelen: ${err instanceof Error ? err.message : err}`);
        }
      },
    });
  }

  async function onRemoveFromFolder(videoId: number) {
    await setVideoFolder(videoId, null);
    refresh();
  }

  async function onRemoveImageFromFolder(imageId: number) {
    await setImageFolder(imageId, null);
    refresh();
  }

  function toggleVideo(videoId: number) {
    setSelectedVideos((prev) => {
      const next = new Set(prev);
      if (next.has(videoId)) next.delete(videoId);
      else next.add(videoId);
      return next;
    });
  }

  function toggleImage(imageId: number) {
    setSelectedImages((prev) => {
      const next = new Set(prev);
      if (next.has(imageId)) next.delete(imageId);
      else next.add(imageId);
      return next;
    });
  }

  function clearSelection() {
    setSelectedVideos(new Set());
    setSelectedImages(new Set());
  }

  function onDeleteSelected() {
    const vIds = Array.from(selectedVideos);
    const iIds = Array.from(selectedImages);
    const total = vIds.length + iIds.length;
    if (total === 0) return;
    setConfirmDialog({
      message: `Törlöd a kijelölt ${total} elemet? Ez nem vonható vissza.`,
      onConfirm: async () => {
        let failCount = 0;
        let lastError: string | null = null;
        for (const vid of vIds) {
          try {
            await deleteVideo(vid);
          } catch (err) {
            failCount++;
            lastError = err instanceof Error ? err.message : String(err);
          }
        }
        for (const iid of iIds) {
          try {
            await deleteImage(iid);
          } catch (err) {
            failCount++;
            lastError = err instanceof Error ? err.message : String(err);
          }
        }
        clearSelection();
        refresh();
        if (failCount > 0) {
          alert(`${failCount} elem törlése sikertelen volt: ${lastError}`);
        }
      },
    });
  }

  // A "Portál megtekintése" is a valódi, ügyfél-oldali domainre visz - így az
  // admin pontosan azt látja előnézetben, amit a megrendelő kap.
  const portalHref = portalUrl(form.slug);

  const visibleVideos = videos.filter((v) => (currentFolder ? v.folder_id === currentFolder : !v.folder_id));
  const visibleImages = images.filter((i) => (currentFolder ? i.folder_id === currentFolder : !i.folder_id));
  const openFolder = folders.find((f) => f.id === currentFolder) || null;
  const selectedCount = selectedVideos.size + selectedImages.size;
  // A LEGÚJABB mappa mindig legfölül (a felhasználó kérése): az új mappa a
  // legnagyobb sort_order-t kapja (lásd backend portal_admin.create_folder),
  // ezért csökkenő sorrendben a frissen létrehozott kerül a lista tetejére.
  const mappakUjElol = [...folders].sort((a, b) => b.sort_order - a.sort_order || b.id - a.id);
  // ÖSSZES KIJELÖLÉSE (a felhasználó kérése): az épp látható (nyitott mappa
  // vagy a mappán kívüli) elemek egy kattintással kijelölhetők - ha már mind
  // ki van jelölve, ugyanaz a gomb megszünteti.
  const lathatoElemSzam = visibleVideos.length + visibleImages.length;
  const mindKijelolve =
    lathatoElemSzam > 0 &&
    visibleVideos.every((v) => selectedVideos.has(v.id)) &&
    visibleImages.every((i) => selectedImages.has(i.id));

  function osszesKijelolese() {
    if (mindKijelolve) {
      clearSelection();
      return;
    }
    setSelectedVideos(new Set(visibleVideos.map((v) => v.id)));
    setSelectedImages(new Set(visibleImages.map((i) => i.id)));
  }

  return (
    // min-w-0 + overflow-x-hidden: telefonon a hosszú, nem törhető tartalmak
    // (slug, fájlnevek) ne tolhassák a lapot a képernyőnél szélesebbre - ettől
    // csúszott el a fejléc is (a felhasználó hibajelzése).
    <div className="min-w-0 flex-1 space-y-4 overflow-x-hidden p-4 sm:p-6 lg:p-8">
      <Link href="/media-portal" className="inline-flex items-center gap-1.5 text-[13px] text-text-muted hover:text-text-primary">
        <ArrowLeft className="h-3.5 w-3.5" />
        Összes Portál
      </Link>

      <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        {/* Beállítások */}
        <Card title="Portál adatai" className="min-w-0">
          <div className="space-y-3">
            <Field label="Projekt címe" value={form.title} onChange={(v) => setForm((f) => ({ ...f, title: v }))} />
            <Field
              label="Ügyfél neve"
              value={form.client_name}
              onChange={(v) => setForm((f) => ({ ...f, client_name: v }))}
            />
            <Field
              label="Dátum (pl. 2026-06-17)"
              value={form.project_date}
              onChange={(v) => setForm((f) => ({ ...f, project_date: v }))}
            />
            <Field label="Portál azonosító (slug)" value={form.slug} onChange={(v) => setForm((f) => ({ ...f, slug: v }))} />

            <div>
              <div className="flex items-center justify-between">
                <label className={labelClass}>Borítókép</label>
                <div className="flex items-center gap-3">
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[12px] font-medium text-text-accent hover:opacity-90">
                    <Upload className="h-3.5 w-3.5" />
                    Feltöltés
                    <input type="file" accept="image/*" className="hidden" onChange={onCoverUpload} />
                  </label>
                  {form.cover_image_url && (
                    <button type="button" onClick={onDeleteCover} className="text-[12px] text-text-muted hover:text-text-danger hover:underline">
                      Eltávolítás
                    </button>
                  )}
                </div>
              </div>
              {form.cover_image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={form.cover_image_url} alt="Borító" className="mt-2 h-32 w-full rounded-[var(--radius)] border border-border object-cover" />
              )}
            </div>

            <div>
              <label className={labelClass}>Leírás</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={3}
                className={inputClass}
              />
            </div>

            <div>
              <label className={labelClass}>Márka</label>
              <div className="mt-1.5 flex gap-2">
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, brand: "hype" }))}
                  className={`flex-1 rounded-[var(--radius)] border px-4 py-2 text-[13px] transition-colors ${
                    form.brand === "hype"
                      ? "border-text-accent/50 bg-bg-accent text-text-primary"
                      : "border-border text-text-secondary hover:text-text-primary"
                  }`}
                >
                  HYPE
                </button>
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, brand: "contentbee" }))}
                  className={`flex-1 rounded-[var(--radius)] border px-4 py-2 text-[13px] transition-colors ${
                    form.brand === "contentbee"
                      ? "border-text-accent/50 bg-bg-accent text-text-primary"
                      : "border-border text-text-secondary hover:text-text-primary"
                  }`}
                >
                  ContentBee
                </button>
              </div>
            </div>
            <div>
              <label className={labelClass}>Elérhető eddig</label>
              <input
                type="date"
                value={form.expires_at}
                onChange={(e) => onChangeExpiry(e.target.value)}
                className={inputClass}
              />
              {form.expires_at && (
                <p className="mt-1.5 text-[12px] text-text-muted">
                  {(() => {
                    const d = daysLeft();
                    if (d === null) return null;
                    if (d < 0) return "Lejárt — a portál rejtve van az ügyfelek elől.";
                    if (d === 0) return "Ma jár le.";
                    return `${d} nap van hátra, amíg a portál elrejti a tartalmat.`;
                  })()}
                </p>
              )}
            </div>
            <div>
              <label className={labelClass}>Lejáratkor</label>
              <div className="mt-1.5 flex gap-2">
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, payment_mode: "contact" }))}
                  className={`flex-1 rounded-[var(--radius)] border px-4 py-2 text-[13px] transition-colors ${
                    form.payment_mode === "contact"
                      ? "border-text-accent/50 bg-bg-accent text-text-primary"
                      : "border-border text-text-secondary hover:text-text-primary"
                  }`}
                >
                  Kapcsolatfelvétel
                </button>
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, payment_mode: "paid" }))}
                  className={`flex-1 rounded-[var(--radius)] border px-4 py-2 text-[13px] transition-colors ${
                    form.payment_mode === "paid"
                      ? "border-text-accent/50 bg-bg-accent text-text-primary"
                      : "border-border text-text-secondary hover:text-text-primary"
                  }`}
                >
                  Fizetős hosszabbítás
                </button>
              </div>
              <p className="mt-1.5 text-[12px] text-text-muted">
                {form.payment_mode === "paid"
                  ? "Az ügyfelek fizetéssel meghosszabbíthatják a hozzáférést lejárat után."
                  : "Az ügyfelek kapcsolatfelvételi üzenetet látnak lejárat után."}
              </p>
            </div>
            <div>
              <div className="flex items-center justify-between">
                <label className={labelClass}>
                  Jelszó {data.has_password ? "(beállítva)" : "(nincs)"}
                </label>
                {data.has_password && (
                  <button type="button" onClick={clearPassword} className="text-[12px] text-text-accent hover:underline">
                    Jelszó törlése
                  </button>
                )}
              </div>
              <input
                type="password"
                value={form.password}
                placeholder={data.has_password ? "Új jelszó (üresen hagyva megmarad)" : "Jelszó beállítása"}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                className={inputClass}
              />
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={save}
              className="flex items-center gap-1.5 rounded-[var(--radius)] px-4 py-2 text-[13px] font-medium text-white"
              style={{ background: "var(--accent-gradient)" }}
            >
              <Save className="h-4 w-4" />
              {saved ? "Mentve" : "Mentés"}
            </button>
            <a
              href={portalHref}
              target="_blank"
              rel="noreferrer"
              className="rounded-[var(--radius)] border border-border px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-3"
            >
              Portál megtekintése
            </a>
            <button
              type="button"
              onClick={makeShare}
              className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-3"
            >
              <Link2 className="h-4 w-4" />
              Megosztó link
            </button>
            <button
              type="button"
              title="Aki ezt a linket kapja, mappákat hozhat létre és feltölthet a portálra - törölni nem tud"
              onClick={() => void linkMasol(() => createFeltoltoLink(initial.id, null))}
              className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-3"
            >
              <Upload className="h-4 w-4" />
              Feltöltő link
            </button>
            <button
              onClick={onDeletePortal}
              className="ml-auto flex items-center gap-2 rounded-[var(--radius)] border border-text-danger/40 px-4 py-2 text-[13px] text-text-danger transition-colors hover:bg-bg-danger"
            >
              <Trash2 className="h-4 w-4" />
              Portál törlése
            </button>
          </div>
          {shareUrl && (
            <p className="mt-3 break-all rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[12px] text-text-muted">
              Másolva: {shareUrl}
            </p>
          )}
        </Card>

        {/* Fájlok / Mappák (Drive-szerű) */}
        <Card className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              {currentFolder && (
                <button
                  onClick={() => setCurrentFolder(null)}
                  title="Vissza"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-surface-3 hover:text-text-primary"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
              )}
              <h2 className="truncate text-[15px] font-medium text-text-primary">{openFolder ? openFolder.name : "Tartalom"}</h2>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {/* Az épp látható elemek kijelölése egyben (a felhasználó
                  kérése) - ha már mind ki van jelölve, ugyanez megszünteti. */}
              {lathatoElemSzam > 0 && (
                <button
                  type="button"
                  onClick={osszesKijelolese}
                  className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[12px] text-text-secondary hover:bg-surface-3"
                >
                  {mindKijelolve ? "Kijelölés megszüntetése" : `Összes kijelölése (${lathatoElemSzam})`}
                </button>
              )}
              <button
                type="button"
                onClick={onCreateFolder}
                className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[12px] text-text-secondary hover:bg-surface-3"
              >
                <FolderPlus className="h-4 w-4" />
                Új mappa
              </button>
            </div>
            <input ref={replaceRef} type="file" accept="video/*" hidden onChange={onReplace} />
          </div>

          <p className="mt-2 text-[12px] text-text-muted">
            {currentFolder
              ? "A feltöltött videók és képek ebbe a mappába kerülnek."
              : "Nyiss meg egy mappát, vagy tölts fel ide videókat és képeket mappa nélkül."}
          </p>

          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDropFiles}
            className={`mt-3 flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-[var(--radius-lg)] border-2 border-dashed px-4 py-8 text-center transition-colors ${
              dragOver ? "border-text-accent/60 bg-bg-accent" : "border-border bg-surface-3 hover:border-text-accent/40"
            }`}
          >
            <Upload className="h-6 w-6 text-text-muted" />
            <span className="text-[13px] text-text-primary">Húzd ide a fájlokat vagy egy egész mappát</span>
            <span className="text-[11px] text-text-muted">
              Mappa húzásakor automatikusan létrejön a mappa a benne lévő fájlokkal. Vagy kattints a tallózáshoz.
            </span>
            <input type="file" accept="video/*,image/*" multiple className="hidden" onChange={onUpload} />
          </label>

          {selectedCount > 0 && (
            <div className="mt-4 flex items-center justify-between rounded-[var(--radius)] border border-text-accent/40 bg-bg-accent px-3 py-2.5">
              <span className="text-[13px] text-text-primary">{selectedCount} kijelölve</span>
              <div className="flex items-center gap-3">
                <button onClick={clearSelection} className="text-[12px] text-text-muted transition-colors hover:text-text-primary">
                  Mégse
                </button>
                <button
                  onClick={onDeleteSelected}
                  className="flex items-center gap-2 rounded-[var(--radius)] border border-text-danger/50 px-3 py-1.5 text-[12px] text-text-danger transition-colors hover:bg-bg-danger"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Kijelöltek törlése
                </button>
              </div>
            </div>
          )}

          {batch && (
            <div className="mt-4 rounded-[var(--radius)] border border-text-accent/40 bg-bg-accent px-3 py-3">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[13px] text-text-primary">
                  Feltöltés: {batch.done} / {batch.total} kép
                </span>
                <span className="text-[11px] text-text-muted">
                  {(() => {
                    if (batch.done === 0) return "Becslés…";
                    const elapsed = (Date.now() - batch.startedAt) / 1000;
                    const perItem = elapsed / batch.done;
                    const remaining = Math.round(perItem * (batch.total - batch.done));
                    if (remaining < 60) return `~${remaining} mp van hátra`;
                    return `~${Math.ceil(remaining / 60)} perc van hátra`;
                  })()}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{ width: `${Math.round((batch.done / batch.total) * 100)}%`, background: "var(--accent-gradient)" }}
                />
              </div>
              <button
                onClick={cancelUploadNow}
                className="mt-2.5 w-full rounded-[var(--radius)] border border-text-danger/40 py-1.5 text-[12px] text-text-danger transition-colors hover:bg-bg-danger"
              >
                Feltöltés leállítása
              </button>
            </div>
          )}

          {videoBatch && (
            <div className="mt-4 rounded-[var(--radius)] border border-text-accent/40 bg-bg-accent px-3 py-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-text-primary">
                  Videó feltöltése: {Math.min(videoBatch.done + 1, videoBatch.total)} / {videoBatch.total}
                </span>
                <span className="text-[11px] text-text-muted">
                  {(() => {
                    if (videoBatch.done === 0) return "Becslés…";
                    const elapsed = (Date.now() - videoBatch.startedAt) / 1000;
                    const perItem = elapsed / videoBatch.done;
                    const remaining = Math.round(perItem * (videoBatch.total - videoBatch.done));
                    if (remaining < 60) return `~${remaining} mp van hátra`;
                    return `~${Math.ceil(remaining / 60)} perc van hátra`;
                  })()}
                </span>
              </div>
            </div>
          )}

          {uploads.length > 0 && (
            <div className="mt-4 space-y-2">
              {uploads.map((u) => (
                <div key={u.name} className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="truncate text-[13px] text-text-primary">{u.name}</span>
                    <span className="text-[11px] text-text-muted">{u.percent < 100 ? `${u.percent}%` : "Feldolgozás…"}</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="h-full rounded-full transition-all duration-200"
                      style={{ width: `${u.percent}%`, background: "var(--accent-gradient)" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!currentFolder && folders.length > 0 && (
            <ul className="mt-4 space-y-2">
              {mappakUjElol.map((f) => {
                const vCount = videos.filter((v) => v.folder_id === f.id).length;
                const iCount = images.filter((i) => i.folder_id === f.id).length;
                return (
                  <li key={f.id} className="flex items-center gap-3 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
                    <button onClick={() => setCurrentFolder(f.id)} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                      <FolderIcon className="h-5 w-5 shrink-0 text-text-accent" />
                      <span className="truncate text-[13px] text-text-primary">{f.name}</span>
                      <span className="ml-auto shrink-0 text-[11px] text-text-muted">{vCount + iCount} elem</span>
                    </button>
                    <button
                      title="Mappa megosztó link (aki kapja, csak ezt a mappát látja)"
                      onClick={() => void linkMasol(() => createFolderShareLink(f.id))}
                      className="text-text-muted transition-colors hover:text-text-primary"
                    >
                      <Link2 className="h-4 w-4" />
                    </button>
                    <button
                      title="Feltöltő link ebbe a mappába (feltölthet, nem törölhet)"
                      onClick={() => void linkMasol(() => createFeltoltoLink(initial.id, f.id))}
                      className="text-text-muted transition-colors hover:text-text-primary"
                    >
                      <Upload className="h-4 w-4" />
                    </button>
                    <button title="Átnevezés" onClick={() => onRenameFolder(f.id)} className="text-text-muted transition-colors hover:text-text-primary">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button title="Mappa törlése" onClick={() => onDeleteFolder(f.id)} className="text-text-muted transition-colors hover:text-text-danger">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <ul className="mt-2 space-y-2">
            {visibleVideos.map((v) => {
              const isSelected = selectedVideos.has(v.id);
              return (
                <li
                  key={v.id}
                  draggable={!isSelected}
                  onDragStart={() => (dragId.current = v.id)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => onDrop(v.id)}
                  className={`flex items-center gap-2 rounded-[var(--radius)] border bg-surface-3 px-2.5 py-2.5 sm:gap-3 sm:px-3 ${
                    isSelected ? "border-text-accent/60" : "border-border"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleVideo(v.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="h-4 w-4 shrink-0 cursor-pointer accent-[var(--accent-solid)]"
                  />
                  <GripVertical className="hidden h-4 w-4 shrink-0 cursor-grab text-text-muted sm:block" />
                  <div className="h-9 w-12 shrink-0 overflow-hidden rounded-[var(--radius)] bg-surface-2 sm:w-16">
                    {v.thumbnail_url && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={v.thumbnail_url} alt="" className="h-full w-full object-cover" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] text-text-primary">{v.title}</p>
                    <p className="text-[11px] text-text-muted">
                      {v.status === "ready"
                        ? `${v.resolution_label} · ${formatDuration(v.duration_seconds)} · ${formatBytes(v.size_bytes)}`
                        : v.status === "processing"
                          ? "Feldolgozás…"
                          : "Sikertelen"}
                    </p>
                  </div>
                  {currentFolder && (
                    <button title="Kivétel a mappából" onClick={() => onRemoveFromFolder(v.id)} className="text-text-muted transition-colors hover:text-text-primary">
                      <ArrowLeft className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    title="Videó megosztó link (aki kapja, csak ezt a videót látja)"
                    onClick={() => void linkMasol(() => createVideoShareLink(v.id))}
                    className="text-text-muted transition-colors hover:text-text-primary"
                  >
                    <Link2 className="h-4 w-4" />
                  </button>
                  <button title="Átnevezés" onClick={() => onRenameVideo(v.id)} className="text-text-muted transition-colors hover:text-text-primary">
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    title="Csere"
                    onClick={() => {
                      replaceId.current = v.id;
                      replaceRef.current?.click();
                    }}
                    className="text-text-muted transition-colors hover:text-text-primary"
                  >
                    <Replace className="h-4 w-4" />
                  </button>
                  <button title="Törlés" onClick={() => onDeleteVideo(v.id)} className="text-text-muted transition-colors hover:text-text-danger">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              );
            })}
            {visibleVideos.length === 0 && (
              <li className="py-8 text-center text-[13px] text-text-muted">
                {currentFolder ? "Nincs videó ebben a mappában." : "Nincs mappán kívüli videó."}
              </li>
            )}
          </ul>

          {visibleImages.length > 0 && (
            <div className="mt-6">
              <h3 className="mb-3 text-[11px] font-medium uppercase tracking-wide text-text-muted">Képek ({visibleImages.length})</h3>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                {visibleImages.map((img) => (
                  <LazyImageCell
                    key={img.id}
                    img={img}
                    selected={selectedImages.has(img.id)}
                    inFolder={!!currentFolder}
                    onToggle={() => toggleImage(img.id)}
                    onRemoveFromFolder={() => onRemoveImageFromFolder(img.id)}
                    onDelete={() => onDeleteImage(img.id)}
                  />
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {prompt && (
        <PromptDialog
          title={prompt.title}
          initialValue={prompt.value}
          onCancel={() => setPrompt(null)}
          onConfirm={(value) => {
            const cb = prompt.onConfirm;
            setPrompt(null);
            cb(value);
          }}
        />
      )}

      {confirmDialog && (
        <ConfirmDialog
          message={confirmDialog.message}
          onCancel={() => setConfirmDialog(null)}
          onConfirm={() => {
            const cb = confirmDialog.onConfirm;
            setConfirmDialog(null);
            cb();
          }}
        />
      )}
    </div>
  );
}

function LazyImageCell({
  img,
  selected,
  inFolder,
  onToggle,
  onRemoveFromFolder,
  onDelete,
}: {
  img: PortalImageItem;
  selected: boolean;
  inFolder: boolean;
  onToggle: () => void;
  onRemoveFromFolder: () => void;
  onDelete: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { rootMargin: "600px 0px" });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`group relative aspect-square overflow-hidden rounded-[var(--radius)] border bg-surface-2 ${
        selected ? "border-text-accent/60 ring-2 ring-text-accent/40" : "border-border"
      }`}
    >
      {visible && (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img.thumbnail_url || img.url} alt={img.title ?? ""} loading="lazy" decoding="async" className="h-full w-full object-cover" />
          <label className="absolute left-2 top-2 z-20 flex h-6 w-6 cursor-pointer items-center justify-center rounded bg-black/60" onClick={(e) => e.stopPropagation()}>
            <input type="checkbox" checked={selected} onChange={onToggle} className="h-4 w-4 cursor-pointer accent-[var(--accent-solid)]" />
          </label>
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center gap-2 bg-black/50 opacity-0 transition group-hover:opacity-100">
            {inFolder && (
              <button
                title="Kivétel a mappából"
                onClick={onRemoveFromFolder}
                className="pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white transition hover:text-white/80"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
            )}
            <button
              title="Törlés"
              onClick={onDelete}
              className="pointer-events-auto flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white transition hover:text-text-danger"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className={labelClass}>{label}</label>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      />
    </div>
  );
}

function PromptDialog({
  title,
  initialValue,
  onCancel,
  onConfirm,
}: {
  title: string;
  initialValue: string;
  onCancel: () => void;
  onConfirm: (value: string) => void;
}) {
  const [value, setValue] = useState(initialValue);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={onCancel}>
      <div className="w-full max-w-sm rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-[15px] font-medium text-text-primary">{title}</h3>
        <input
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onConfirm(value);
            if (e.key === "Escape") onCancel();
          }}
          className={inputClass}
        />
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-[var(--radius)] border border-border px-4 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Mégse
          </button>
          <button
            type="button"
            onClick={() => onConfirm(value)}
            className="rounded-[var(--radius)] px-4 py-1.5 text-[13px] font-medium text-white"
            style={{ background: "var(--accent-gradient)" }}
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
}

function ConfirmDialog({ message, onCancel, onConfirm }: { message: string; onCancel: () => void; onConfirm: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={onCancel}>
      <div className="w-full max-w-sm rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6" onClick={(e) => e.stopPropagation()}>
        <p className="text-[13px] leading-relaxed text-text-primary">{message}</p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-[var(--radius)] border border-border px-4 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Mégse
          </button>
          <button
            onClick={onConfirm}
            className="flex items-center gap-2 rounded-[var(--radius)] border border-text-danger/40 px-4 py-2 text-[13px] text-text-danger transition-colors hover:bg-bg-danger"
          >
            Törlés
          </button>
        </div>
      </div>
    </div>
  );
}
