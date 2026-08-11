"use client";

import Script from "next/script";

/** A Barion Base Pixel betöltése - CSAK a publikus portál-oldalakon.
 *
 * Szándékosan nem a gyökér layoutban ül: a HYPE OS belső felülete a saját
 * munkatársainké, ott nincs mit követni, és egy külső követő szkriptet sem
 * akarunk minden admin oldalra betölteni. A portál viszont ügyfeleknek szól és
 * fizetés is történik rajta, amihez a Barion a Pixelt kéri.
 *
 * Pixel ID nélkül nem tölt be semmit - fejlesztés közben és olyan telepítésnél,
 * ahol nincs Barion, a portál pontosan ugyanúgy működik.
 *
 * A tényleges esemény-küldést a lib/barionPixel.ts segédei végzik; a marketing
 * célú adatküldés csak a süti-hozzájárulás után indul (lásd CookieConsent). */
export function BarionPixel() {
  const pixelId = process.env.NEXT_PUBLIC_BARION_PIXEL_ID;
  if (!pixelId) return null;

  return (
    <Script id="barion-pixel" strategy="afterInteractive">
      {`
        window["bp"] = window["bp"] || function () {
          (window["bp"].q = window["bp"].q || []).push(arguments);
        };
        window["bp"].l = 1 * new Date();
        var scriptElement = document.createElement("script");
        var firstScript = document.getElementsByTagName("script")[0];
        scriptElement.async = true;
        scriptElement.src = "https://pixel.barion.com/bp.js";
        firstScript.parentNode.insertBefore(scriptElement, firstScript);
        window["barion_pixel_id"] = "${pixelId}";
        bp("init", "addBarionPixelId", window["barion_pixel_id"]);
      `}
    </Script>
  );
}
