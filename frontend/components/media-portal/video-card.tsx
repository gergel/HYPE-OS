"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { Play, Download, Loader2, Link as LinkIcon } from "lucide-react";
import { PortalVideo } from "@/lib/portalApi";
import { formatDuration, downloadVideo } from "@/lib/portalUtils";

export function VideoCard({
  video,
  index,
  onPlay,
  isNew = false,
  onShare,
}: {
  video: PortalVideo;
  index: number;
  onPlay: (v: PortalVideo) => void;
  /** Még meg nem nyitott videó (localStorage-ban követve, lásd portal-view.tsx
   * seenVideos) - "Új" címkét kap, hogy az ügyfél lássa, mit nem nézett még meg. */
  isNew?: boolean;
  /** A videó saját megosztó linkjének másolása (a felhasználó kérése: a
   * portál-nézetből is lehessen linket továbbküldeni). */
  onShare?: () => void;
}) {
  const [preparing, setPreparing] = useState(false);
  async function handleDownload(e: React.MouseEvent) {
    e.stopPropagation();
    if (preparing) return;
    setPreparing(true);
    try {
      await downloadVideo(video.id, video.mp4_url, `${video.title}.mp4`, video.size_bytes);
    } finally {
      setTimeout(() => setPreparing(false), 1200);
    }
  }
  return (
    <motion.article
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, delay: (index % 3) * 0.08, ease: [0.16, 1, 0.3, 1] }}
      className="group relative overflow-hidden rounded-3xl border border-ink-line bg-ink-card"
    >
      <button
        onClick={() => onPlay(video)}
        className="relative block aspect-video w-full overflow-hidden"
        aria-label={`Lejátszás: ${video.title}`}
      >
        {video.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={video.thumbnail_url}
            alt={video.title}
            className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
          />
        ) : (
          <div className="h-full w-full bg-ink-soft" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent opacity-80 transition-opacity group-hover:opacity-95" />
        {isNew && (
          <span className="absolute left-3 top-3 rounded-full bg-flare px-2.5 py-1 font-mono text-[11px] font-semibold uppercase tracking-eyebrow text-white shadow-lg">
            Új
          </span>
        )}
        <span className="absolute left-1/2 top-1/2 flex h-16 w-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/30 bg-black/30 backdrop-blur-md transition-all duration-500 group-hover:scale-110 group-hover:border-white/60">
          <Play className="ml-0.5 h-6 w-6 fill-bone text-bone" />
        </span>
        <span className="absolute bottom-3 right-3 rounded-full bg-black/60 px-2.5 py-1 font-mono text-xs text-bone backdrop-blur-sm">
          {formatDuration(video.duration_seconds)}
        </span>
      </button>
      <div className="flex items-center justify-between gap-3 px-5 py-4">
        <div className="min-w-0">
          <h3 className="truncate font-display text-lg text-bone">{video.title}</h3>
          <p className="mt-0.5 font-mono text-[11px] uppercase tracking-eyebrow text-mist">
            {video.resolution_label}
            {video.aspect_ratio_label ? ` · ${video.aspect_ratio_label}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {onShare && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onShare();
              }}
              aria-label={`Link másolása: ${video.title}`}
              title="A videó linkjének másolása - aki megkapja, csak ezt a videót látja"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-ink-line text-mist transition hover:border-bone/60 hover:text-bone"
            >
              <LinkIcon className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={handleDownload}
            disabled={preparing}
            aria-label={`Letöltés: ${video.title}`}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-bone text-ink transition hover:bg-white disabled:opacity-60"
          >
            {preparing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </motion.article>
  );
}
