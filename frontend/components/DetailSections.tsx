"use client";

import { useRef, useState, type ReactNode } from "react";
import { GripVertical } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

export type DetailSection = { key: string; label: string; badge?: number; content: ReactNode };

/** A részletnézet TELJES tartalma egyetlen, görgethető oldalon, szekció-
 * kártyákra bontva - NINCS fül-navigáció (a felhasználó kifejezett kérése:
 * a korábbi fül-váltós elrendezés "kaotikusnak" hatott, a referenciakép
 * szerint minden szekció egyszerre látszik, csak vizuálisan van csoportosítva
 * kártyákba).
 *
 * A kártyák a fogantyúnál fogva HÚZÁSSAL átrendezhetők (ha canReorder), és a
 * mentett sorrend az adott entitástípus MINDEN rekordjánál érvényes - a
 * sorrend a backendben, entitástípusonként egy közös listában tárolódik (lásd
 * backend/app/models/detail_section_order.py), nem böngészőben, hogy tényleg
 * mindenhol és mindenkinél ugyanaz legyen.
 *
 * A húzás pointer-eseményekkel készült, NEM a HTML5 drag-and-drop API-val: a
 * natív DnD érintőképernyőn nem működik, és nem is automatizálható
 * megbízhatóan (így nem lett volna tesztelhető, hogy tényleg működik-e).
 *
 * CSS multi-column elrendezést használ (nem CSS grid) - ez ad "masonry"-szerű,
 * eltérő magasságú kártyákat oszlopokba rendező viselkedést natív CSS-sel,
 * JS-es masonry könyvtár nélkül (lásd referenciakép: a kártyák nem egyenlő
 * magasságú sorokban, hanem a legrövidebb oszlopba folyva rendeződnek). */
export function DetailSections({
  sections,
  entityType,
  canReorder = false,
}: {
  sections: DetailSection[];
  /** Enélkül nincs átrendezés (nincs hova menteni a sorrendet). */
  entityType?: string;
  canReorder?: boolean;
}) {
  // A sorrendet a szerver már a mentett beállítás szerint adja át; ez az
  // állapot csak a húzás utáni azonnali visszajelzéshez kell, újratöltés
  // nélkül.
  const [order, setOrder] = useState<string[] | null>(null);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [overKey, setOverKey] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const reorderable = canReorder && !!entityType;

  const ordered =
    order === null
      ? sections
      : [...sections]
          .map((s, i) => ({ s, i }))
          .sort((a, b) => {
            // Ami nincs a sorrendben (pl. újonnan hozzáadott kártya), az a
            // végére kerül, az eredeti sorrendjét megtartva.
            const ra = order.indexOf(a.s.key);
            const rb = order.indexOf(b.s.key);
            return (
              (ra === -1 ? Number.MAX_SAFE_INTEGER : ra) - (rb === -1 ? Number.MAX_SAFE_INTEGER : rb) || a.i - b.i
            );
          })
          .map(({ s }) => s);

  async function persist(keys: string[]) {
    if (!entityType) return;
    setSaving(true);
    try {
      await authFetch(`/api/v1/detail-tabs/${entityType}/section-order`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ section_keys: keys }),
      });
    } finally {
      setSaving(false);
    }
  }

  /** Melyik kártya van a megadott képernyő-pont alatt. */
  function sectionKeyAt(x: number, y: number): string | null {
    const el = document.elementFromPoint(x, y);
    const card = el?.closest("[data-section-key]");
    return card?.getAttribute("data-section-key") ?? null;
  }

  function startDrag(key: string, e: React.PointerEvent<HTMLDivElement>) {
    e.preventDefault();
    const handle = e.currentTarget;
    handle.setPointerCapture(e.pointerId);
    setDragKey(key);

    const onMove = (ev: PointerEvent) => {
      const target = sectionKeyAt(ev.clientX, ev.clientY);
      setOverKey(target && target !== key ? target : null);
    };
    const onUp = (ev: PointerEvent) => {
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
      handle.removeEventListener("pointercancel", onUp);

      const target = sectionKeyAt(ev.clientX, ev.clientY);
      setDragKey(null);
      setOverKey(null);
      if (!target || target === key) return;

      const keys = ordered.map((s) => s.key);
      const from = keys.indexOf(key);
      const to = keys.indexOf(target);
      if (from === -1 || to === -1) return;
      keys.splice(to, 0, ...keys.splice(from, 1));
      setOrder(keys);
      persist(keys);
    };

    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
    handle.addEventListener("pointercancel", onUp);
  }

  return (
    <div ref={containerRef}>
      {reorderable && (
        <p className="mb-2 text-[12px] text-text-muted">
          A kártyák a jobb felső sarkukban lévő fogantyúval átrendezhetők - a sorrend minden rekordnál érvényes lesz.
          {saving && <span className="ml-2 text-text-accent">Mentés…</span>}
        </p>
      )}
      <div className="columns-1 gap-5 lg:columns-2 [&>*]:mb-5 [&>*]:break-inside-avoid">
        {ordered.map((s) => (
          <div
            key={s.key}
            data-section-key={s.key}
            className={`relative ${dragKey === s.key ? "opacity-40" : ""} ${
              overKey === s.key ? "rounded-[var(--radius-lg)] shadow-[0_0_0_2px_var(--accent-solid)]" : ""
            }`}
          >
            {reorderable && (
              // Csak a fogantyú indít húzást, nem a teljes kártya - különben a
              // kártyán belüli szöveg kijelölése és a beviteli mezők
              // használata is húzásnak számítana.
              <div
                onPointerDown={(e) => startDrag(s.key, e)}
                title={`"${s.label}" áthelyezése`}
                aria-label={`"${s.label}" áthelyezése`}
                className="absolute right-2 top-2 z-10 cursor-grab touch-none rounded p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-primary active:cursor-grabbing"
              >
                <GripVertical size={15} aria-hidden />
              </div>
            )}
            {s.content}
          </div>
        ))}
      </div>
    </div>
  );
}
