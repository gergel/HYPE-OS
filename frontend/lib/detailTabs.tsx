import { MoreHorizontal } from "lucide-react";
import { Card } from "@/components/Card";
import type { DetailTab } from "@/components/DetailTabs";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { ICON_MAP } from "@/components/icon-map";
import type { DetailTab as DbDetailTab, FieldTypeInfo, JsonRecord } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

/** Ugyanaz a szintetikus kulcs, mint a backend OTHER_TAB_KEY-je (lásd
 * backend/app/services/detail_tabs.py) - a fül-szintű jogosultság-ellenőrzés
 * mindkét oldalon ugyanazt az "{page}:_other" összetett kulcsot használja. */
const OTHER_TAB_KEY = "_other";
const ALWAYS_EXCLUDE_META = new Set(["id", "created_at", "updated_at"]);

function canView(pagePermissions: Record<string, string[]> | null, page: string, tabKey: string): boolean {
  if (pagePermissions === null) return true;
  return !!pagePermissions[`${page}:${tabKey}`]?.includes("view");
}

function canEdit(pagePermissions: Record<string, string[]> | null, page: string, tabKey: string): boolean {
  if (pagePermissions === null) return true;
  return !!pagePermissions[`${page}:${tabKey}`]?.includes("edit");
}

function intersectVisible(fields: string[], visibleFields: string[] | null): string[] {
  if (!visibleFields || visibleFields.length === 0) return fields;
  return fields.filter((f) => visibleFields.includes(f));
}

/** Admin által a Beállítások oldalon konfigurált (DB-driven) fülekből + a
 * mezőlistából + az egyéni mező-láthatóságból/fül-jogosultságból építi fel a
 * <DetailTabs> által elvárt tab-listát - ez a közös alap MINDEN generikus
 * részletnézethez (lásd projektek/[id], csapat/[id], stb.). Amit egyik admin
 * által konfigurált fül field_keys listája sem tartalmaz, az automatikusan a
 * szintetikus "Egyéb" fülre esik (lásd OTHER_TAB_KEY), hogy soha ne vesszen
 * el mező azért, mert admin még nem sorolta be sehova.
 *
 * A fül-szintű jogosultság ("{page}:{tab_key}", lásd
 * core/security.check_page_action) KÉTFÉLE módon hat: "view" hiánya esetén a
 * fül EGYÁLTALÁN nem jelenik meg (nem csak olvashatatlan - a felhasználó
 * nem is tudja, hogy létezik), "edit" hiánya esetén megjelenik, de minden
 * mezője csak olvasható (readOnly EditableDetailGrid). pagePermissions=null
 * (a felhasználó nincs korlátozva oldal-szinten) -> minden fül látszik és
 * szerkeszthető, változatlan viselkedés.
 *
 * extraTabs: bespoke, nem mező-alapú fülek (pl. Projekt "Csapat & Utómunka"
 * füle M2mLinker/RelatedTable widgetekkel) - ezek a DB-driven füleken TÚL,
 * a lista végén jelennek meg, de ugyanúgy fül-szintű jogosultsághoz kötve. */
export function buildFieldTabs({
  page,
  patchPath,
  record,
  dbTabs,
  visibleFields,
  fieldTypes,
  pagePermissions,
  alwaysHidden = [],
  extraTabs = [],
  prependContent = {},
  badges = {},
}: {
  page: string;
  patchPath: string;
  record: JsonRecord;
  dbTabs: DbDetailTab[];
  visibleFields: string[] | null;
  fieldTypes: Record<string, FieldTypeInfo>;
  pagePermissions: Record<string, string[]> | null;
  alwaysHidden?: string[];
  extraTabs?: (DetailTab & { editable?: boolean })[];
  /** Bespoke widget(ek) egy adott DB-driven fül mező-rácsa ELÉ szúrva (pl. a
   * Projekt "diszpo" fülén a diszpó-küldés gombok, "technika" fülén az
   * eszközfoglaló) - a fül maga továbbra is admin által átrendezhető marad
   * (field_keys), csak a bespoke rész mindig ugyanahhoz a tab_key-hez tapad. */
  prependContent?: Record<string, React.ReactNode>;
  /** Jelvény-szám egy adott tab_key-hez (pl. foglalások száma a "technika"
   * fülön) - a fül létét/sorrendjét nem befolyásolja, csak a badge-et adja. */
  badges?: Record<string, number>;
}): DetailTab[] {
  const hiddenSet = new Set([...ALWAYS_EXCLUDE_META, ...alwaysHidden]);
  const assignedFieldSet = new Set(dbTabs.flatMap((t) => t.field_keys));
  const otherFields = Object.keys(record).filter((k) => !assignedFieldSet.has(k) && !hiddenSet.has(k));

  const tabs: DetailTab[] = [];

  for (const t of dbTabs) {
    if (!canView(pagePermissions, page, t.tab_key)) continue;
    const fields = intersectVisible(
      t.field_keys.filter((f) => !hiddenSet.has(f)),
      visibleFields,
    );
    if (fields.length === 0 && !prependContent[t.tab_key]) continue;
    const Icon = t.icon ? ICON_MAP[t.icon] : undefined;
    tabs.push({
      key: t.tab_key,
      label: t.label,
      badge: badges[t.tab_key],
      content: (
        <>
          {prependContent[t.tab_key]}
          {fields.length > 0 && (
            <Card title={t.label} icon={Icon}>
              <EditableDetailGrid
                patchPath={patchPath}
                fields={toEditableDetailFields(record, [], fields, fieldTypes)}
                readOnly={!canEdit(pagePermissions, page, t.tab_key)}
              />
            </Card>
          )}
        </>
      ),
    });
  }

  for (const extra of extraTabs) {
    if (!canView(pagePermissions, page, extra.key)) continue;
    tabs.push(extra);
  }

  if (otherFields.length > 0 && canView(pagePermissions, page, OTHER_TAB_KEY)) {
    const fields = intersectVisible(otherFields, visibleFields);
    if (fields.length > 0) {
      tabs.push({
        key: OTHER_TAB_KEY,
        label: "Egyéb",
        content: (
          <Card title="Egyéb" icon={MoreHorizontal}>
            <EditableDetailGrid
              patchPath={patchPath}
              fields={toEditableDetailFields(record, [], fields, fieldTypes)}
              readOnly={!canEdit(pagePermissions, page, OTHER_TAB_KEY)}
            />
          </Card>
        ),
      });
    }
  }

  return tabs;
}
