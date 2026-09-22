"use client";

import { Fragment, useMemo } from "react";
import Link from "next/link";

/** KÖNNYŰ, BIZTONSÁGOS markdown-megjelenítő (a felhasználó kérése: az AI
 * chatben és a kommentekben lehessen formázottan írni és olvasni).
 *
 * Szándékosan nem HTML-t állít elő (nincs dangerouslySetInnerHTML, tehát
 * nincs XSS-felület), hanem React-elemekre bontja a szöveget. A támogatott
 * készlet a hétköznapi jegyzet-formázás: # címsorok, **félkövér**, *dőlt*,
 * `kód`, ``` kódblokk, - felsorolás, 1. számozott lista, > idézet, [cím](url)
 * linkek, nyers http(s)/www linkek, és @Név kiemelés (mentions kapcsolóval).
 * A formázatlan szöveg pontosan úgy jelenik meg, mint eddig. */

const URL_MINTA = /(https?:\/\/[^\s<>"')]+|www\.[^\s<>"')]+)/;
const MENTION_MINTA = /(@[\p{L}\p{N}][\p{L}\p{N} ._-]{0,40})/u;

type InlineElem = string | { t: "code" | "b" | "i" | "link" | "url" | "mention"; s: string; href?: string };

/** Az inline jelölések feldolgozása egy szövegdarabon - determinisztikus
 * sorrendben (kód → link → félkövér → dőlt → URL → mention), hogy a
 * jelölések ne akadjanak össze. */
function inlineDarabok(szoveg: string, mentions: boolean): InlineElem[] {
  const minta = new RegExp(
    [
      "(`[^`\\n]+`)", // inline kód
      "(\\[[^\\]\\n]+\\]\\([^)\\s]+\\))", // [cím](url)
      "(\\*\\*[^*\\n]+\\*\\*)", // **félkövér**
      "(\\*[^*\\n]+\\*)", // *dőlt*
      URL_MINTA.source,
      ...(mentions ? [MENTION_MINTA.source] : []),
    ].join("|"),
    "gu",
  );
  const ki: InlineElem[] = [];
  let utolso = 0;
  let m: RegExpExecArray | null;
  while ((m = minta.exec(szoveg)) !== null) {
    if (m.index > utolso) ki.push(szoveg.slice(utolso, m.index));
    const d = m[0];
    if (d.startsWith("`")) ki.push({ t: "code", s: d.slice(1, -1) });
    else if (d.startsWith("[")) {
      const lm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(d);
      ki.push(lm ? { t: "link", s: lm[1], href: lm[2] } : d);
    } else if (d.startsWith("**")) ki.push({ t: "b", s: d.slice(2, -2) });
    else if (d.startsWith("*")) ki.push({ t: "i", s: d.slice(1, -1) });
    else if (d.startsWith("@")) ki.push({ t: "mention", s: d });
    else {
      // Nyers URL - a mondatzáró írásjel ne legyen a link része.
      const zaro = /[.,;:!?)]+$/.exec(d)?.[0] ?? "";
      ki.push({ t: "url", s: zaro ? d.slice(0, -zaro.length) : d });
      if (zaro) ki.push(zaro);
    }
    utolso = m.index + d.length;
  }
  if (utolso < szoveg.length) ki.push(szoveg.slice(utolso));
  return ki;
}

function Inline({ szoveg, mentions }: { szoveg: string; mentions: boolean }) {
  return (
    <>
      {inlineDarabok(szoveg, mentions).map((d, i) => {
        if (typeof d === "string") return <Fragment key={i}>{d}</Fragment>;
        if (d.t === "code")
          return (
            <code key={i} className="rounded bg-surface-3 px-1 py-[1px] text-[0.92em] text-text-primary">
              {d.s}
            </code>
          );
        if (d.t === "b")
          return (
            <b key={i} className="font-semibold">
              <Inline szoveg={d.s} mentions={mentions} />
            </b>
          );
        if (d.t === "i")
          return (
            <i key={i}>
              <Inline szoveg={d.s} mentions={mentions} />
            </i>
          );
        if (d.t === "mention")
          return (
            <span key={i} className="text-text-accent">
              {d.s}
            </span>
          );
        const href = d.t === "url" ? (d.s.startsWith("http") ? d.s : `https://${d.s}`) : d.href ?? "";
        const cim = d.t === "url" ? d.s : d.s;
        if (href.startsWith("/")) {
          return (
            <Link key={i} href={href} className="text-text-accent hover:underline">
              {cim}
            </Link>
          );
        }
        // Csak http(s) mehet ki külső linkként - a javascript:-féle sémákat
        // nem tesszük kattinthatóvá.
        if (!/^https?:\/\//.test(href)) return <Fragment key={i}>{cim}</Fragment>;
        return (
          <a key={i} href={href} target="_blank" rel="noopener noreferrer" className="text-text-accent underline hover:no-underline">
            {cim}
          </a>
        );
      })}
    </>
  );
}

type Blokk =
  | { t: "p" | "idezet"; sorok: string[] }
  | { t: "h"; szint: number; s: string }
  | { t: "ul" | "ol"; elemek: string[] }
  | { t: "kod"; s: string }
  | { t: "hr" }
  | { t: "ures" };

function blokkok(szoveg: string): Blokk[] {
  const ki: Blokk[] = [];
  const sorok = szoveg.replace(/\r\n/g, "\n").split("\n");
  let i = 0;
  while (i < sorok.length) {
    const sor = sorok[i];
    if (sor.trim().startsWith("```")) {
      const kod: string[] = [];
      i++;
      while (i < sorok.length && !sorok[i].trim().startsWith("```")) {
        kod.push(sorok[i]);
        i++;
      }
      i++; // a záró ``` átlépése
      ki.push({ t: "kod", s: kod.join("\n") });
      continue;
    }
    const h = /^(#{1,3})\s+(.*)$/.exec(sor);
    if (h) {
      ki.push({ t: "h", szint: h[1].length, s: h[2] });
      i++;
      continue;
    }
    if (/^\s*(---|\*\*\*)\s*$/.test(sor)) {
      ki.push({ t: "hr" });
      i++;
      continue;
    }
    if (/^\s*[-*]\s+/.test(sor)) {
      const elemek: string[] = [];
      while (i < sorok.length && /^\s*[-*]\s+/.test(sorok[i])) {
        elemek.push(sorok[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      ki.push({ t: "ul", elemek });
      continue;
    }
    if (/^\s*\d+[.)]\s+/.test(sor)) {
      const elemek: string[] = [];
      while (i < sorok.length && /^\s*\d+[.)]\s+/.test(sorok[i])) {
        elemek.push(sorok[i].replace(/^\s*\d+[.)]\s+/, ""));
        i++;
      }
      ki.push({ t: "ol", elemek });
      continue;
    }
    if (/^\s*>\s?/.test(sor)) {
      const belso: string[] = [];
      while (i < sorok.length && /^\s*>\s?/.test(sorok[i])) {
        belso.push(sorok[i].replace(/^\s*>\s?/, ""));
        i++;
      }
      ki.push({ t: "idezet", sorok: belso });
      continue;
    }
    if (sor.trim() === "") {
      // Az ÜRES SOR-t megtartjuk tagolásként (a felhasználó kérése) - a lista
      // elejéről/végéről lévő üres sorokat lentebb levágjuk.
      ki.push({ t: "ures" });
      i++;
      continue;
    }
    // Sima bekezdés: a szomszédos szöveg-sorok együtt, a sortörések megtartva.
    const bek: string[] = [];
    while (
      i < sorok.length &&
      sorok[i].trim() !== "" &&
      !/^(#{1,3})\s+/.test(sorok[i]) &&
      !/^\s*[-*]\s+/.test(sorok[i]) &&
      !/^\s*\d+[.)]\s+/.test(sorok[i]) &&
      !/^\s*>\s?/.test(sorok[i]) &&
      !sorok[i].trim().startsWith("```")
    ) {
      bek.push(sorok[i]);
      i++;
    }
    ki.push({ t: "p", sorok: bek });
  }
  // Az üres sorokat csak TAGOLÁSKÉNT (blokkok között) tartjuk meg: a lista
  // elejéről és végéről levágjuk őket (a felhasználó kérése: az eleji/végi
  // üres sor ne maradjon).
  while (ki.length && ki[0].t === "ures") ki.shift();
  while (ki.length && ki[ki.length - 1].t === "ures") ki.pop();
  return ki;
}

export function Markdown({ szoveg, mentions = false }: { szoveg: string; mentions?: boolean }) {
  const reszek = useMemo(() => blokkok(szoveg), [szoveg]);
  const H_STILUS: Record<number, string> = {
    1: "mt-2 mb-1 text-[1.25em] font-semibold text-text-primary",
    2: "mt-2 mb-1 text-[1.12em] font-semibold text-text-primary",
    3: "mt-1.5 mb-0.5 text-[1.04em] font-semibold text-text-primary",
  };
  return (
    <div className="break-words">
      {reszek.map((b, i) => {
        if (b.t === "h")
          return (
            <p key={i} className={H_STILUS[b.szint]}>
              <Inline szoveg={b.s} mentions={mentions} />
            </p>
          );
        if (b.t === "ul")
          return (
            <ul key={i} className="my-1 list-disc space-y-0.5 pl-5">
              {b.elemek.map((e, j) => (
                <li key={j}>
                  <Inline szoveg={e} mentions={mentions} />
                </li>
              ))}
            </ul>
          );
        if (b.t === "ol")
          return (
            <ol key={i} className="my-1 list-decimal space-y-0.5 pl-5">
              {b.elemek.map((e, j) => (
                <li key={j}>
                  <Inline szoveg={e} mentions={mentions} />
                </li>
              ))}
            </ol>
          );
        if (b.t === "kod")
          return (
            <pre key={i} className="my-1 overflow-x-auto rounded bg-surface-3 p-2 text-[0.92em] text-text-primary">
              {b.s}
            </pre>
          );
        if (b.t === "idezet")
          return (
            <blockquote key={i} className="my-1 border-l-2 border-border pl-2 text-text-secondary">
              <p className="whitespace-pre-line">
                <Inline szoveg={b.sorok.join("\n")} mentions={mentions} />
              </p>
            </blockquote>
          );
        if (b.t === "hr") return <hr key={i} className="my-2 border-border" />;
        // Tagoló üres sor: egy sornyi függőleges hézag (a felhasználó kérése).
        if (b.t === "ures") return <div key={i} aria-hidden className="h-[0.9em]" />;
        if (b.t === "p")
          return (
            <p key={i} className="my-0.5 whitespace-pre-line">
              <Inline szoveg={b.sorok.join("\n")} mentions={mentions} />
            </p>
          );
        return null;
      })}
    </div>
  );
}
