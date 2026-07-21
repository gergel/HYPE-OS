import { MoreHorizontal } from "lucide-react";
import { Card } from "@/components/Card";
import type { DetailSection } from "@/components/DetailSections";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { ICON_MAP } from "@/components/icon-map";
import type { DetailTab as DbDetailTab, FieldTypeInfo, JsonRecord } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

/** Ugyanaz a szintetikus kulcs, mint a backend OTHER_TAB_KEY-je (lásd
 * backend/app/services/detail_tabs.py) - a szekció-szintű jogosultság-
 * ellenőrzés mindkét oldalon ugyanazt az "{page}:_other" összetett kulcsot
 * használja. */
const OTHER_TAB_KEY = "_other";
const ALWAYS_EXCLUDE_META = new Set(["id", "created_at", "updated_at"]);

/** A "{page}:{tabKey}" összetett kulcs csak akkor SZŰKÍTI a jogosultságot, ha
 * admin kifejezetten beállította azt (lásd Beállítások oldal,
 * UserAccessManager fülenkénti Látja/Szerkesztheti checkboxai) - ha nincs
 * ilyen összetett kulcs, a szekció a meglévő, oldal-szintű jogot örökli (nem
 * esik vissza tiltásra). Enélkül bármelyik munkatárs, akinek admin BÁRMELYIK
 * oldalhoz korlátozást állított be (pagePermissions !== null), az összes
 * részletnézet-szekción elveszítené a hozzáférést minden olyan szekcióhoz,
 * amihez admin még nem konfigurált explicit engedélyt - beleértve a bespoke
 * widgeteket (pl. eszközfoglalás, szerződés készítés) is, amik nem is mező-
 * szerkesztést jelentenek, hanem önálló akció-gombok egy adott szekción
 * belül. Ugyanez a logika a backend oldalon core/security.check_tab_action. */
function resolveTabPermissions(pagePermissions: Record<string, string[]> | null, page: string, tabKey: string): string[] | null {
  if (pagePermissions === null) return null;
  return pagePermissions[`${page}:${tabKey}`] ?? pagePermissions[page] ?? [];
}

function canView(pagePermissions: Record<string, string[]> | null, page: string, tabKey: string): boolean {
  const perms = resolveTabPermissions(pagePermissions, page, tabKey);
  return perms === null || perms.includes("view");
}

function canEdit(pagePermissions: Record<string, string[]> | null, page: string, tabKey: string): boolean {
  const perms = resolveTabPermissions(pagePermissions, page, tabKey);
  return perms === null || perms.includes("edit");
}

function intersectVisible(fields: string[], visibleFields: string[] | null): string[] {
  if (!visibleFields || visibleFields.length === 0) return fields;
  return fields.filter((f) => visibleFields.includes(f));
}

/** Admin által a Beállítások oldalon konfigurált (DB-driven) csoportosításból
 * + a mezőlistából + az egyéni mező-láthatóságból/jogosultságból építi fel a
 * <DetailSections> által elvárt szekció-listát - ez a közös alap MINDEN
 * generikus részletnézethez (lásd projektek/[id], csapat/[id], stb.). Minden
 * szekció egy önálló kártyaként jelenik meg EGYETLEN, görgethető oldalon
 * (nincs fül-navigáció) - admin csak azt szabja meg a Beállítások oldalon,
 * mely mezők kerüljenek melyik kártyába, nem azt, hogy külön kattintással
 * kelljen köztük váltani. Amit egyik admin által konfigurált csoport
 * field_keys listája sem tartalmaz, az automatikusan a szintetikus "Egyéb"
 * kártyára esik (lásd OTHER_TAB_KEY), hogy soha ne vesszen el mező azért,
 * mert admin még nem sorolta be sehova.
 *
 * A szekció-szintű jogosultság ("{page}:{tab_key}", lásd
 * core/security.check_tab_action) KÉTFÉLE módon hat: "view" hiánya esetén a
 * kártya EGYÁLTALÁN nem jelenik meg (nem csak olvashatatlan - a felhasználó
 * nem is tudja, hogy létezik), "edit" hiánya esetén megjelenik, de minden
 * mezője csak olvasható (readOnly EditableDetailGrid). pagePermissions=null
 * (a felhasználó nincs korlátozva oldal-szinten) -> minden szekció látszik és
 * szerkeszthető, változatlan viselkedés.
 *
 * extraTabs: bespoke, nem mező-alapú szekciók (pl. Projekt "Csapat &
 * Utómunka" kártyája M2mLinker/RelatedTable widgetekkel) - ezek a DB-driven
 * szekciókon TÚL, a lista végén jelennek meg, de ugyanúgy jogosultsághoz
 * kötve. */
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
  extraTabs?: DetailSection[];
  /** Bespoke widget(ek) egy adott DB-driven szekció mező-rácsa ELÉ szúrva
   * (pl. a Projekt "diszpo" szekcióján a diszpó-küldés gombok, "technika"
   * szekcióján az eszközfoglaló) - a szekció maga továbbra is admin által
   * átrendezhető marad (field_keys), csak a bespoke rész mindig ugyanahhoz a
   * tab_key-hez tapad. */
  prependContent?: Record<string, React.ReactNode>;
  /** Darabszám egy adott tab_key mező-rács kártyájának címéhez fűzve (pl. a
   * "technika" szekció foglalásainak száma) - csak megjelenítés, nem
   * befolyásolja a szekció létét/sorrendjét. */
  badges?: Record<string, number>;
}): DetailSection[] {
  const hiddenSet = new Set([...ALWAYS_EXCLUDE_META, ...alwaysHidden]);
  const assignedFieldSet = new Set(dbTabs.flatMap((t) => t.field_keys));
  const otherFields = Object.keys(record).filter((k) => !assignedFieldSet.has(k) && !hiddenSet.has(k));

  const sections: DetailSection[] = [];

  for (const t of dbTabs) {
    if (!canView(pagePermissions, page, t.tab_key)) continue;
    const fields = intersectVisible(
      t.field_keys.filter((f) => !hiddenSet.has(f)),
      visibleFields,
    );
    if (fields.length === 0 && !prependContent[t.tab_key]) continue;
    const Icon = t.icon ? ICON_MAP[t.icon] : undefined;
    const title = badges[t.tab_key] ? `${t.label} (${badges[t.tab_key]})` : t.label;
    sections.push({
      key: t.tab_key,
      label: t.label,
      content: (
        <>
          {prependContent[t.tab_key]}
          {fields.length > 0 && (
            <Card title={title} icon={Icon}>
              <EditableDetailGrid
                patchPath={patchPath}
                fields={toEditableDetailFields(record, [], fields, fieldTypes)}
                readOnly={!canEdit(pagePermissions, page, t.tab_key)}
                layout="boxed"
              />
            </Card>
          )}
        </>
      ),
    });
  }

  for (const extra of extraTabs) {
    if (!canView(pagePermissions, page, extra.key)) continue;
    sections.push(extra);
  }

  if (otherFields.length > 0 && canView(pagePermissions, page, OTHER_TAB_KEY)) {
    const fields = intersectVisible(otherFields, visibleFields);
    if (fields.length > 0) {
      sections.push({
        key: OTHER_TAB_KEY,
        label: "Egyéb",
        content: (
          <Card title="Egyéb" icon={MoreHorizontal}>
            <EditableDetailGrid
              patchPath={patchPath}
              fields={toEditableDetailFields(record, [], fields, fieldTypes)}
              readOnly={!canEdit(pagePermissions, page, OTHER_TAB_KEY)}
              layout="boxed"
            />
          </Card>
        ),
      });
    }
  }

  return sections;
}
