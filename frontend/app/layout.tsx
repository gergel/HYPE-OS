import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Csak a Média Portál ügyfél-nézetéhez (/p/[slug]) kell - a "font-display"
// Tailwind utility (lásd app/portal-theme.css) ezt használja, a HYPE OS admin
// felület sehol nem hivatkozik rá.
//
// NINCS `weight` felsorolás, és ez fontos: a Fraunces VÁLTOZÓ (variable) font,
// a Google pedig már nem szolgálja ki a belőle vágott statikus súlyokat - a
// konkrét 400/500/600 kérésre 404-et ad, amitől a production build elhasal
// ("Module not found: @vercel/turbopack-next/internal/font/google/font").
// Weight nélkül a változó fájl jön, ami a teljes 100-900 tartományt lefedi,
// tehát a portál megjelenése nem változik - csak egy fájlból.
//
// A "latin-ext" azért kell, mert az ő és az ű a Latin Extended-A blokkban van:
// enélkül a magyar szövegben pont ez a két betű esne vissza egy másik fontra.
const portalDisplay = Fraunces({
  subsets: ["latin", "latin-ext"],
  variable: "--font-portal-display",
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "HYPE OS",
  description: "HYPE OS - belső operatív rendszer videóprodukciós működésre",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="hu"
      className={`${geistSans.variable} ${geistMono.variable} ${portalDisplay.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background text-text-primary">{children}</body>
    </html>
  );
}
