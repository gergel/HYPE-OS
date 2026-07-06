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
const portalDisplay = Fraunces({
  subsets: ["latin"],
  variable: "--font-portal-display",
  weight: ["400", "500", "600"],
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
