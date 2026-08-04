"use client";

import { useRouter } from "next/navigation";
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
  return (
    <tr
      onClick={() => (onClick ? onClick() : href && router.push(href))}
      className={`cursor-pointer hover:bg-surface-3 ${className}`}
    >
      {children}
    </tr>
  );
}
