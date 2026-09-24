"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Tudashalo as TudashaloAdat, TudashaloEl, TudashaloPont } from "@/lib/api";

/* ─────────────────────────────────────────────────────────────────────────────
 * Lara — TUDÁSHÁLÓ (kliens, canvas).
 *
 * A megtanult tudás „glóriája" (J.A.R.V.I.S.-szerű HUD): középen a mag, körülötte
 * a témakörök, kifelé a partnerek, a legkülső gyűrűn a projektkódok.
 *   • szín = témakör (validált, színtévesztés-biztos paletta a sötét felületen),
 *   • forma = a pont fajtája (partner ●, projektkód ■, számla-cél ▲, szabály ◆),
 *   • méret = a kapcsolatok súlya, vonalvastagság/fényerő = bizonyosság,
 *   • szaggatott vonal = még csak jelölt (nincs mögötte jóváhagyott tudás),
 *   • a HÁLÓ MÉRETE a látható kapcsolatok ÁTLAGOS BIZONYOSSÁGA: 100%-os
 *     bizonyosságnál tölti ki a teljes teret (lásd `haloArany`).
 * Két nézet: 3D gömb (egérrel forgatható, görgővel nagyítható, magától lassan
 * forog) és a sík glória. Teljes képernyőre is tehető.
 * A „Növekedés lejátszása" az első megjelenések szerint építi fel a hálót.
 * ────────────────────────────────────────────────────────────────────────── */

/** Témaszínek — `validate_palette.js --mode dark --surface #07090d --pairs all`:
 * minden ellenőrzés PASS (CVD ΔE 9,6, normál látás ΔE 17,0). Rögzített sorrend. */
const TEMA_SZIN: Record<string, string> = {
  szamla: "#a06604",
  tig: "#1795fa",
  szerzodes: "#944ec1",
  email: "#73a434",
  asszisztens: "#d9668e",
  // 6. szín: minden ellenőrzés PASS; a kontraszt WARN-t a feliratok + a
  // jelmagyarázat kezelik (a témát sosem csak a szín jelöli).
  projekt: "#5d10f8",
};
const TEMA_SORREND = ["szamla", "tig", "szerzodes", "email", "asszisztens", "projekt"] as const;
const TEMA_CIMKE: Record<string, string> = {
  szamla: "Számlák",
  tig: "TIG-ek",
  szerzodes: "Szerződések",
  email: "E-mailek",
  asszisztens: "AI asszisztens",
  projekt: "Projektek, rendszer",
};
const FAJTA_CIMKE: Record<string, string> = {
  core: "Mag",
  tema: "Témakör",
  partner: "Partner",
  kod: "Projektkód",
  cel: "Számla-cél",
  szabaly: "Szabály",
};
/** A projektkód témafüggetlen: semleges tinta (formája — négyzet — azonosítja). */
const SEMLEGES = "#c9d3de";
const HATTER = "#07090d";
const TINTA = "#e8ecf0";
const TINTA_2 = "#9aa4ae";
const HUD = "#a06604";

const LEJATSZAS_MS = 14000;

/** A HÁLÓ MÉRETE = a látható kapcsolatok átlagos BIZONYOSSÁGA: 100%-os
 * bizonyosságnál tölti ki a teljes teret. Hogy alacsony bizonyosságnál is
 * olvasható maradjon, a legkisebb méret `HALO_MIN` — e fölött egyenesen arányos
 * (21% → 45%, 60% → 72%, 100% → 100%). Lejátszás közben ez is változik.
 * A nagyítás (görgő / + −) csak a nézetet közelíti, a méret-arányt nem. */
const HALO_MIN = 0.3;
function haloArany(atlagBizonyossag: number | null): number {
  return HALO_MIN + (1 - HALO_MIN) * Math.max(0, Math.min(1, atlagBizonyossag ?? 0));
}
const NAP = 86400000;

type Pont = TudashaloPont & {
  x: number;
  y: number;
  /** 3D (gömb) elrendezés — egységgömbön belül. */
  gx: number;
  gy: number;
  gz: number;
  szin: string;
  tMs: number;
  /** Célsugár (normalizált) — a glória gyűrűi. */
  r0: number;
};
type El = TudashaloEl & { ia: number; ib: number; szin: string; tMs: number };

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967295;
}

function kever(hex: string, masik: string, t: number): string {
  const p = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [a, b] = [p(hex), p(masik)];
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(",")})`;
}

function rgba(hex: string, a: number): string {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${a})`;
}

type Szektorok = Record<string, { kozep: number; szel: number }>;

/** A témaszektorok a tartalmuk arányában osztoznak a glórián (a sűrű téma
 * nagyobb ívet kap, az üres is látszik egy keskeny szelettel). */
function szektorok(pontok: TudashaloPont[]): Szektorok {
  const db: Record<string, number> = {};
  for (const p of pontok)
    if (p.tema && (p.fajta === "partner" || p.fajta === "szabaly" || p.fajta === "cel")) db[p.tema] = (db[p.tema] ?? 0) + 1;
  const suly = TEMA_SORREND.map((t) => (db[t] ?? 0) + 3);
  const osszes = suly.reduce((a, b) => a + b, 0);
  const ki: Szektorok = {};
  let a = -Math.PI / 2 - ((suly[0] / osszes) * Math.PI * 2) / 2;
  TEMA_SORREND.forEach((t, i) => {
    const szel = (suly[i] / osszes) * Math.PI * 2;
    ki[t] = { kozep: a + szel / 2, szel };
    a += szel;
  });
  return ki;
}

/** Determinisztikus glória-elrendezés: mag → témák (r 0,26) → cél/szabály (≈0,4)
 * → partnerek (0,55–0,74, erősebb közelebb) → projektkódok (külső gyűrű ≈0,88),
 * majd rövid ütközés-feloldás a gyűrűkön belül. */
function elrendez(pontok: TudashaloPont[], elek: TudashaloEl[], sz: Szektorok): Pont[] {
  const SZEKTOR = (tema: string | null) => sz[tema ?? "szamla"]?.kozep ?? -Math.PI / 2;
  const maxSuly: Record<string, number> = {};
  for (const p of pontok) maxSuly[p.fajta] = Math.max(maxSuly[p.fajta] ?? 0, p.suly);
  const kimenet: Pont[] = pontok.map((p) => {
    const tMs = p.t ? Date.parse(p.t) : 0;
    const szin = p.fajta === "kod" ? SEMLEGES : p.fajta === "core" ? "#ffd49a" : TEMA_SZIN[p.tema ?? ""] ?? SEMLEGES;
    let r0 = 0;
    let szog = SZEKTOR(p.tema);
    const h = hash(p.id);
    const erosseg = maxSuly[p.fajta] ? Math.sqrt(p.suly / maxSuly[p.fajta]) : 0;
    if (p.fajta === "tema") r0 = 0.26;
    else if (p.fajta === "cel") {
      r0 = 0.4;
      szog += (h - 0.5) * 0.55;
    } else if (p.fajta === "szabaly") {
      r0 = 0.36 + h * 0.06;
      szog += (h - 0.5) * 0.9;
    } else if (p.fajta === "partner") {
      r0 = 0.75 - 0.2 * erosseg + (h - 0.5) * 0.05;
      szog += (h - 0.5) * 1.1;
    } else if (p.fajta === "kod") {
      r0 = 0.86 + (h - 0.5) * 0.08;
      szog = h * Math.PI * 2;
    }
    return { ...p, szin, tMs, r0, x: Math.cos(szog) * r0, y: Math.sin(szog) * r0, gx: 0, gy: 0, gz: 0 };
  });
  // A témaszektoron belül EGYENLETES szögeloszlás (a sűrű témánál sem torlódik):
  // partnerek, szabályok, számla-célok külön gyűrűn, váltakozó sugárral.
  for (const [fajta, alap, lepcso] of [
    ["partner", 0, 0.045],
    ["szabaly", 0.36, 0.03],
    ["cel", 0.42, 0.03],
  ] as const) {
    const csoport = new Map<string, Pont[]>();
    for (const p of kimenet) if (p.fajta === fajta) csoport.set(p.tema ?? "", [...(csoport.get(p.tema ?? "") ?? []), p]);
    for (const [tema, lista] of csoport) {
      lista.sort((a, b) => hash(a.id) - hash(b.id));
      lista.forEach((p, k) => {
        const szel = (sz[tema]?.szel ?? 1) * 0.86;
        const szog = SZEKTOR(tema) + ((k + 0.5) / lista.length - 0.5) * (fajta === "partner" ? szel : szel * 0.6);
        if (fajta !== "partner") p.r0 = alap;
        p.r0 += ((k % 3) - 1) * lepcso;
        p.x = Math.cos(szog) * p.r0;
        p.y = Math.sin(szog) * p.r0;
      });
    }
  }
  const index = new Map(kimenet.map((p, i) => [p.id, i]));
  // A projektkód a hozzá kötött partnerek irányába kerül (súlyozott kör-átlag).
  const irany = new Map<number, [number, number]>();
  for (const e of elek) {
    const [ia, ib] = [index.get(e.a), index.get(e.b)];
    if (ia === undefined || ib === undefined) continue;
    for (const [k, m] of [
      [ia, ib],
      [ib, ia],
    ] as const) {
      if (kimenet[k].fajta !== "kod" || kimenet[m].fajta === "kod") continue;
      const v = irany.get(k) ?? [0, 0];
      const d = Math.hypot(kimenet[m].x, kimenet[m].y) || 1;
      irany.set(k, [v[0] + (kimenet[m].x / d) * e.suly, v[1] + (kimenet[m].y / d) * e.suly]);
    }
  }
  for (const [k, [vx, vy]] of irany) {
    const szog = Math.atan2(vy, vx) + (hash(kimenet[k].id) - 0.5) * 0.25;
    kimenet[k].x = Math.cos(szog) * kimenet[k].r0;
    kimenet[k].y = Math.sin(szog) * kimenet[k].r0;
  }
  // Ütközés-feloldás (a gyűrűkön belül): taszítás + visszahúzás a célsugárra.
  const mozgo = kimenet.filter((p) => p.fajta !== "core" && p.fajta !== "tema");
  for (let it = 0; it < 90; it++) {
    for (let i = 0; i < mozgo.length; i++) {
      const a = mozgo[i];
      for (let j = i + 1; j < mozgo.length; j++) {
        const b = mozgo[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.hypot(dx, dy) || 1e-6;
        const min = 0.034;
        if (d < min) {
          const tol = ((min - d) / d) * 0.5;
          a.x -= dx * tol;
          a.y -= dy * tol;
          b.x += dx * tol;
          b.y += dy * tol;
        }
      }
    }
    for (const p of mozgo) {
      const d = Math.hypot(p.x, p.y) || 1e-6;
      const uj = d + (p.r0 - d) * 0.35;
      p.x = (p.x / d) * uj;
      p.y = (p.y / d) * uj;
    }
  }
  return kimenet;
}

/** A témák iránya a gömbön: egyenletesen körben, felváltva kissé fent és lent,
 * hogy a (függőleges tengely körüli) forgásnál mindegyik elöl is látsszon. */
function temaIrany(tema: string | null): [number, number, number] {
  const k = Math.max(0, TEMA_SORREND.indexOf((tema ?? "szamla") as (typeof TEMA_SORREND)[number]));
  const hossz = (k / TEMA_SORREND.length) * Math.PI * 2;
  const szel = k % 2 ? -0.42 : 0.42;
  return [Math.cos(szel) * Math.sin(hossz), Math.sin(szel), Math.cos(szel) * Math.cos(hossz)];
}

function norm(v: [number, number, number]): [number, number, number] {
  const d = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / d, v[1] / d, v[2] / d];
}

/** 3D gömb-elrendezés (determinisztikus): mag középen → témák (r 0,36) a saját
 * irányukban → szabály/cél (≈0,55) és partnerek (0,72–0,9, erősebb beljebb)
 * napraforgó-mintában a téma iránya körüli kúpban → projektkódok a külső héjon
 * (≈0,99), a hozzájuk kötött partnerek irányában. Végül 3D ütközés-feloldás. */
function elrendez3d(kimenet: Pont[], elek: TudashaloEl[]): void {
  const ARANY = Math.PI * (3 - Math.sqrt(5));
  const maxSuly: Record<string, number> = {};
  for (const p of kimenet) maxSuly[p.fajta] = Math.max(maxSuly[p.fajta] ?? 0, p.suly);
  const helyez = (p: Pont, irany: [number, number, number], r: number) => {
    const [x, y, z] = norm(irany);
    p.gx = x * r;
    p.gy = y * r;
    p.gz = z * r;
  };
  const csoport = new Map<string, Pont[]>();
  for (const p of kimenet) {
    if (p.fajta === "core") helyez(p, [0, 0, 1], 0);
    else if (p.fajta === "tema") helyez(p, temaIrany(p.tema), 0.36);
    else if (p.fajta === "partner" || p.fajta === "szabaly" || p.fajta === "cel") {
      const k = `${p.tema ?? "szamla"}|${p.fajta === "partner" ? "p" : "b"}`;
      csoport.set(k, [...(csoport.get(k) ?? []), p]);
    }
  }
  for (const [k, lista] of csoport) {
    const [tema, fajta] = k.split("|");
    const d = temaIrany(tema);
    // A téma irányára merőleges bázis.
    const seged: [number, number, number] = Math.abs(d[1]) > 0.9 ? [1, 0, 0] : [0, 1, 0];
    const u = norm([d[1] * seged[2] - d[2] * seged[1], d[2] * seged[0] - d[0] * seged[2], d[0] * seged[1] - d[1] * seged[0]]);
    const v = norm([d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]);
    lista.sort((a, b) => hash(a.id) - hash(b.id));
    const kup = fajta === "p" ? Math.min(1.15, 0.5 + 0.1 * Math.sqrt(lista.length)) : Math.min(0.6, 0.25 + 0.04 * lista.length);
    lista.forEach((p, i) => {
      const rho = kup * Math.sqrt((i + 0.5) / lista.length);
      const phi = i * ARANY;
      const irany: [number, number, number] = [0, 1, 2].map(
        (j) => d[j] * Math.cos(rho) + (u[j] * Math.cos(phi) + v[j] * Math.sin(phi)) * Math.sin(rho),
      ) as [number, number, number];
      const erosseg = maxSuly[p.fajta] ? Math.sqrt(p.suly / maxSuly[p.fajta]) : 0;
      const r = p.fajta === "partner" ? 0.9 - 0.18 * erosseg + (hash(p.id) - 0.5) * 0.05 : p.fajta === "cel" ? 0.58 : 0.54;
      helyez(p, irany, r);
    });
  }
  // Projektkód: a kötött pontok irányában a külső héjon.
  const index = new Map(kimenet.map((p, i) => [p.id, i]));
  const irany = new Map<number, [number, number, number]>();
  for (const e of elek) {
    const [ia, ib] = [index.get(e.a), index.get(e.b)];
    if (ia === undefined || ib === undefined) continue;
    for (const [k, m] of [
      [ia, ib],
      [ib, ia],
    ] as const) {
      if (kimenet[k].fajta !== "kod" || kimenet[m].fajta === "kod" || kimenet[m].fajta === "core") continue;
      const q = kimenet[m];
      const d = Math.hypot(q.gx, q.gy, q.gz) || 1;
      const w = irany.get(k) ?? [0, 0, 0];
      irany.set(k, [w[0] + (q.gx / d) * e.suly, w[1] + (q.gy / d) * e.suly, w[2] + (q.gz / d) * e.suly]);
    }
  }
  kimenet.forEach((p, i) => {
    if (p.fajta !== "kod") return;
    const h = hash(p.id);
    const w = irany.get(i);
    const vel: [number, number, number] = [hash(p.id + "x") - 0.5, hash(p.id + "y") - 0.5, hash(p.id + "z") - 0.5];
    const alap: [number, number, number] = w && Math.hypot(...w) > 1e-9 ? norm(w) : norm(vel);
    helyez(p, [alap[0] + vel[0] * 0.3, alap[1] + vel[1] * 0.3, alap[2] + vel[2] * 0.3], 0.99 + (h - 0.5) * 0.04);
  });
  // 3D ütközés-feloldás: taszítás + visszahúzás a saját héjra.
  const mozgo = kimenet.filter((p) => p.fajta !== "core" && p.fajta !== "tema");
  const cel = mozgo.map((p) => Math.hypot(p.gx, p.gy, p.gz));
  for (let it = 0; it < 60; it++) {
    for (let i = 0; i < mozgo.length; i++) {
      const a = mozgo[i];
      for (let j = i + 1; j < mozgo.length; j++) {
        const b = mozgo[j];
        const dx = b.gx - a.gx;
        const dy = b.gy - a.gy;
        const dz = b.gz - a.gz;
        const d = Math.hypot(dx, dy, dz) || 1e-6;
        const min = 0.07;
        if (d < min) {
          const tol = ((min - d) / d) * 0.5;
          a.gx -= dx * tol;
          a.gy -= dy * tol;
          a.gz -= dz * tol;
          b.gx += dx * tol;
          b.gy += dy * tol;
          b.gz += dz * tol;
        }
      }
    }
    mozgo.forEach((p, i) => {
      const d = Math.hypot(p.gx, p.gy, p.gz) || 1e-6;
      const uj = (d + (cel[i] - d) * 0.4) / d;
      p.gx *= uj;
      p.gy *= uj;
      p.gz *= uj;
    });
  }
}

function datum(ms: number): string {
  return new Date(ms).toLocaleDateString("hu-HU", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Europe/Budapest",
  });
}

function szazalek(v: number): string {
  return `${Math.round(v * 100)}%`;
}

export function Tudashalo({ adat }: { adat: TudashaloAdat }) {
  const tartoRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [meret, setMeret] = useState({ w: 960, h: 720 });
  const [rejtett, setRejtett] = useState<Set<string>>(new Set());
  const [kijelolt, setKijelolt] = useState<string | null>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const [tablazat, setTablazat] = useState(false);
  const [lejatszik, setLejatszik] = useState(false);

  const szekt = useMemo(() => szektorok(adat.pontok), [adat]);
  const pontok = useMemo(() => {
    const k = elrendez(adat.pontok, adat.elek, szekt);
    elrendez3d(k, adat.elek);
    return k;
  }, [adat, szekt]);
  const [nezet, setNezet] = useState<"3d" | "sik">("3d");
  const [teljesKepernyo, setTeljesKepernyo] = useState(false);
  const teljesRef = useRef<HTMLDivElement>(null);
  // Nézet-állapot a rajzoló huroknak (refben: az egér és a forgás nem renderel újra).
  const nezetRef = useRef(nezet);
  useLayoutEffect(() => {
    nezetRef.current = nezet;
  }, [nezet]);
  const zoomRef = useRef(1);
  const panRef = useRef({ x: 0, y: 0 });
  const forgasRef = useRef({ yaw: 0.6, pitch: -0.32 });
  const huzasRef = useRef<{ x: number; y: number; mozgott: boolean; pan: boolean } | null>(null);
  /** Az utolsó képkocka vetített pontjai (találatvizsgálathoz). */
  const vetitesRef = useRef<{ x: Float32Array; y: Float32Array; r: Float32Array; z: Float32Array }>({
    x: new Float32Array(0),
    y: new Float32Array(0),
    r: new Float32Array(0),
    z: new Float32Array(0),
  });
  const index = useMemo(() => new Map(pontok.map((p, i) => [p.id, i])), [pontok]);
  const elek = useMemo<El[]>(() => {
    const ki: El[] = [];
    for (const e of adat.elek) {
      const [ia, ib] = [index.get(e.a), index.get(e.b)];
      if (ia === undefined || ib === undefined) continue;
      const [pa, pb] = [pontok[ia], pontok[ib]];
      const tema = pa.fajta === "tema" ? pa.tema : pb.fajta === "tema" ? pb.tema : pa.fajta === "kod" ? pb.tema : pa.tema;
      ki.push({ ...e, ia, ib, szin: e.vaz ? "#ffd49a" : TEMA_SZIN[tema ?? ""] ?? SEMLEGES, tMs: e.t ? Date.parse(e.t) : 0 });
    }
    return ki;
  }, [adat, index, pontok]);

  const valodiElek = useMemo(() => elek.filter((e) => !e.vaz), [elek]);
  const tMin = useMemo(() => {
    const idok = valodiElek.map((e) => e.tMs).filter((t) => t > 0);
    const kezdet = Date.parse(adat.tanulas_kezdete);
    return Math.min(kezdet, ...(idok.length ? idok : [kezdet]));
  }, [valodiElek, adat.tanulas_kezdete]);
  // Az idősáv vége az adatból (determinisztikus — szerver és kliens ugyanazt rajzolja).
  // A legutolsó tudás ideje (tVeg) a KIÍRT dátum vége; a sáv egy nappal tovább
  // fut (tMax), hogy a végén minden kapcsolat kirajzolódjon — ezt a +1 napot
  // viszont nem írjuk ki (korábban emiatt mutatta a HUD mindig a holnapi dátumot).
  const tVeg = useMemo(() => {
    const utolso = adat.utolso_ido ? Date.parse(adat.utolso_ido) : 0;
    return Math.max(utolso, tMin);
  }, [adat.utolso_ido, tMin]);
  const tMax = tVeg + NAP;
  const [ido, setIdo] = useState(tMax);
  // A rajzoló hurok (rAF) a refekből olvas; a render után szinkronizáljuk.
  const idoRef = useRef(ido);
  useLayoutEffect(() => {
    idoRef.current = ido;
  }, [ido]);

  // Méretezés (a tároló szélességéhez, HiDPI-vel).
  useEffect(() => {
    const el = tartoRef.current;
    if (!el) return;
    const meretez = () => {
      const w = Math.max(320, Math.floor(el.clientWidth));
      const tk = !!document.fullscreenElement;
      const h = tk
        ? window.innerHeight - 24
        : w < 640
          ? Math.round(w * 1.05)
          : Math.round(Math.min(window.innerHeight * 0.84, Math.max(560, w * 0.72)));
      setMeret({ w, h });
    };
    const ro = new ResizeObserver(meretez);
    ro.observe(el);
    const fs = () => {
      setTeljesKepernyo(!!document.fullscreenElement);
      requestAnimationFrame(meretez);
    };
    document.addEventListener("fullscreenchange", fs);
    window.addEventListener("resize", meretez);
    return () => {
      ro.disconnect();
      document.removeEventListener("fullscreenchange", fs);
      window.removeEventListener("resize", meretez);
    };
  }, []);

  // Lejátszás: a tanulás kezdetétől máig ~14 mp alatt.
  useEffect(() => {
    if (!lejatszik) return;
    const start = performance.now();
    const t0 = tMin;
    let id = 0;
    const lep = (most: number) => {
      const k = Math.min(1, (most - start) / LEJATSZAS_MS);
      setIdo(t0 + (tMax - t0) * k);
      if (k < 1) id = requestAnimationFrame(lep);
      else setLejatszik(false);
    };
    id = requestAnimationFrame(lep);
    return () => cancelAnimationFrame(id);
  }, [lejatszik, tMin, tMax]);

  // Az aktuális időpontig látható tudás (a pontméret ebből nő).
  const lathato = useMemo(() => {
    const fok = new Float64Array(pontok.length);
    const elLathato = new Uint8Array(elek.length);
    const tLathato = (p: Pont) => !(p.tema && rejtett.has(p.tema) && p.fajta !== "core");
    elek.forEach((e, i) => {
      if (e.tMs > ido && !e.vaz) return;
      if (e.vaz && e.tMs > ido && e.tMs !== 0) return;
      const [pa, pb] = [pontok[e.ia], pontok[e.ib]];
      if (!tLathato(pa) || !tLathato(pb)) return;
      elLathato[i] = 1;
      fok[e.ia] += e.suly;
      fok[e.ib] += e.suly;
    });
    const pontLathato = new Uint8Array(pontok.length);
    pontok.forEach((p, i) => {
      if (p.fajta === "core" || (p.fajta === "tema" && tLathato(p))) pontLathato[i] = 1;
    });
    elek.forEach((e, i) => {
      if (elLathato[i]) {
        pontLathato[e.ia] = 1;
        pontLathato[e.ib] = 1;
      }
    });
    let kapcsolat = 0;
    let eros = 0;
    let jovahagyott = 0;
    let tapasztalt = 0;
    let bizSum = 0;
    elek.forEach((e, i) => {
      if (!elLathato[i] || e.vaz) return;
      kapcsolat++;
      bizSum += e.bizonyossag;
      if (e.bizonyossag >= 0.6) eros++;
      if (e.jovahagyott > 0) jovahagyott++;
      if ((e.tapasztalat ?? 0) > 0) tapasztalt++;
    });
    const pontSzam = pontok.filter((p, i) => pontLathato[i] && p.fajta !== "core" && p.fajta !== "tema").length;
    const atlag = kapcsolat ? bizSum / kapcsolat : null;
    const arany = haloArany(atlag);
    return { fok, elLathato, pontLathato, kapcsolat, eros, jovahagyott, tapasztalt, atlag, pontSzam, arany };
  }, [pontok, elek, ido, rejtett]);
  const lathatoRef = useRef(lathato);
  useLayoutEffect(() => {
    lathatoRef.current = lathato;
  }, [lathato]);
  // A háló AKTUÁLIS (animált) mérete: a rajzoló hurok vezeti a cél (arany) felé,
  // így betöltéskor és új tudásnál a háló láthatóan „kinő". A találatvizsgálat
  // is ezt olvassa, hogy a kattintás ott találjon, ahol a pont látszik.
  const haloRef = useRef(HALO_MIN * 0.8);

  const sugar = useCallback(
    (i: number, S: number) => {
      const p = pontok[i];
      const f = Math.sqrt(lathatoRef.current.fok[i]);
      const k = S / 420;
      // Lara magja is a tudással nő (kicsi mag → erős, nagy mag).
      if (p.fajta === "core") return (8 + 13 * haloRef.current) * k;
      if (p.fajta === "tema") return (8 + Math.min(10, f * 0.9)) * k;
      if (p.fajta === "partner") return (2.4 + Math.min(15, f * 2.3)) * k;
      if (p.fajta === "kod") return (2.2 + Math.min(11, f * 1.9)) * k;
      return (3.6 + Math.min(10, f * 1.6)) * k;
    },
    [pontok],
  );

  const szomszedok = useMemo(() => {
    if (!kijelolt) return null;
    const i = index.get(kijelolt);
    if (i === undefined) return null;
    const s = new Set<number>([i]);
    for (const e of elek) {
      if (e.ia === i) s.add(e.ib);
      if (e.ib === i) s.add(e.ia);
    }
    return s;
  }, [kijelolt, elek, index]);
  const allapotRef = useRef({ kijelolt: -1, szomszedok: null as Set<number> | null, hover: -1 });
  useLayoutEffect(() => {
    allapotRef.current = {
      kijelolt: kijelolt ? index.get(kijelolt) ?? -1 : -1,
      szomszedok,
      hover: hover ? index.get(hover.id) ?? -1 : -1,
    };
  }, [kijelolt, szomszedok, hover, index]);

  // ── Rajzoló hurok ──────────────────────────────────────────────────────────
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = meret.w * dpr;
    cv.height = meret.h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const csendes = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const Steljes = Math.min(meret.w, meret.h) / 2 - 34;
    const D = 3.2; // kamera-távolság (a gömb sugarának egységében)
    const n = pontok.length;
    const PX = new Float32Array(n);
    const PY = new Float32Array(n);
    const PZ = new Float32Array(n);
    const PF = new Float32Array(n);
    const PR = new Float32Array(n);
    type Reszecske = { el: number; k: number; seb: number };
    let reszecskek: Reszecske[] = [];
    let id = 0;
    const kezdes = performance.now();
    let elozo = kezdes;

    const alak = (p: Pont, x: number, y: number, r: number, kitoltes: string, korvonal: boolean) => {
      ctx.beginPath();
      if (p.fajta === "kod") ctx.rect(x - r, y - r, r * 2, r * 2);
      else if (p.fajta === "cel") {
        ctx.moveTo(x, y - r * 1.2);
        ctx.lineTo(x + r * 1.05, y + r * 0.7);
        ctx.lineTo(x - r * 1.05, y + r * 0.7);
        ctx.closePath();
      } else if (p.fajta === "szabaly") {
        ctx.moveTo(x, y - r * 1.25);
        ctx.lineTo(x + r * 1.25, y);
        ctx.lineTo(x, y + r * 1.25);
        ctx.lineTo(x - r * 1.25, y);
        ctx.closePath();
      } else ctx.arc(x, y, r, 0, Math.PI * 2);
      if (korvonal) {
        ctx.strokeStyle = kitoltes;
        ctx.lineWidth = 1.4;
        ctx.stroke();
      } else {
        ctx.fillStyle = kitoltes;
        ctx.fill();
      }
    };

    const rajzol = (most: number) => {
      const dt = Math.min(0.1, (most - elozo) / 1000);
      elozo = most;
      const fazis = csendes ? 0 : (most - kezdes) / 1000;
      const L = lathatoRef.current;
      const A = allapotRef.current;
      const T = idoRef.current;
      const harom = nezetRef.current === "3d";
      haloRef.current = csendes ? L.arany : haloRef.current + (L.arany - haloRef.current) * 0.05;
      const zoom = zoomRef.current;
      const S = Steljes * haloRef.current * zoom;
      const cx = meret.w / 2 + panRef.current.x;
      const cy = meret.h / 2 + panRef.current.y;
      // Magától lassan forog, amíg nem nyúlnak hozzá (húzás, rámutatás, kijelölés).
      if (harom && !csendes && !huzasRef.current && A.hover < 0 && A.kijelolt < 0) forgasRef.current.yaw += dt * 0.12;
      const { yaw, pitch } = forgasRef.current;
      const [cyw, syw, cp, sp] = [Math.cos(yaw), Math.sin(yaw), Math.cos(pitch), Math.sin(pitch)];
      /** 3D → képernyő: forgatás (függőleges tengely, majd billentés) + perspektíva. */
      const vetit = (x: number, y: number, z: number): [number, number, number, number] => {
        if (!harom) return [cx + x * S, cy + y * S, 0, 1];
        const x1 = x * cyw + z * syw;
        const z1 = -x * syw + z * cyw;
        const y2 = y * cp - z1 * sp;
        const z2 = y * sp + z1 * cp;
        const f = D / (D - z2);
        return [cx + x1 * S * f, cy - y2 * S * f, z2, f];
      };
      const melyseg = (z: number) => (harom ? 0.28 + 0.72 * Math.max(0, Math.min(1, (z + 1) / 2)) : 1);
      pontok.forEach((p, i) => {
        const [x, y, z, f] = harom ? vetit(p.gx, p.gy, p.gz) : vetit(p.x, p.y, 0);
        PX[i] = x;
        PY[i] = y;
        PZ[i] = z;
        PF[i] = f;
        PR[i] = sugar(i, Steljes) * f * Math.sqrt(zoom);
      });
      vetitesRef.current = { x: PX, y: PY, r: PR, z: PZ };

      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = HATTER;
      ctx.fillRect(0, 0, meret.w, meret.h);
      const vignetta = ctx.createRadialGradient(cx, cy, 0, cx, cy, S * 1.15);
      vignetta.addColorStop(0, "rgba(160,102,4,0.10)");
      vignetta.addColorStop(0.6, "rgba(160,102,4,0.03)");
      vignetta.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = vignetta;
      ctx.fillRect(0, 0, meret.w, meret.h);

      // A teljes (100%-os) méret halvány jelzése: ekkorára nő a háló 100% bizonyosságnál.
      ctx.beginPath();
      ctx.arc(cx, cy, Steljes * zoom * 1.035, 0, Math.PI * 2);
      ctx.setLineDash([2, 6]);
      ctx.strokeStyle = rgba(HUD, 0.22);
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);

      // HUD-gyűrűk, forgó ívek, skála.
      ctx.lineWidth = 1;
      for (const r of harom ? [1.02] : [0.26, 0.4, 0.62, 0.86, 0.985]) {
        ctx.beginPath();
        ctx.arc(cx, cy, r * S, 0, Math.PI * 2);
        ctx.strokeStyle = rgba(HUD, r > 0.9 ? 0.28 : 0.1);
        ctx.stroke();
      }
      for (const [r, seb, hossz, w] of [
        [0.955, 0.08, 1.2, 2],
        [0.93, -0.05, 0.6, 1],
        [0.31, 0.2, 0.9, 1.5],
        [0.2, -0.3, 1.6, 1],
      ] as const) {
        const rr = harom ? r * 1.1 : r;
        ctx.beginPath();
        const a0 = fazis * seb;
        ctx.arc(cx, cy, rr * S, a0, a0 + hossz);
        ctx.strokeStyle = rgba(HUD, 0.45);
        ctx.lineWidth = w;
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(cx, cy, rr * S, a0 + Math.PI, a0 + Math.PI + hossz * 0.4);
        ctx.stroke();
      }
      ctx.lineWidth = 1;
      const skala = harom ? 1.1 : 1.0;
      for (let i = 0; i < 180; i++) {
        const a = (i / 180) * Math.PI * 2;
        const hosszu = i % 15 === 0;
        const r1 = S * skala;
        const r2 = S * (skala + (hosszu ? 0.035 : 0.015));
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
        ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2);
        ctx.strokeStyle = rgba(HUD, hosszu ? 0.5 : 0.18);
        ctx.stroke();
      }
      if (harom) {
        // A gömb drótváza (délkörök, szélességi körök) — a hátsó fele halványabb.
        const vonal = (pts: [number, number, number][]) => {
          for (let k = 1; k < pts.length; k++) {
            const [x1, y1, z1] = vetit(...pts[k - 1]);
            const [x2, y2, z2] = vetit(...pts[k]);
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.strokeStyle = rgba(HUD, (z1 + z2) / 2 > 0 ? 0.16 : 0.05);
            ctx.stroke();
          }
        };
        const R = 1.03;
        for (let m = 0; m < 6; m++) {
          const a = (m / 6) * Math.PI;
          vonal(Array.from({ length: 49 }, (_, k) => {
            const t = (k / 48) * Math.PI * 2;
            return [R * Math.sin(t) * Math.cos(a), R * Math.cos(t), R * Math.sin(t) * Math.sin(a)] as [number, number, number];
          }));
        }
        for (const lat of [-0.9, -0.45, 0, 0.45, 0.9]) {
          vonal(Array.from({ length: 49 }, (_, k) => {
            const t = (k / 48) * Math.PI * 2;
            return [R * Math.cos(lat) * Math.cos(t), R * Math.sin(lat), R * Math.cos(lat) * Math.sin(t)] as [number, number, number];
          }));
        }
      } else {
        // Témaszektor-ívek a külső gyűrűn.
        TEMA_SORREND.forEach((t) => {
          if (rejtett.has(t)) return;
          const { kozep: k, szel } = szekt[t];
          ctx.beginPath();
          ctx.arc(cx, cy, S * 0.985, k - szel * 0.46, k + szel * 0.46);
          ctx.strokeStyle = rgba(TEMA_SZIN[t], 0.8);
          ctx.lineWidth = 3;
          ctx.stroke();
        });
      }

      // Kapcsolatok (additív fény), a középpont felé hajló ívvel.
      const kontroll = (pa: Pont, pb: Pont): [number, number] => {
        const [x, y] = harom
          ? vetit(((pa.gx + pb.gx) / 2) * 0.82, ((pa.gy + pb.gy) / 2) * 0.82, ((pa.gz + pb.gz) / 2) * 0.82)
          : vetit(((pa.x + pb.x) / 2) * 0.82, ((pa.y + pb.y) / 2) * 0.82, 0);
        return [x, y];
      };
      ctx.globalCompositeOperation = "lighter";
      const vanKijeloles = A.kijelolt >= 0 && A.szomszedok;
      elek.forEach((e, i) => {
        if (!L.elLathato[i]) return;
        const [pa, pb] = [pontok[e.ia], pontok[e.ib]];
        const erint = vanKijeloles && (e.ia === A.kijelolt || e.ib === A.kijelolt);
        const halvany = vanKijeloles && !erint;
        const c = e.vaz ? 0.55 : e.bizonyossag;
        const [qx, qy] = kontroll(pa, pb);
        const mely = melyseg((PZ[e.ia] + PZ[e.ib]) / 2);
        ctx.beginPath();
        ctx.moveTo(PX[e.ia], PY[e.ia]);
        ctx.quadraticCurveTo(qx, qy, PX[e.ib], PY[e.ib]);
        ctx.setLineDash(!e.vaz && e.jovahagyott === 0 && !e.tapasztalat ? [3, 4] : []);
        ctx.lineWidth = (e.vaz ? 1.4 : 0.5 + 3.4 * c) * (erint ? 1.4 : 1) * Math.sqrt(zoom) * (0.6 + 0.4 * mely);
        ctx.strokeStyle = rgba(e.szin.startsWith("#") ? e.szin : SEMLEGES, (0.08 + 0.55 * c) * mely * (halvany ? 0.12 : erint ? 1.6 : 1));
        ctx.stroke();
        // Újonnan megjelenő kapcsolat felvillanása lejátszás közben.
        if (!e.vaz && T - e.tMs >= 0 && T - e.tMs < 3 * NAP && T < tMax - NAP) {
          ctx.lineWidth += 2;
          ctx.strokeStyle = rgba("#ffffff", 0.25 * (1 - (T - e.tMs) / (3 * NAP)));
          ctx.stroke();
        }
      });
      ctx.setLineDash([]);

      // Fényimpulzusok az erős kapcsolatokon (a mag felé).
      if (!csendes) {
        if (reszecskek.length < 70) {
          const eros = elek.map((e, i) => i).filter((i) => L.elLathato[i] && (elek[i].vaz || elek[i].bizonyossag >= 0.45));
          if (eros.length && Math.random() < 0.6) reszecskek.push({ el: eros[Math.floor(Math.random() * eros.length)], k: 0, seb: 0.004 + Math.random() * 0.008 });
        }
        reszecskek = reszecskek.filter((r) => r.k < 1 && L.elLathato[r.el]);
        for (const r of reszecskek) {
          r.k += r.seb;
          const e = elek[r.el];
          const [pa, pb] = [pontok[e.ia], pontok[e.ib]];
          const hossz = (p: Pont) => (harom ? Math.hypot(p.gx, p.gy, p.gz) : Math.hypot(p.x, p.y));
          const kulso = hossz(pa) > hossz(pb);
          const [i1, i2] = kulso ? [e.ia, e.ib] : [e.ib, e.ia];
          const [qx, qy] = kontroll(pa, pb);
          const u = r.k;
          const x = (1 - u) * (1 - u) * PX[i1] + 2 * (1 - u) * u * qx + u * u * PX[i2];
          const y = (1 - u) * (1 - u) * PY[i1] + 2 * (1 - u) * u * qy + u * u * PY[i2];
          const mely = melyseg((PZ[i1] + PZ[i2]) / 2);
          const g = ctx.createRadialGradient(x, y, 0, x, y, 5);
          g.addColorStop(0, rgba("#ffffff", 0.9 * mely));
          g.addColorStop(0.4, rgba(e.szin.startsWith("#") ? e.szin : SEMLEGES, 0.6 * mely));
          g.addColorStop(1, "rgba(0,0,0,0)");
          ctx.fillStyle = g;
          ctx.fillRect(x - 5, y - 5, 10, 10);
        }
      }

      // Pontok: fényudvar + forma — hátulról előre (3D-ben a közelebbi van felül).
      const sorrend = pontok.map((_, i) => i);
      if (harom) sorrend.sort((a, b) => PZ[a] - PZ[b]);
      const cimkek: { i: number; r: number }[] = [];
      for (const i of sorrend) {
        const p = pontok[i];
        if (!L.pontLathato[i]) continue;
        const x = PX[i];
        const y = PY[i];
        let r = PR[i];
        if (p.fajta === "core") r *= 1 + (csendes ? 0 : Math.sin(fazis * 2) * 0.06);
        const halvany = vanKijeloles && !A.szomszedok!.has(i);
        const alfa = (halvany ? 0.18 : 1) * melyseg(PZ[i]);
        ctx.globalCompositeOperation = "lighter";
        const g = ctx.createRadialGradient(x, y, 0, x, y, r * (p.fajta === "core" ? 5 : 3.2));
        g.addColorStop(0, rgba(p.szin.startsWith("#") ? p.szin : SEMLEGES, 0.55 * alfa));
        g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(x, y, r * (p.fajta === "core" ? 5 : 3.2), 0, Math.PI * 2);
        ctx.fill();
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = alfa;
        if (p.fajta === "tema") {
          ctx.beginPath();
          ctx.arc(x, y, r * 1.45, 0, Math.PI * 2);
          ctx.strokeStyle = p.szin;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }
        const jelolt = p.fajta === "szabaly" && p.allapot !== "active";
        alak(p, x, y, r, p.fajta === "core" ? "#ffe8c4" : kever(p.szin, "#ffffff", 0.18), jelolt);
        if (p.fajta === "core" && !csendes) {
          for (let k = 0; k < 3; k++) {
            ctx.beginPath();
            const a0 = fazis * (0.8 + k * 0.5) * (k % 2 ? -1 : 1);
            ctx.arc(x, y, r * (1.6 + k * 0.45), a0, a0 + 1.9);
            ctx.strokeStyle = rgba("#ffd49a", 0.55 - k * 0.12);
            ctx.lineWidth = 1.2;
            ctx.stroke();
          }
        }
        // Új pont felvillanó gyűrűje lejátszás közben.
        if (p.tMs && T - p.tMs >= 0 && T - p.tMs < 4 * NAP && T < tMax - NAP) {
          const k = (T - p.tMs) / (4 * NAP);
          ctx.beginPath();
          ctx.arc(x, y, r + 14 * k, 0, Math.PI * 2);
          ctx.strokeStyle = rgba("#ffffff", 0.6 * (1 - k));
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }
        if (i === A.kijelolt || i === A.hover) {
          ctx.globalAlpha = 1;
          ctx.beginPath();
          ctx.arc(x, y, r + 5, 0, Math.PI * 2);
          ctx.strokeStyle = TINTA;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
        cimkek.push({ i, r });
      }

      // Feliratok: témakörök mindig; a legerősebb (3D-ben az elöl lévő) pontok és a kijelölés környéke.
      ctx.globalCompositeOperation = "source-over";
      const foglalt: [number, number, number, number][] = [];
      const felirat = (i: number, r: number, fo: boolean) => {
        const p = pontok[i];
        const szoveg = p.fajta === "tema" ? p.cimke.toUpperCase() : p.cimke.length > 28 ? p.cimke.slice(0, 27) + "…" : p.cimke;
        const meret = Math.round((fo ? 12 : 11) * Math.min(1.35, Math.sqrt(zoom)));
        ctx.font = `${fo ? 600 : 400} ${meret}px var(--font-geist-mono, ui-monospace), ui-monospace, monospace`;
        const w = ctx.measureText(szoveg).width;
        const x = PX[i];
        const y = PY[i];
        const dx = x - cx;
        const dy = y - cy;
        const d = Math.hypot(dx, dy);
        const kifele = d > 1 ? [dx / d, dy / d] : [0, 1];
        const lx = x + kifele[0] * (r + 8) - (kifele[0] < -0.2 ? w : kifele[0] > 0.2 ? 0 : w / 2);
        const ly = y + kifele[1] * (r + 8) + (kifele[1] > 0.2 ? meret - 1 : kifele[1] < -0.2 ? -2 : 4);
        const doboz: [number, number, number, number] = [lx - 2, ly - meret, w + 4, meret + 3];
        if (!fo && foglalt.some((f) => doboz[0] < f[0] + f[2] && doboz[0] + doboz[2] > f[0] && doboz[1] < f[1] + f[3] && doboz[1] + doboz[3] > f[1])) return;
        foglalt.push(doboz);
        ctx.globalAlpha = melyseg(PZ[i]);
        ctx.fillStyle = "rgba(7,9,13,0.72)";
        ctx.fillRect(doboz[0], doboz[1], doboz[2], doboz[3]);
        ctx.fillStyle = fo ? TINTA : TINTA_2;
        ctx.fillText(szoveg, lx, ly);
        ctx.globalAlpha = 1;
      };
      const elol = (i: number) => !harom || PZ[i] > -0.25;
      const rangsor = cimkek
        .filter(({ i }) => pontok[i].fajta !== "core" && pontok[i].fajta !== "tema")
        .sort((a, b) => L.fok[b.i] - L.fok[a.i]);
      cimkek.filter(({ i }) => pontok[i].fajta === "tema").forEach(({ i, r }) => felirat(i, r, true));
      if (vanKijeloles) {
        rangsor.filter(({ i }) => A.szomszedok!.has(i)).slice(0, 30).forEach(({ i, r }) => felirat(i, r, i === A.kijelolt));
      } else {
        rangsor.filter(({ i }) => elol(i)).slice(0, Math.round(14 + 10 * Math.min(2, zoom - 1))).forEach(({ i, r }) => felirat(i, r, false));
      }

      id = requestAnimationFrame(rajzol);
    };
    id = requestAnimationFrame(rajzol);
    return () => cancelAnimationFrame(id);
  }, [meret, pontok, elek, sugar, rejtett, tMax, tablazat, szekt]);

  // Görgő: nagyítás (nem görgeti az oldalt, amíg az egér a hálón van).
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const gorgo = (ev: WheelEvent) => {
      ev.preventDefault();
      zoomRef.current = Math.max(0.6, Math.min(4, zoomRef.current * Math.exp(-ev.deltaY * 0.0015)));
    };
    cv.addEventListener("wheel", gorgo, { passive: false });
    return () => cv.removeEventListener("wheel", gorgo);
  }, [tablazat]);

  // ── Egér: húzás = forgatás (3D) / mozgatás (sík, vagy Shift+húzás), kattintás = kijelölés ──
  const talalat = useCallback(
    (ex: number, ey: number): number => {
      const V = vetitesRef.current;
      let legjobb = -1;
      let tav = Infinity;
      let legjobbZ = -Infinity;
      pontok.forEach((p, i) => {
        if (!lathato.pontLathato[i] || i >= V.x.length) return;
        const d = Math.hypot(V.x[i] - ex, V.y[i] - ey);
        if (d < V.r[i] + 7 && (V.z[i] > legjobbZ + 0.05 || (Math.abs(V.z[i] - legjobbZ) <= 0.05 && d < tav))) {
          tav = d;
          legjobbZ = V.z[i];
          legjobb = i;
        }
      });
      return legjobb;
    },
    [pontok, lathato],
  );

  const onDown = (ev: React.PointerEvent<HTMLCanvasElement>) => {
    huzasRef.current = { x: ev.clientX, y: ev.clientY, mozgott: false, pan: ev.shiftKey || nezet === "sik" };
    ev.currentTarget.setPointerCapture(ev.pointerId);
  };
  const onMove = (ev: React.PointerEvent<HTMLCanvasElement>) => {
    const h = huzasRef.current;
    if (h) {
      const dx = ev.clientX - h.x;
      const dy = ev.clientY - h.y;
      if (!h.mozgott && Math.hypot(dx, dy) < 4) return;
      h.mozgott = true;
      h.x = ev.clientX;
      h.y = ev.clientY;
      if (h.pan) {
        panRef.current = { x: panRef.current.x + dx, y: panRef.current.y + dy };
      } else {
        const f = forgasRef.current;
        f.yaw += dx * 0.006;
        f.pitch = Math.max(-1.35, Math.min(1.35, f.pitch + dy * 0.006));
      }
      if (hover) setHover(null);
      return;
    }
    const r = ev.currentTarget.getBoundingClientRect();
    const i = talalat(ev.clientX - r.left, ev.clientY - r.top);
    setHover(i >= 0 ? { id: pontok[i].id, x: ev.clientX - r.left, y: ev.clientY - r.top } : null);
  };
  const onUp = (ev: React.PointerEvent<HTMLCanvasElement>) => {
    const h = huzasRef.current;
    huzasRef.current = null;
    if (!h || h.mozgott) return;
    const r = ev.currentTarget.getBoundingClientRect();
    const i = talalat(ev.clientX - r.left, ev.clientY - r.top);
    setKijelolt(i >= 0 && pontok[i].id !== kijelolt ? pontok[i].id : null);
  };
  const nagyit = (k: number) => {
    zoomRef.current = Math.max(0.6, Math.min(4, zoomRef.current * k));
  };
  const alaphelyzet = () => {
    zoomRef.current = 1;
    panRef.current = { x: 0, y: 0 };
    forgasRef.current = { yaw: 0.6, pitch: -0.32 };
  };
  const teljesValt = () => {
    const el = teljesRef.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.().catch(() => undefined);
  };
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setKijelolt(null);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  const pontAdat = (id: string | null) => {
    if (!id) return null;
    const i = index.get(id);
    if (i === undefined) return null;
    const p = pontok[i];
    const kapcs = elek
      .filter((e) => !e.vaz && (e.ia === i || e.ib === i))
      .map((e) => ({ masik: pontok[e.ia === i ? e.ib : e.ia], e }))
      .sort((a, b) => b.e.bizonyossag - a.e.bizonyossag);
    const jov = p.jovahagyott ?? 0;
    const jel = p.jelolt ?? 0;
    const atl = kapcs.length ? kapcs.reduce((s, k) => s + k.e.bizonyossag, 0) / kapcs.length : null;
    return { p, kapcs, jov, jel, atl };
  };
  const hoverAdat = hover ? pontAdat(hover.id) : null;
  const kijeloltAdat = pontAdat(kijelolt);
  const nincsTudas = valodiElek.length === 0;

  const tablaSorok = useMemo(
    () =>
      valodiElek
        .slice()
        .sort((a, b) => b.bizonyossag - a.bizonyossag)
        .slice(0, 80),
    [valodiElek],
  );

  return (
    <div className="flex flex-col gap-3">
      {/* Szűrők és idővezérlés egy sorban a háló fölött. */}
      <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-3 py-2">
        {TEMA_SORREND.map((t) => {
          const ki = rejtett.has(t);
          return (
            <button
              key={t}
              type="button"
              aria-pressed={!ki}
              onClick={() =>
                setRejtett((r) => {
                  const u = new Set(r);
                  if (u.has(t)) u.delete(t);
                  else u.add(t);
                  return u;
                })
              }
              className={`flex items-center gap-1.5 rounded-[var(--radius)] border px-2.5 py-1 text-[12px] ${
                ki ? "border-border text-text-muted line-through" : "border-border bg-surface-3 text-text-primary"
              }`}
            >
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: TEMA_SZIN[t], opacity: ki ? 0.35 : 1 }} />
              {TEMA_CIMKE[t]}
            </button>
          );
        })}
        <span className="mx-1 hidden h-5 w-px bg-border sm:inline-block" />
        <span className="text-[11.5px] text-text-muted">● partner · ■ projektkód · ▲ számla-cél · ◆ szabály · ‒ ‒ jelölt</span>
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => {
            if (lejatszik) setLejatszik(false);
            else {
              setIdo(tMin);
              setLejatszik(true);
            }
          }}
          className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[12.5px] font-medium text-text-accent"
        >
          {lejatszik ? "❚❚ Megállítás" : "▶ Növekedés lejátszása"}
        </button>
        {!tablazat && (
          <div className="flex items-center gap-1">
            <div className="flex overflow-hidden rounded-[var(--radius)] border border-border">
              {(["3d", "sik"] as const).map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-pressed={nezet === n}
                  onClick={() => setNezet(n)}
                  className={`px-2.5 py-1.5 text-[12.5px] ${nezet === n ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"}`}
                >
                  {n === "3d" ? "3D gömb" : "Sík"}
                </button>
              ))}
            </div>
            <button type="button" onClick={() => nagyit(1 / 1.25)} aria-label="Kicsinyítés" className="rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-3">
              −
            </button>
            <button type="button" onClick={() => nagyit(1.25)} aria-label="Nagyítás" className="rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-3">
              +
            </button>
            <button type="button" onClick={alaphelyzet} className="rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-3">
              Alaphelyzet
            </button>
            <button type="button" onClick={teljesValt} className="rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-3">
              {teljesKepernyo ? "Kilépés" : "Teljes képernyő"}
            </button>
          </div>
        )}
        <button
          type="button"
          onClick={() => setTablazat((v) => !v)}
          className="rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-3"
        >
          {tablazat ? "Háló" : "Táblázat"}
        </button>
      </div>

      <div
        ref={teljesRef}
        className={`flex flex-col gap-3 xl:flex-row ${teljesKepernyo ? "items-start overflow-auto p-3" : ""}`}
        style={teljesKepernyo ? { background: HATTER } : undefined}
      >
        <div ref={tartoRef} className="relative min-w-0 flex-1 overflow-hidden rounded-[var(--radius-lg)] border border-border" style={{ background: HATTER }}>
          {tablazat ? (
            <div className="max-h-[80vh] overflow-auto p-3">
              <table className="w-full border-collapse text-[12.5px]">
                <thead>
                  <tr className="border-b border-border text-left text-text-muted">
                    <th className="px-2 py-1.5 font-medium">Kapcsolat</th>
                    <th className="px-2 py-1.5 font-medium">Bizonyíték-erősség</th>
                    <th className="px-2 py-1.5 font-medium">Jóváhagyott / jelölt / tapasztalat</th>
                    <th className="px-2 py-1.5 font-medium">Első megjelenés</th>
                  </tr>
                </thead>
                <tbody>
                  {tablaSorok.map((e) => (
                    <tr key={`${e.a}|${e.b}`} className="border-b border-border/50">
                      <td className="px-2 py-1.5 text-text-primary">
                        {pontok[e.ia].cimke} ↔ {pontok[e.ib].cimke}
                      </td>
                      <td className="px-2 py-1.5 tabular-nums text-text-primary">{szazalek(e.bizonyossag)}</td>
                      <td className="px-2 py-1.5 tabular-nums text-text-secondary">
                        {e.jovahagyott} / {e.jelolt} / {e.tapasztalat ?? 0}
                      </td>
                      <td className="px-2 py-1.5 text-text-muted">{e.tMs ? datum(e.tMs) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <>
              <canvas
                ref={canvasRef}
                style={{
                  width: meret.w,
                  height: meret.h,
                  display: "block",
                  cursor: hover ? "pointer" : nezet === "3d" ? "grab" : "move",
                  touchAction: "none",
                }}
                onPointerDown={onDown}
                onPointerMove={onMove}
                onPointerUp={onUp}
                onPointerCancel={() => (huzasRef.current = null)}
                onPointerLeave={() => setHover(null)}
                role="img"
                aria-label={`Tudásháló: ${lathato.pontSzam} pont, ${lathato.kapcsolat} kapcsolat. A részletekért használd a Táblázat nézetet.`}
              />
              {/* HUD: a látható tudás számai (lejátszás közben nőnek). Mobilon a vászon alatt. */}
              <div className="pointer-events-none static px-3 pb-3 font-mono sm:absolute sm:left-3 sm:top-3 sm:p-0 text-[10.5px] uppercase tracking-[0.12em]" style={{ color: TINTA_2 }}>
                <p style={{ color: "#ffd49a" }}>Tudásháló // Lara</p>
                <p className="mt-0.5">{datum(Math.min(ido, tVeg))}</p>
                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
                  <HudSzam cimke="Pont" ertek={lathato.pontSzam} />
                  <HudSzam cimke="Kapcsolat" ertek={lathato.kapcsolat} />
                  <HudSzam cimke="Erős (≥60%)" ertek={lathato.eros} />
                  <HudSzam cimke="Jóváhagyott kapcs." ertek={lathato.jovahagyott} />
                  <HudSzam cimke="Tapasztalt kapcs." ertek={lathato.tapasztalt} />
                  <HudSzam cimke="Átl. bizonyíték-erősség" ertek={lathato.atlag === null ? "—" : szazalek(lathato.atlag)} />
                  <HudSzam cimke="Aktív szabály" ertek={adat.osszesites.aktiv_szabalyok} />
                  <HudSzam cimke="Méret (100% = teljes bizonyíték)" ertek={szazalek(lathato.arany)} />
                </div>
              </div>
              {nincsTudas && (
                <div className="pointer-events-none absolute inset-x-0 bottom-16 text-center font-mono text-[12px]" style={{ color: TINTA_2 }}>
                  Még nincs megtanult kapcsolat. Tanulás → „Visszatekintés” és „Visszajátszás”, majd hagyd jóvá a jelölteket a Tudástárban.
                </div>
              )}
              {/* Idősáv. */}
              <div className="static flex items-center gap-3 px-3 pb-3 font-mono text-[10.5px] sm:absolute sm:inset-x-3 sm:bottom-3 sm:p-0" style={{ color: TINTA_2 }}>
                <span>{datum(tMin)}</span>
                <input
                  type="range"
                  min={tMin}
                  max={tMax}
                  step={NAP / 4}
                  value={ido}
                  onChange={(e) => {
                    setLejatszik(false);
                    setIdo(Number(e.target.value));
                  }}
                  aria-label="Időpont: a tudás állapota eddig a napig"
                  className="flex-1 accent-[#a06604]"
                />
                <span>{datum(tVeg)}</span>
              </div>
              {hover && hoverAdat && (
                <div
                  className="pointer-events-none absolute z-10 max-w-[260px] rounded-[var(--radius)] border border-border bg-surface-2/95 px-2.5 py-2 text-[12px] shadow-lg"
                  style={{ left: Math.min(hover.x + 14, meret.w - 270), top: Math.max(8, hover.y - 10) }}
                >
                  <p className="font-medium text-text-primary">{hoverAdat.p.cimke}</p>
                  <p className="text-text-secondary">
                    {FAJTA_CIMKE[hoverAdat.p.fajta]}
                    {hoverAdat.p.tema ? ` · ${TEMA_CIMKE[hoverAdat.p.tema] ?? hoverAdat.p.tema}` : ""}
                  </p>
                  {hoverAdat.p.fajta !== "core" && (
                    <p className="mt-1 tabular-nums text-text-secondary">
                      {hoverAdat.kapcs.length} kapcsolat · {hoverAdat.jov} jóváhagyott · {hoverAdat.jel} jelölt
                      {hoverAdat.atl !== null ? ` · átl. ${szazalek(hoverAdat.atl)}` : ""}
                    </p>
                  )}
                  <p className="mt-1 text-[11px] text-text-muted">Kattints a részletekért</p>
                </div>
              )}
            </>
          )}
        </div>

        {kijeloltAdat && (
          <aside className="w-full shrink-0 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4 xl:w-[340px]">
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <p className="flex items-center gap-1.5 text-[11.5px] text-text-muted">
                  {kijeloltAdat.p.tema && (
                    <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: TEMA_SZIN[kijeloltAdat.p.tema] }} />
                  )}
                  {FAJTA_CIMKE[kijeloltAdat.p.fajta]}
                  {kijeloltAdat.p.tema ? ` · ${TEMA_CIMKE[kijeloltAdat.p.tema] ?? kijeloltAdat.p.tema}` : ""}
                  {kijeloltAdat.p.fajta === "szabaly" ? ` · ${kijeloltAdat.p.allapot === "active" ? "élesítve" : "jelölt"}` : ""}
                </p>
                <p className="text-[15px] font-medium text-text-primary">{kijeloltAdat.p.cimke}</p>
              </div>
              <button
                type="button"
                onClick={() => setKijelolt(null)}
                className="rounded-[var(--radius)] px-2 py-0.5 text-[13px] text-text-muted hover:bg-surface-3"
                aria-label="Bezárás"
              >
                ✕
              </button>
            </div>
            <div className="mb-3 grid grid-cols-3 gap-2 text-center">
              <MiniSzam cimke="Kapcsolat" ertek={String(kijeloltAdat.kapcs.length)} />
              <MiniSzam cimke="Jóváhagyott" ertek={String(kijeloltAdat.jov)} />
              <MiniSzam cimke="Átl. bizonyíték-erősség" ertek={kijeloltAdat.atl === null ? "—" : szazalek(kijeloltAdat.atl)} />
            </div>
            {kijeloltAdat.p.peldak.length > 0 && (
              <div className="mb-3">
                <p className="mb-1 text-[11.5px] text-text-muted">{kijeloltAdat.p.fajta === "szabaly" ? "A szabály" : "Jóváhagyott tudás"}</p>
                <ul className="flex flex-col gap-1.5">
                  {kijeloltAdat.p.peldak.map((t, k) => (
                    <li key={k} className="rounded-[var(--radius)] bg-surface-3 px-2 py-1.5 text-[12px] text-text-secondary">
                      {t}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="mb-1 text-[11.5px] text-text-muted">Kapcsolatai (bizonyíték-erősség szerint)</p>
            <ul className="flex max-h-[46vh] flex-col gap-1 overflow-auto">
              {kijeloltAdat.kapcs.map(({ masik, e }) => (
                <li key={masik.id}>
                  <button
                    type="button"
                    onClick={() => setKijelolt(masik.id)}
                    className="w-full rounded-[var(--radius)] px-1.5 py-1 text-left hover:bg-surface-3"
                  >
                    <span className="flex items-center justify-between gap-2 text-[12px]">
                      <span className="truncate text-text-primary">
                        {masik.cimke} <span className="text-text-muted">· {FAJTA_CIMKE[masik.fajta]}</span>
                      </span>
                      <span className="shrink-0 tabular-nums text-text-secondary">{szazalek(e.bizonyossag)}</span>
                    </span>
                    <span className="mt-1 block h-[3px] rounded-full bg-surface-4">
                      <span
                        className="block h-[3px] rounded-full"
                        style={{ width: `${Math.max(4, e.bizonyossag * 100)}%`, background: masik.tema ? TEMA_SZIN[masik.tema] : SEMLEGES }}
                      />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        )}
      </div>

      <p className="text-[11.5px] text-text-muted">
        3D: húzással forgatod, görgővel / + − gombbal nagyítasz, Shift+húzással mozgatod · a háló MÉRETE = az átlagos
        bizonyíték-erősség (100%-nál tölti ki a szaggatott külső kört) · Pontméret = a kapcsolatok súlya · vonalvastagság és
        fényerő = bizonyíték-erősség (jóváhagyott példa és élesített szabály
        erős, jelölt gyenge, régi Notion-korszakbeli tudás kisebb súlyú; a tapasztalat — a teljes adattörténet ismétlődő
        tényei és az adaton igazolt állítások — a mögötte álló esetek számával erősödik) · szaggatott = még csak jelölt. A
        háló csak rögzített, valós tudásból épül. A százalék a kapcsolat mögötti BIZONYÍTÉK erőssége, nem Lara
        feladat-pontossága — azt a „Tanulás és minőség” oldal méri, külön mérőszámokkal.
      </p>
    </div>
  );
}

function HudSzam({ cimke, ertek }: { cimke: string; ertek: number | string }) {
  return (
    <p>
      <span className="tabular-nums" style={{ color: TINTA }}>
        {ertek}
      </span>{" "}
      {cimke}
    </p>
  );
}

function MiniSzam({ cimke, ertek }: { cimke: string; ertek: string }) {
  return (
    <div className="rounded-[var(--radius)] bg-surface-3 px-1.5 py-1.5">
      <p className="text-[15px] font-medium tabular-nums text-text-primary">{ertek}</p>
      <p className="text-[10.5px] text-text-muted">{cimke}</p>
    </div>
  );
}
