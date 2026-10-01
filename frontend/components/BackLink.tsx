"use client";

import { useRouter } from "next/navigation";
import { PREV_PATH_KEY } from "@/components/NavigationTracker";

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
export function BackLink({
  href,
  label,
  csakInnen = false,
}: {
  href: string;
  label: string;
  /** Igaz: a böngésző-vissza CSAK akkor, ha a felhasználó tényleg a `href`
   * oldaláról jött ide - különben egyenesen a `href`-re visz. Ott kell, ahol
   * a link egy konkrét listát ígér („← Belsősök”): a puszta előzmény-lépés
   * egy közbeiktatott (pl. felugró ablakos) lépés után máshova - például a
   * projektkódokhoz - dobott vissza (a felhasználó hibajelzése). */
  csakInnen?: boolean;
}) {
  const router = useRouter();

  return (
    <a
      data-app-chrome
      href={href}
      onClick={(e) => {
        e.preventDefault();
        const navCount = typeof window !== "undefined" ? Number(sessionStorage.getItem("hype_nav_count") || "0") : 0;
        const innenJott = !csakInnen || sessionStorage.getItem(PREV_PATH_KEY) === href.split("?")[0];
        if (navCount > 1 && innenJott) {
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
