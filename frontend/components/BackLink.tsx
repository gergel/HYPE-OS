import Link from "next/link";

export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="mb-3 inline-block text-[13px] text-text-secondary hover:text-text-primary">
      ← {label}
    </Link>
  );
}
