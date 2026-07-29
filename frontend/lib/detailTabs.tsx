import { Fragment } from "react";
import { MoreHorizontal } from "lucide-react";
import { Card } from "@/components/Card";
import type { DetailSection } from "@/components/DetailSections";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { ICON_MAP } from "@/components/icon-map";
import type { DetailTab as DbDetailTab, FieldTypeInfo, JsonRecord } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

/** Ugyanaz a szintetikus kulcs, mint a backend OTHER_TAB_KEY-je (lásd
 * backend/app/services/detail_tabs.py). */
const OTHER_TAB_KEY = "_other";
const ALWAYS_EXCLUDE_META = new Set(["id", "created_at", "updated_at"]);

/** Szintetikus "mezőkulcs" a Projekt oldal eszközfoglaló widgetjéhez - ezt a
 * kulcsot veszi fel a Beállítások oldal a Projekt entitás availableFields
 * listájába (lásd beallitasok/page.tsx VISIBILITY_ENTITIES), hogy a widget
 * ugyanúgy áthelyezhető legyen fülek között és ugyanúgy elrejthető
 * munkatársanként, mint egy valódi DB-mező (lásd buildFieldTabs widgets
 * paramétere). */
export const EQUIPMENT_WIDGET_FIELD_KEY = "__eszkozok_widget";

/** A forgatás időpontja (kezdő/záró dátum + óra) egyben szerkeszthető widget -
 * ugyanaz a mechanizmus, mint az eszköz-widgetnél: admin szabadon áthelyezheti
 * fülek közt, és munkatársanként elrejthető. Lásd ForgatasIdopontEditor. */
export const FORGATAS_IDOPONT_WIDGET_FIELD_KEY = "__forgatas_idopont_widget";

/** A szekciók MINDIG látszanak (nincs szekció-szintű elrejtés) - csak a
 * SZERKESZTÉS korlátozható admin által a "{page}:{tab_key}" összetett
 * kulccsal (lásd Beállítások oldal, UserAccessManager fülenkénti
 * Szerkesztheti checkboxa). Korábban a szekció LÁTHATÓSÁGA is ehhez a
 * kulcshoz volt kötve, de ez azt jelentette, hogy bármelyik munkatárs,
 * akinek admin BÁRMELYIK oldalhoz korlátozást állított be
 * (pagePermissions !== null), elveszítette volna a hozzáférést minden olyan
 * szekcióhoz, amihez admin még nem konfigurált explicit engedélyt -
 * beleértve a bespoke widgeteket (pl. eszközfoglalás, szerződés készítés)
 * is, amik nem is mező-szerkesztést jelentenek, hanem önálló akció-gombok.
 * Ez a felhasználó számára "eltűnt mezőkként" jelentkezett - ezért a
 * láthatóság mostantól sosem korlátozott, csak a szerkeszthetőség. */
function canEdit(pagePermissions: Record<string, string[]> | null, page: string, tabKey: string): boolean {
  if (pagePermissions === null) return true;
  const perms = pagePermissions[`${page}:${tabKey}`] ?? pagePermissions[page];
  return !!perms?.includes("edit");
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
 * core/security.check_tab_action) csak a szerkeszthetőséget korlátozza: ha
 * admin nem adott "edit" jogot egy adott szekcióhoz, az megjelenik, de minden
 * mezője csak olvasható (readOnly EditableDetailGrid) - a kártya maga sosem
 * tűnik el. pagePermissions=null (a felhasználó nincs korlátozva
 * oldal-szinten) -> minden szekció szerkeszthető, változatlan viselkedés.
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
  widgets = {},
  sectionOrder = [],
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
  /** Bespoke widget(ek), amik szintetikus "mezőkulcs"-ként viselkednek (a
   * kulcsot a hívó oldal veszi fel a Beállítások VISIBILITY_ENTITIES
   * availableFields listájába, lásd beallitasok/page.tsx) - admin a
   * Részletnézet fülek szerkesztőjében ugyanúgy áthelyezheti egyik fülről a
   * másikra, mint egy valódi DB-mezőt, és ugyanúgy elrejthető
   * munkatársanként a mező-láthatóság beállítással. Eltérően a fenti
   * prependContent-től (ami egy FIX, admin által törölhető/átnevezhető
   * tab_key-hez tapad, és eltűnik, ha az a fül megszűnik), ez sosem tűnik
   * el: ha admin nem rendeli egyik fülhöz sem, a szintetikus "Egyéb" fülre
   * esik, pont úgy, mint egy hozzá nem rendelt mező. */
  widgets?: Record<string, React.ReactNode>;
  /** A felhasználó által húzással beállított kártya-sorrend (lásd
   * DetailSections + backend detail_section_orders) - itt, szerver oldalon
   * alkalmazzuk, hogy már az ELSŐ renderelés a mentett sorrendben történjen,
   * ne ugorjanak át a kártyák betöltés után. Ami nincs benne a mentett
   * listában, az a végére kerül, a természetes sorrendjében. */
  sectionOrder?: string[];
}): DetailSection[] {
  const hiddenSet = new Set([...ALWAYS_EXCLUDE_META, ...alwaysHidden]);
  const widgetKeys = Object.keys(widgets);
  const assignedFieldSet = new Set(dbTabs.flatMap((t) => t.field_keys));
  const otherFields = Object.keys(record).filter((k) => !assignedFieldSet.has(k) && !hiddenSet.has(k));
  const otherWidgetKeys = widgetKeys.filter((k) => !assignedFieldSet.has(k));

  const sections: DetailSection[] = [];

  for (const t of dbTabs) {
    const fields = intersectVisible(
      t.field_keys.filter((f) => !hiddenSet.has(f) && !widgetKeys.includes(f)),
      visibleFields,
    );
    const tabWidgetKeys = intersectVisible(
      t.field_keys.filter((f) => widgetKeys.includes(f)),
      visibleFields,
    );
    if (fields.length === 0 && tabWidgetKeys.length === 0 && !prependContent[t.tab_key]) continue;
    const Icon = t.icon ? ICON_MAP[t.icon] : undefined;
    const title = badges[t.tab_key] ? `${t.label} (${badges[t.tab_key]})` : t.label;
    sections.push({
      key: t.tab_key,
      label: t.label,
      content: (
        <>
          {prependContent[t.tab_key]}
          {tabWidgetKeys.map((k) => (
            <Fragment key={k}>{widgets[k]}</Fragment>
          ))}
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

  sections.push(...extraTabs);

  const visibleOtherFields = intersectVisible(otherFields, visibleFields);
  const visibleOtherWidgetKeys = intersectVisible(otherWidgetKeys, visibleFields);
  if (visibleOtherFields.length > 0 || visibleOtherWidgetKeys.length > 0) {
    sections.push({
      key: OTHER_TAB_KEY,
      label: "Egyéb",
      content: (
        <>
          {visibleOtherWidgetKeys.map((k) => (
            <Fragment key={k}>{widgets[k]}</Fragment>
          ))}
          {visibleOtherFields.length > 0 && (
            <Card title="Egyéb" icon={MoreHorizontal}>
              <EditableDetailGrid
                patchPath={patchPath}
                fields={toEditableDetailFields(record, [], visibleOtherFields, fieldTypes)}
                readOnly={!canEdit(pagePermissions, page, OTHER_TAB_KEY)}
                layout="boxed"
              />
            </Card>
          )}
        </>
      ),
    });
  }

  if (sectionOrder.length > 0) {
    const rank = (key: string) => {
      const i = sectionOrder.indexOf(key);
      return i === -1 ? Number.MAX_SAFE_INTEGER : i;
    };
    // Stabil rendezés: az azonos rangúak (mind a -1-esek) megtartják az
    // eredeti egymáshoz képesti sorrendjüket.
    return sections
      .map((s, i) => ({ s, i }))
      .sort((a, b) => rank(a.s.key) - rank(b.s.key) || a.i - b.i)
      .map(({ s }) => s);
  }

  return sections;
}
