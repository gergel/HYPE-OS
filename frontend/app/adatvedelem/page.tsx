import { CookieConsent } from "@/components/media-portal/CookieConsent";

export const metadata = {
  title: "Adatkezelési Tájékoztató — HYPE Productions",
};

/** Adatkezelési tájékoztató a PUBLIKUS portálhoz.
 *
 * A portál fizetési folyamata (Barion + süti-hozzájárulás) miatt kell: a
 * fizetési űrlapról és a süti-sávról is ide hivatkozunk. Ezért a HYPE OS
 * bejelentkezésen KÍVÜL él, ugyanúgy, mint a /p/[slug] portál-oldal. */
export default function AdatvedelemPage() {
  const sections = [
    {
      h: "1. Az adatkezelő",
      p: "Cégnév: Hype Productions Korlátolt Felelősségű Társaság (Hype Productions Kft.) · Székhely: 3036 Gyöngyöstarján, Kossuth Lajos utca 3. · Cégjegyzékszám: 10-09-041944 · Adószám: 23995828-2-10 · E-mail: info@hypestab.hu · Honlap: https://hypeclient.com. Az adatkezelő a jelen tájékoztatóban meghatározott adatokat a hatályos adatvédelmi jogszabályok szerint kezeli.",
    },
    {
      h: "2. A kezelt adatok köre, célja és jogalapja",
      p: "Számlázási adatok, fizetési adatok és technikai adatok kezelése a szolgáltatás nyújtásához szükséges módon történik.",
    },
    {
      h: "3. Adatfeldolgozók",
      p: "Barion Payment Zrt., Számlázz.hu / KBOSS.hu Kft.",
    },
    {
      h: "4. Az adatkezelés időtartama",
      p: "A számlázási adatokat 8 évig őrizzük meg a hatályos jogszabályok szerint.",
    },
    {
      h: "5. Sütik (cookie-k)",
      p: "A weboldal működéséhez szükséges és opcionális analitikai sütiket használ.",
    },
    {
      h: "6. Adattovábbítás",
      p: "Személyes adatot kizárólag a szolgáltatás teljesítéséhez szükséges esetekben továbbítunk.",
    },
    {
      h: "7. Az érintett jogai",
      p: "Hozzáférés, helyesbítés, törlés, korlátozás, adathordozhatóság, tiltakozás.",
    },
    {
      h: "8. Jogorvoslat",
      p: "NAIH vagy bírósági jogorvoslat vehető igénybe.",
    },
    {
      h: "9. Az adatkezelés biztonsága",
      p: "Megfelelő technikai és szervezési intézkedéseket alkalmazunk.",
    },
    {
      h: "10. A tájékoztató módosítása",
      p: "A mindenkor hatályos verzió a weboldalon érhető el.",
    },
  ];

  return (
    <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
      <main className="mx-auto max-w-3xl px-6 py-16 sm:py-24">
        <a
          href="/"
          className="font-mono text-xs uppercase tracking-eyebrow text-mist transition hover:text-bone"
        >
          ← Vissza
        </a>

        <h1 className="mt-6 font-display text-3xl text-bone sm:text-4xl">
          Adatkezelési Tájékoztató
        </h1>

        <p className="mt-3 font-mono text-xs uppercase tracking-eyebrow text-mist">
          Hatályos: 2026. — HYPE Productions Kft.
        </p>

        <div className="mt-10 space-y-10">
          {sections.map((section) => (
            <section key={section.h}>
              <h2 className="mb-3 text-lg font-semibold text-bone">
                {section.h}
              </h2>

              <p className="text-sm leading-relaxed text-mist">
                {section.p}
              </p>
            </section>
          ))}
        </div>
      </main>
      <CookieConsent />
    </div>
  );
}
