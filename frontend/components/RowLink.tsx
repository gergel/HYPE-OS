"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

export function RowLink({
  href,
  children,
  className = "",
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  const router = useRouter();
  return (
    <tr
      onClick={() => router.push(href)}
      className={`cursor-pointer border-b border-border last:border-0 hover:bg-surface-3 ${className}`}
    >
      {children}
    </tr>
  );
}
