"use client";
import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import { X, Download, Loader2, Link as LinkIcon, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { PortalVideo } from "@/lib/portalApi";
import { downloadVideo } from "@/lib/portalUtils";

export function VideoPlayer({
  video,
  onClose,
  onShare,
}: {
  video: PortalVideo;
  onClose: () => void;
  /** A videó megosztó linkjének másolása a NAGYBAN megnyitott nézetből is
   * (a felhasználó kérése) - lásd PortalView.linkreMasol. */
  onShare?: () => void;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [linkMasolva, setLinkMasolva] = useState(false);

  function handleShare() {
    onShare?.();
    setLinkMasolva(true);
    window.setTimeout(() => setLinkMasolva(false), 2500);
  }

  async function handleDownload() {
    if (preparing) return;
    setPreparing(true);
    try {
      await downloadVideo(video.id, video.mp4_url, `${video.title}.mp4`, video.size_bytes);
    } finally {
      setTimeout(() => setPreparing(false), 1200);
    }
  }

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let hls: Hls | null = null;
    const hasHls = !!video.hls_url;
    if (hasHls && el.canPlayType("application/vnd.apple.mpegurl")) {
      el.src = video.hls_url;
    } else if (hasHls && Hls.isSupported()) {
      hls = new Hls({ enableWorker: true });
      hls.loadSource(video.hls_url);
      hls.attachMedia(el);
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (data.fatal && video.mp4_url) {
          hls?.destroy();
          el.src = video.mp4_url;
          el.play().catch(() => {});
        } else if (data.fatal) {
          setError(true);
        }
      });
    } else if (video.mp4_url) {
      el.src = video.mp4_url;
    } else {
      setError(true);
    }
    el.play().catch(() => {});
    return () => {
      hls?.destroy();
    };
  }, [video]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-md p-4 sm:p-8"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <button
          aria-label="Bezárás"
          onClick={onClose}
          className="absolute right-5 top-5 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-white/15 text-bone transition hover:bg-white/10"
        >
          <X className="h-5 w-5" />
        </button>
        <motion.div
          className="w-full max-w-6xl overflow-hidden rounded-2xl border border-ink-line bg-ink shadow-2xl"
          initial={{ scale: 0.96, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.96, opacity: 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          onClick={(e) => e.stopPropagation()}
        >
          {error ? (
            <div className="flex aspect-video items-center justify-center text-mist">
              Ez a videó jelenleg nem játszható le.
            </div>
          ) : (
            <video ref={ref} controls playsInline poster={video.thumbnail_url} className="aspect-video w-full bg-black" />
          )}
          <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
            <div className="min-w-0">
              <h3 className="truncate font-display text-lg text-bone">{video.title}</h3>
              <span className="font-mono text-xs uppercase tracking-eyebrow text-mist">{video.resolution_label}</span>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2.5">
            {onShare && (
              <button
                onClick={handleShare}
                title="A videó linkjének másolása - aki megkapja, csak ezt a videót látja"
                className="flex items-center gap-2 whitespace-nowrap rounded-full border border-ink-line px-5 py-3 text-sm text-bone transition hover:border-bone/60"
              >
                {linkMasolva ? <Check className="h-5 w-5" /> : <LinkIcon className="h-5 w-5" />}
                {linkMasolva ? "Link másolva" : "Link másolása"}
              </button>
            )}
            <button
              onClick={handleDownload}
              disabled={preparing}
              className="flex min-w-[140px] shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-full bg-bone px-6 py-3 text-sm font-medium text-ink transition hover:bg-white disabled:opacity-60"
            >
              <span className="flex items-center gap-2">
                {preparing ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Előkészítés…
                  </>
                ) : (
                  <>
                    <Download className="h-5 w-5" />
                    Letöltés
                  </>
                )}
              </span>
            </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
