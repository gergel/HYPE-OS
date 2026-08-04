"use client";

import { useRouter } from "next/navigation";

/** "Vissza" link minden részletnézet tetején. Ha a felhasználó az appon
 * belülről navigált ide (bármelyik listáról/kapcsolódó nézetről) - lásd
 * NavigationTracker, ami útvonalanként számolja az app-on belüli lépéseket -
 * a kattintás a valódi böngésző-"vissza" navigációt indítja (router.back()) -
 * ez pontosan oda dobja vissza a felhasználót, ahonnan jött (megtartva a
 * lista szűrését, rendezését, scroll pozícióját is), FÜGGETLENÜL attól, hogy
 * melyik oldalról nyitották meg ezt a rekordot. Nem a nyers
 * `window.history.length`-et nézzük, mert az egy vadonatúj tab-ban/ablakban
 * is simán 2+ lehet (pl. about:blank -> a nyitott URL), tévesen "van
 * előzmény"-t jelezve. A `href`/`label` csak akkor kerül elő, ha nincs
 * app-on belüli előzmény (pl. közvetlen URL-lel/könyvjelzővel nyitották meg
 * a lapot) - ilyenkor ez a legjobb elérhető alapértelmezett cél. */
export function BackLink({ href, label }: { href: string; label: string }) {
  const router = useRouter();

  return (
    <a
      data-app-chrome
      href={href}
      onClick={(e) => {
        e.preventDefault();
        const navCount = typeof window !== "undefined" ? Number(sessionStorage.getItem("hype_nav_count") || "0") : 0;
        if (navCount > 1) {
          router.back();
        } else {
          router.push(href);
        }
      }}
      className="inline-flex cursor-pointer items-center gap-1.5 text-[13px] text-text-muted transition-colors duration-200 hover:text-text-primary"
    >
      ← {label}
    </a>
  );
}
