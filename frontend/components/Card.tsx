import type { LucideIcon } from "lucide-react";

/** A kártya kerete - a CollapsibleCard is ezt használja, hogy az összecsukható
 * kártyák pontosan ugyanúgy nézzenek ki, mint a többi. Nincs erős árnyék: a réteget a felület kontrasztja és egy
 * hajszálvékony keret adja - ettől hat "megmunkált fém lapnak", nem lebegő
 * dobozanak. A belső fény-vonal (inset) csak annyi, hogy a felső él
 * elkülönüljön a háttértől. */
export const CARD_CLASS =
  "rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]";

export function Card({
  title,
  icon: Icon,
  actions,
  children,
  className = "",
}: {
  title?: string;
  /** Opcionális kis ikon a cím elé - halkan, a cím alárendelt jelzéseként.
   * Nem színez: a kártya témáját a CÍM mondja meg, az ikon csak segít
   * gyorsan megtalálni a kártyát görgetés közben. */
  icon?: LucideIcon;
  /** Opcionális jobbra igazított tartalom a cím mellett (pl. hónapváltó
   * nyilak) - csak akkor jelenik meg, ha van title is. */
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`${CARD_CLASS} ${className}`}>
      {title && (
        <div className="mb-4 flex items-center justify-between gap-3">
          <p className="t-card flex items-center gap-2">
            {Icon && <Icon size={14} strokeWidth={1.75} className="shrink-0 text-text-muted" aria-hidden />}
            {title}
          </p>
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}
