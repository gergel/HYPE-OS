"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type SearchHit = { id: number; label: string; sublabel: string | null; href: string };
type SearchGroup = { entity_type: string; title: string; hits: SearchHit[]; truncated: boolean };

const MIN_QUERY_LENGTH = 2;
const DEBOUNCE_MS = 250;

/** A TopBar jobb felső keresője: egyszerre keres MINDEN entitástípusban,
 * amihez a bejelentkezett felhasználónak van "view" joga (a szűrést a backend
 * végzi, lásd api/routes/search.py - a frontend sosem kap olyan találatot,
 * amit a felhasználó nem láthatna).
 *
 * A választ a hozzá tartozó keresőszöveggel EGYÜTT tároljuk, és csak akkor
 * mutatjuk, ha az még a jelenleg beírt szöveghez tartozik. Így egy lassabb,
 * korábbi kérés nem tudja felülírni egy frissebb találatait, és nem kell a
 * találatokat külön "törölni" gépelés közben (a betöltés-állapot is ebből
 * származtatható). */
export function GlobalSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<{ query: string; groups: SearchGroup[] }>({ query: "", groups: [] });
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const needle = query.trim();
  const longEnough = needle.length >= MIN_QUERY_LENGTH;
  const groups = result.query === needle ? result.groups : [];
  const loading = longEnough && result.query !== needle;

  const flatHits = groups.flatMap((group) => group.hits);
  const safeIndex = Math.min(activeIndex, Math.max(flatHits.length - 1, 0));
  // Előre kiszámolt sorszámok, hogy a rendereléskor ne kelljen számlálót írni.
  const indexOfHit = new Map(flatHits.map((hit, index) => [hit, index]));

  useEffect(() => {
    if (!longEnough) return;
    const timer = setTimeout(async () => {
      try {
        const res = await authFetch(`/api/v1/search?q=${encodeURIComponent(needle)}`);
        const data: SearchGroup[] = res.ok ? await res.json() : [];
        setResult({ query: needle, groups: data });
      } catch {
        setResult({ query: needle, groups: [] });
      }
      setActiveIndex(0);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [needle, longEnough]);

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  function go(hit: SearchHit) {
    setOpen(false);
    setQuery("");
    router.push(hit.href);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (flatHits.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (Math.min(i, flatHits.length - 1) + 1) % flatHits.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (Math.min(i, flatHits.length - 1) - 1 + flatHits.length) % flatHits.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(flatHits[safeIndex]);
    }
  }

  return (
    <div ref={containerRef} className="relative hidden md:block">
      <label className="flex items-center gap-2 rounded-full border border-border bg-surface-1 px-3.5 py-2 text-text-muted transition-colors focus-within:border-text-accent/40">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Keresés bármiben…"
          className="w-40 bg-transparent text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none lg:w-64"
        />
      </label>

      {open && longEnough && (
        <div className="absolute right-0 z-50 mt-2 max-h-[70vh] w-[380px] overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 py-2 shadow-lg">
          {loading && <p className="px-3 py-2 text-[13px] text-text-muted">Keresés…</p>}
          {!loading && groups.length === 0 && (
            <p className="px-3 py-2 text-[13px] text-text-muted">Nincs találat erre: „{needle}”</p>
          )}
          {groups.map((group) => (
            <div key={group.entity_type} className="mb-1 last:mb-0">
              <p className="px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">{group.title}</p>
              {group.hits.map((hit) => (
                <button
                  key={`${group.entity_type}-${hit.id}`}
                  type="button"
                  onClick={() => go(hit)}
                  onPointerEnter={() => setActiveIndex(indexOfHit.get(hit) ?? 0)}
                  className={`block w-full px-3 py-1.5 text-left transition-colors hover:bg-surface-3 ${
                    indexOfHit.get(hit) === safeIndex ? "bg-surface-3" : ""
                  }`}
                >
                  <span className="block truncate text-[13px] text-text-primary">{hit.label}</span>
                  {hit.sublabel && <span className="block truncate text-[11px] text-text-muted">{hit.sublabel}</span>}
                </button>
              ))}
              {group.truncated && (
                <p className="px-3 py-1 text-[11px] text-text-muted">További találatok is vannak – pontosíts.</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
