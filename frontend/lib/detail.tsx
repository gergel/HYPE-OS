import type { ReactNode } from "react";
import { FieldTypeInfo, formatDate, formatHuf } from "@/lib/api";
import { Hivatkozas, LinkeltSzoveg } from "@/components/LinkeltSzoveg";
import { tartalmazLinket } from "@/lib/linkek";
import { humanizeKey } from "@/lib/mezoNev";

const HIDDEN_KEYS = new Set(["id", "created_at", "updated_at"]);

/** Szintetikus, csak megjelenítésre szánt (kliens-oldalon számolt) mezők,
 * amiket a hívó oldal illeszt a rekordba (pl. equipment.project_ids.length) -
 * ezek sosem PATCH-elhetők, még akkor sem, ha az értékük szám/string (amit a
 * classifyInput önmagában szerkeszthetőnek nézne). */
const FORCE_READONLY_KEYS = new Set(["forgatasok_szama"]);

const MONEY_KEY_PATTERN = /(netto|brutto|osszeg|koltseg|profit|bevetel|arfolyam|dij|ber)/i;
const DATE_VALUE_PATTERN = /^\d{4}-\d{2}-\d{2}/;
const URL_PATTERN = /^https?:\/\/\S+$/i;
const LONG_TEXT_LENGTH = 120;

export type DetailField = { label: string; value: ReactNode; wide?: boolean };

/** A mezőnév-humanizálás külön, függőség nélküli modulban van (lásd
 * lib/mezoNev.ts), hogy kliens-komponensek is használhassák - ez a modul a
 * lib/api.ts-en át a szerver-only "next/headers"-t is behúzza. Innen
 * továbbexportáljuk, hogy a meglévő importok változatlanok maradjanak. */
export { humanizeKey } from "@/lib/mezoNev";

function isLongText(value: string): boolean {
  return value.includes("\n") || value.length > LONG_TEXT_LENGTH;
}

function isUrl(value: string): boolean {
  return URL_PATTERN.test(value.trim());
}

function LinkValue({ href }: { href: string }) {
  return <Hivatkozas href={href} />;
}

function formatValue(key: string, value: unknown, hint?: FieldTypeInfo): { node: ReactNode; wide: boolean } {
  if (value === null || value === undefined || value === "") return { node: "–", wide: false };
  if (typeof value === "boolean") return { node: value ? "Igen" : "Nem", wide: false };
  if (Array.isArray(value)) {
    if (value.length === 0) return { node: "–", wide: false };
    if (value.every((v) => typeof v === "string" && isUrl(v))) {
      return {
        node: (
          <div className="flex flex-col gap-0.5">
            {value.map((v) => (
              <LinkValue key={v} href={v} />
            ))}
          </div>
        ),
        wide: value.length > 1,
      };
    }
    const joined = value.map((v) => (typeof v === "object" && v !== null ? JSON.stringify(v) : String(v))).join(", ");
    return { node: joined, wide: isLongText(joined) };
  }
  if (typeof value === "object") return { node: JSON.stringify(value), wide: false };
  if (typeof value === "number") {
    return { node: MONEY_KEY_PATTERN.test(key) ? formatHuf(value) : String(value), wide: false };
  }
  // A Time oszlopok "08:30:00" alakban jönnek - a másodperc itt zaj, a
  // felhasználó órát:percet vár (lásd Project.forgatas_kezdes_ido).
  if (typeof value === "string" && TIME_VALUE_PATTERN.test(value)) return { node: value.slice(0, 5), wide: false };
  if (typeof value === "string" && DATE_VALUE_PATTERN.test(value)) return { node: formatDate(value), wide: false };
  if (typeof value === "string" && isUrl(value)) return { node: <LinkValue href={value} />, wide: false };
  if (typeof value === "string" && (hint?.type === "multiline" || isLongText(value))) {
    // a Notion rich_text mezők (pl. diszpó szövege, brief, technika lista) sortöréseit
    // meg kell tartani, különben az egész szöveg egy sorba tördelődik a böngészőben.
    // A szövegbe írt linkek (vágás leírása, gyártás komment) kattinthatók.
    return {
      node: (
        <span className="whitespace-pre-line">
          <LinkeltSzoveg szoveg={value} />
        </span>
      ),
      wide: true,
    };
  }
  // Rövid szöveg is tartalmazhat linket ("nyers: https://..."), ilyenkor sem
  // kell kézzel kimásolni a címet.
  if (typeof value === "string" && tartalmazLinket(value)) return { node: <LinkeltSzoveg szoveg={value} />, wide: false };
  return { node: String(value), wide: false };
}

export type EditableInputType = "text" | "number" | "date" | "time" | "boolean" | "textarea" | "select";

export type EditableDetailField = DetailField & {
  key: string;
  editable: boolean;
  inputType: EditableInputType;
  rawValue: string | number | boolean | null;
  options?: string[];
  /** Select mezőnél: a listán kívüli, új érték is felvehető helyben. */
  allowNew?: boolean;
};

const DATE_KEY_PATTERN = /datum|date|hatarido|keltezes/i;
const TIME_VALUE_PATTERN = /^\d{2}:\d{2}(:\d{2})?$/;

/** Ha az érték null, a nyers JSON-ból önmagában nem derül ki, hogy a mező
 * valójában boolean/dátum/select-e (pl. egy még be nem pipált checkbox vagy
 * egy még be nem állított állapot) - ezért a backend field-típus hintjét
 * (lásd getFieldTypes) használjuk, ha elérhető, és csak ennek hiányában esünk
 * vissza a mezőnév-mintázatra. */
function classifyInput(
  key: string,
  value: unknown,
  fieldTypeHint?: FieldTypeInfo,
): { editable: boolean; inputType: EditableInputType; options?: string[]; allowNew?: boolean } {
  if (fieldTypeHint?.type === "select" && fieldTypeHint.options) {
    return {
      editable: true,
      inputType: "select",
      options: fieldTypeHint.options,
      allowNew: fieldTypeHint.allow_new,
    };
  }
  // Hosszú szövegnek szánt oszlop (Text) - MINDIG textarea, akkor is, ha épp
  // üres vagy rövid a tartalma. Enélkül az üres brief egysoros mezőként nyílt
  // meg, amiben az Enter mentett: pont az első bekezdést nem lehetett megírni.
  if (fieldTypeHint?.type === "multiline") return { editable: true, inputType: "textarea" };
  if (value === null || value === undefined) {
    if (fieldTypeHint?.type === "boolean") return { editable: true, inputType: "boolean" };
    if (fieldTypeHint?.type === "date" || fieldTypeHint?.type === "datetime") return { editable: true, inputType: "date" };
    if (fieldTypeHint?.type === "time") return { editable: true, inputType: "time" };
    if (fieldTypeHint?.type === "number") return { editable: true, inputType: "number" };
    return { editable: true, inputType: DATE_KEY_PATTERN.test(key) ? "date" : "text" };
  }
  if (typeof value === "boolean") return { editable: true, inputType: "boolean" };
  if (typeof value === "number") return { editable: true, inputType: "number" };
  if (typeof value === "string") {
    // A "time" mezőket (pl. forgatás kezdete/vége) csak a backend típus-hintje
    // alapján ismerjük fel - a "08:00:00" érték önmagában sima szöveg lenne.
    if (fieldTypeHint?.type === "time") return { editable: true, inputType: "time" };
    if (DATE_VALUE_PATTERN.test(value)) return { editable: true, inputType: "date" };
    if (isLongText(value)) return { editable: true, inputType: "textarea" };
    return { editable: true, inputType: "text" };
  }
  // objektum/tömb mezők (relation snapshotok, formula-eredmények) egyelőre
  // nem inline-szerkeszthetők - kockázatos lenne kézzel írt JSON-ra hagyatkozni,
  // a valódi kapcsolatokat (crew, eszközök, stb.) amúgy is dedikált UI kezeli
  return { editable: false, inputType: "text" };
}

/** Egy nyers rekord (bármelyik entitás, tetszőleges Notionből átjött mezőkkel)
 * EditableDetailGrid-kompatibilis mezőlistává alakítása - minden mezőhöz
 * megtartja a nyers értéket és egy inputType-hintet, hogy helyben
 * szerkeszthetővé tegye. onlyShow (ha meg van adva és nem üres) a Beállítások
 * oldalon konfigurált mező-láthatóság szűrője. */
export function toEditableDetailFields(
  record: Record<string, unknown>,
  hide: string[] = [],
  onlyShow?: string[] | null,
  fieldTypes?: Record<string, FieldTypeInfo> | null,
): EditableDetailField[] {
  const hideSet = new Set([...HIDDEN_KEYS, ...hide]);
  const onlyShowSet = onlyShow && onlyShow.length > 0 ? new Set(onlyShow) : null;
  return Object.entries(record)
    .filter(([key]) => !hideSet.has(key))
    .filter(([key]) => !onlyShowSet || onlyShowSet.has(key))
    .map(([key, value]) => {
      const { node, wide } = formatValue(key, value, fieldTypes?.[key]);
      const classified = classifyInput(key, value, fieldTypes?.[key]);
      const { inputType, options, allowNew } = classified;
      const editable = FORCE_READONLY_KEYS.has(key) ? false : classified.editable;
      const rawValue =
        typeof value === "string" || typeof value === "number" || typeof value === "boolean" || value === null
          ? value
          : null;
      return { key, label: humanizeKey(key), value: node, wide, editable, inputType, rawValue, options, allowNew };
    });
}
