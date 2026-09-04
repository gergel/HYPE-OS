"use client";

import { useState } from "react";
import { selectColor } from "@/lib/selectColor";

export type BoardCard = {
  id: number;
  href: string;
  title: string;
  subtitle?: string | null;
  badges: string[];
  /** A kártyán megjelenő további adatok (címke + érték párok) - hogy pontosan
   * melyik mezők, azt a "Nézet beállítása" panelen lehet megadni. */
  mezok?: { cimke: string; ertek: string }[];
  /** Kikre van kiosztva az anyag - a felhasználó kérése, hogy ez MINDIG
   * látsszon a kártyán, a "Nézet beállítása" választástól függetlenül. */
  kiosztva?: string[];
  /** Akiknek épp FUT az időmérője ezen az anyagon - élő jelzés a kártyán. */
  timerek?: string[];
};

export type BoardColumn = {
  key: string;
  label: string;
  cards: BoardCard[];
  /** Az oszlop halvány színe ("#rrggbb") - a fejléc és MINDEN benne lévő
   * kártya ezt a színt kapja, halványan (lásd Utómunka -> Nézet beállítása).
   * Üresen hagyva marad a semleges alapszín. */
  szin?: string | null;
};

/** Halvány háttér/keret a megadott színből. A színt nem tömören használjuk:
 * a kártyáknak olvashatónak kell maradniuk sötét és világos témában is, ezért
 * csak egy vékony réteget keverünk a felület színéhez (color-mix), a szöveg
 * pedig marad a téma saját színén. */
function halvany(szin: string | null | undefined, szazalek: number): string | undefined {
  if (!szin) return undefined;
  return `color-mix(in srgb, ${szin} ${szazalek}%, transparent)`;
}

const PAGE_SIZE = 10;

/** A húzáskor átadott adat típusa. Saját MIME-típus, hogy egy kívülről
 * behúzott fájl vagy szöveg ne indítsa el az áthelyezést. */
const HUZAS_TIPUS = "application/x-hype-anyag";

function BoardCardView({
  card,
  szin,
  huzhato,
  onMegnyitas,
}: {
  card: BoardCard;
  szin?: string | null;
  huzhato: boolean;
  /** Ha meg van adva, a kártya kattintásra EZT hívja a href-fel (felugró
   * ablakos megnyitás) a teljes oldalra navigálás helyett. */
  onMegnyitas?: (href: string) => void;
}) {
  return (
    <a
      href={card.href}
      onClick={
        onMegnyitas
          ? (e) => {
              // Ctrl/Cmd/középső katt: hadd nyíljon új lapon, ahogy szokott.
              if (e.ctrlKey || e.metaKey || e.button !== 0) return;
              e.preventDefault();
              onMegnyitas(card.href);
            }
          : undefined
      }
      draggable={huzhato}
      onDragStart={
        huzhato
          ? (e) => {
              e.dataTransfer.setData(HUZAS_TIPUS, String(card.id));
              // A böngésző alapból a LINKET vinné (URL-ként) - a saját
              // adatunk mellé a "move" jelzés adja a helyes egérkurzort.
              e.dataTransfer.effectAllowed = "move";
            }
          : undefined
      }
      style={szin ? { background: halvany(szin, 14), borderColor: halvany(szin, 38) } : undefined}
      className={`block rounded-[var(--radius)] border border-border bg-surface-3 p-2.5 text-[13px] hover:bg-surface-2 ${
        huzhato ? "cursor-grab active:cursor-grabbing" : ""
      }`}
    >
      {/* [overflow-wrap:anywhere]: a fájlnév-szerű címek (alulvonásokkal,
          pontokkal) nem tartalmaznak törhető szóközt, e nélkül kilógnának a
          kártyából. */}
      <p className="font-medium text-text-primary [overflow-wrap:anywhere]">{card.title}</p>
      {card.subtitle && <p className="mt-0.5 text-[12px] text-text-muted [overflow-wrap:anywhere]">{card.subtitle}</p>}
      {card.kiosztva && card.kiosztva.length > 0 && (
        <p className="mt-0.5 text-[12px] text-text-muted [overflow-wrap:anywhere]">
          Kiosztva: <span className="text-text-secondary">{card.kiosztva.join(", ")}</span>
        </p>
      )}
      {card.timerek && card.timerek.length > 0 && (
        <p className="mt-1 flex items-center gap-1.5 text-[12px] font-medium text-text-success">
          {/* Pulzáló pötty: messziről is látszik, hogy ITT épp megy a munka. */}
          <span aria-hidden className="relative flex h-2 w-2 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-current" />
          </span>
          Épp vágja: {card.timerek.join(", ")}
        </p>
      )}
      {card.mezok && card.mezok.length > 0 && (
        <dl className="mt-1 space-y-0.5 text-[12px]">
          {card.mezok.map((m) => (
            <div key={m.cimke} className="flex gap-1.5">
              <dt className="shrink-0 text-text-muted">{m.cimke}:</dt>
              <dd className="min-w-0 truncate text-text-secondary">{m.ertek}</dd>
            </div>
          ))}
        </dl>
      )}
      {card.badges.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {card.badges.map((b) => (
            <span
              key={b}
              className="rounded px-1.5 py-0.5 text-[11px]"
              style={{ background: selectColor(b).bg, color: selectColor(b).text }}
            >
              {b}
            </span>
          ))}
        </div>
      )}
    </a>
  );
}

/** Egyetlen oszlop - alapból legfeljebb 10 kártyát mutat, hogy egy nagy
 * csoportnál (pl. sok "Aktuális" állapotú anyag) ne kelljen egyszerre száz
 * sort görgetni - "további megjelenítése" nyitja ki a többit. */
function BoardColumnView({
  column,
  onAthelyezes,
  onMegnyitas,
}: {
  column: BoardColumn;
  /** Ha meg van adva, ide lehet kártyát HÚZNI: (kártya id, cél oszlop kulcsa). */
  onAthelyezes?: (cardId: number, celOszlop: string) => void;
  onMegnyitas?: (href: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [felette, setFelette] = useState(false);
  const visible = expanded ? column.cards : column.cards.slice(0, PAGE_SIZE);
  const remaining = column.cards.length - visible.length;
  const huzhato = onAthelyezes !== undefined;

  return (
    <div
      data-oszlop={column.key}
      onDragOver={
        huzhato
          ? (e) => {
              if (!e.dataTransfer.types.includes(HUZAS_TIPUS)) return;
              // preventDefault NÉLKÜL a böngésző nem enged ejteni.
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
              setFelette(true);
            }
          : undefined
      }
      onDragLeave={huzhato ? () => setFelette(false) : undefined}
      onDrop={
        huzhato
          ? (e) => {
              e.preventDefault();
              setFelette(false);
              const id = Number(e.dataTransfer.getData(HUZAS_TIPUS));
              if (Number.isFinite(id) && id > 0) onAthelyezes(id, column.key);
            }
          : undefined
      }
      style={column.szin ? { background: halvany(column.szin, 8), borderColor: halvany(column.szin, 45) } : undefined}
      className={`flex w-72 shrink-0 flex-col rounded-[var(--radius-lg)] border bg-surface-3 p-3 ${
        felette ? "border-text-accent" : "border-border"
      }`}
    >
      <p className="mb-2 flex items-center gap-1.5 text-[13px] font-medium text-text-primary">
        {column.szin && (
          <span
            aria-hidden
            style={{ background: column.szin }}
            className="inline-block h-2 w-2 shrink-0 rounded-full"
          />
        )}
        {column.label} <span className="text-text-muted">({column.cards.length})</span>
      </p>
      <div className="flex flex-col gap-2">
        {visible.length === 0 && <p className="text-[12px] text-text-muted italic">Üres.</p>}
        {visible.map((card) => (
          <BoardCardView key={card.id} card={card} szin={column.szin} huzhato={huzhato} onMegnyitas={onMegnyitas} />
        ))}
      </div>
      {remaining > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-2 text-left text-[12px] text-text-accent hover:underline"
        >
          {remaining} további megjelenítése
        </button>
      )}
    </div>
  );
}

/** Kanban-szerű táblanézet (állapot vagy vinyó szerint csoportosított
 * oszlopok) - a vágóknak, hogy ne a nyers adattáblát/lista-nézetet kelljen
 * böngészniük, hanem egyben lássák, mi hol tart. Ugyanez a komponens adja az
 * "Állapot szerint" és a "Vinyók szerint" nézetet is (lásd Utómunka oldal),
 * csak az oszlopok csoportosítási kulcsa más. */
export function DeliverableBoard({
  columns,
  onAthelyezes,
  onMegnyitas,
}: {
  columns: BoardColumn[];
  /** Ha meg van adva, a kártyák megfoghatók és másik oszlopba húzhatók -
   * ettől változik az anyag állapota (lásd UtomunkaContent). A vinyó szerinti
   * táblán szándékosan nincs: ott az oszlop nem egy állítható mező. */
  onAthelyezes?: (cardId: number, celOszlop: string) => void;
  /** Ha meg van adva, a kártya FELUGRÓ ABLAKBAN nyílik (a felhasználó
   * kérése), nem teljes oldalként - lásd UtomunkaContent + RecordDetailModal. */
  onMegnyitas?: (href: string) => void;
}) {
  if (columns.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs megjeleníthető anyag.</p>;
  }
  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {columns.map((col) => (
        <BoardColumnView key={col.key} column={col} onAthelyezes={onAthelyezes} onMegnyitas={onMegnyitas} />
      ))}
    </div>
  );
}
