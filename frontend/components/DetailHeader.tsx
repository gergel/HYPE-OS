import type { ReactNode } from "react";
import { BackLink } from "@/components/BackLink";

/** Sticky-szerű fejléc egy részletnézet tetején: kenyérmorzsa (vissza-link +
 * lista neve), nagy cím + állapot-pill, opcionális alcím-sor (pl. kapcsolódó
 * rekordokra mutató linkek), és jobbra igazított akció-gombok (pl. Törlés,
 * egyedi backend-akciók) - egységes, rendezett belépési pont minden
 * részletnézethez, ahelyett hogy entitásonként külön-külön rendezetlenül
 * jelenne meg a cím/akció-sáv. */
export function DetailHeader({
  backHref,
  backLabel,
  title,
  statusBadge,
  subtitle,
  actions,
}: {
  /** Elhagyható: felugró ablakba ágyazott részletnézetnél nincs hova
   * "visszalépni" (lásd ProjectDetailContent embedded módja). */
  backHref?: string;
  backLabel?: string;
  title: string;
  statusBadge?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="border-b border-border pb-4">
      {backHref && <BackLink href={backHref} label={backLabel ?? "Vissza"} />}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="truncate text-2xl font-semibold text-text-primary">{title}</h1>
            {statusBadge}
          </div>
          {subtitle && <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[13px] text-text-secondary">{subtitle}</div>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
