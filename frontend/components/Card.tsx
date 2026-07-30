import type { LucideIcon } from "lucide-react";

/** A kártya kerete - a CollapsibleCard is ezt használja, hogy az összecsukható
 * kártyák pontosan ugyanúgy nézzenek ki, mint a többi. */
export const CARD_CLASS =
  "rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5 shadow-[0_1px_0_rgba(255,255,255,0.03)_inset,0_8px_24px_-16px_rgba(0,0,0,0.6)]";

export function Card({
  title,
  icon: Icon,
  actions,
  children,
  className = "",
}: {
  title?: string;
  /** Opcionális kis ikon a cím elé (lásd referenciakép: minden kártya-cím
   * mellett egy témajelző ikon áll) - accent színnel, hogy vizuálisan is
   * elkülönítse a kártya témáját (Diszpó/Technika/stb.). */
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
        <div className="mb-3 flex items-center justify-between gap-2">
          <p className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
            {Icon && <Icon size={15} strokeWidth={2} className="text-text-accent" aria-hidden />}
            {title}
          </p>
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}
