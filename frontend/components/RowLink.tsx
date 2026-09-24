"use client";

import { useRouter } from "next/navigation";
import { useFelugroNyitas } from "@/components/FelugroAblak";
import type { ReactNode } from "react";

export function RowLink({
  href,
  onClick,
  children,
  className = "",
}: {
  href?: string;
  /** Ha meg van adva, ez fut le kattintáskor a href-es router.push HELYETT
   * (pl. részletnézet felugró ablakban való megnyitásához navigáció
   * helyett) - lásd ProjektekContent.tsx. */
  onClick?: () => void;
  children: ReactNode;
  className?: string;
}) {
  const router = useRouter();
  // A felugró területeken (Pénzügyek, projektkódok) a sor felugró ablakban
  // nyílik, nem navigál - lásd components/FelugroAblak.tsx.
  const felugro = useFelugroNyitas();
  return (
    <tr
      onClick={() => {
        if (onClick) onClick();
        else if (href && !felugro?.(href)) router.push(href);
      }}
      className={`cursor-pointer hover:bg-surface-3 ${className}`}
    >
      {children}
    </tr>
  );
}
