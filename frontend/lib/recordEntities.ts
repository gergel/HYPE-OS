import { ENTITY_PATHS } from "@/lib/api";

/** Azok az entitások, amiknek NINCS saját részletnézet-oldaluk (a Díjak, a
 * munkaidő-elszámolások, a visszajelzések, az eszközfoglalások és a
 * kapcsolattartók csak kapcsolódó táblákban jelennek meg máshol) - ezeket a
 * generikus /rekord/[entity]/[id] oldal nyitja meg, ugyanazzal a
 * szerkeszthető mező-ráccsal, mint bármelyik "rendes" adatlap. Enélkül ezek a
 * rekordok sehol nem lettek volna szerkeszthetők.
 *
 * `page`: melyik oldal jogosultsága szabályozza a szerkesztést (a rekord
 * "gazdája") - lásd getMyPagePermissions / buildFieldTabs.
 * `entityType`: a mező-láthatóság és a mezőtípusok kulcsa a backend felé
 * (lásd getVisibleFields / getFieldTypes / getDetailTabs). */
export const RECORD_ENTITIES = {
  rate: { path: ENTITY_PATHS.rate, entityType: "rate", page: "/csapat", label: "Díj" },
  timesheet: {
    path: ENTITY_PATHS.timesheet,
    entityType: "timesheet",
    page: "/utomunka",
    label: "Munkaidő-elszámolás",
  },
  feedback: { path: ENTITY_PATHS.feedback, entityType: "feedback", page: "/utomunka", label: "Visszajelzés" },
  assignment: {
    path: ENTITY_PATHS.assignment,
    entityType: "assignment",
    page: "/felszereles",
    label: "Eszközfoglalás",
  },
  contact: { path: ENTITY_PATHS.contact, entityType: "contact", page: "/ugyfelek", label: "Kapcsolattartó" },
} as const;

export type RecordEntityKey = keyof typeof RECORD_ENTITIES;

export function recordEntity(key: string) {
  return (RECORD_ENTITIES as Record<string, (typeof RECORD_ENTITIES)[RecordEntityKey] | undefined>)[key];
}

/** A generikus adatlap útvonala - ugyanez az /embed előtaggal a felugró
 * ablakban megnyíló változat (lásd RecordDetailModal). */
export function recordHref(key: RecordEntityKey, id: number | string): string {
  return `/rekord/${key}/${id}`;
}
