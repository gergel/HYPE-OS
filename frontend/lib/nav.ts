export type NavItem = {
  label: string;
  href: string;
};

export type NavGroup = {
  label: string | null;
  items: NavItem[];
};

export type PagePermissionGroup = { page: string; label: string };

/** Egy jogosultsági "oldal" per topSegment (ugyanaz a granularitás, amit a
 * middleware.ts topSegment-alapú navigáció-szűrése és a backend
 * check_page_action-je használ) - egy csoporton belüli összes nav item
 * ugyanazt a topSegmentet osztja (pl. "Project Code-ok" és "Projektek" is
 * "/projektek"), ezért egyetlen checkbox-szal (a csoport címkéjével)
 * reprezentáljuk; a címke nélküli (önálló) itemek a saját címkéjüket adják.
 * Lásd UserAccessManager - a Beállítások oldal ez alapján sorolja fel a
 * per-oldal megtekintés/szerkesztés/létrehozás/törlés checkboxokat. */
export function pagePermissionGroups(): PagePermissionGroup[] {
  const seen = new Set<string>();
  const result: PagePermissionGroup[] = [];
  for (const group of navGroups) {
    for (const item of group.items) {
      const topSegment = "/" + item.href.split("/").filter(Boolean)[0];
      if (seen.has(topSegment)) continue;
      seen.add(topSegment);
      result.push({ page: topSegment, label: group.label ?? item.label });
    }
  }
  return result;
}

export const navGroups: NavGroup[] = [
  { label: null, items: [{ label: "Dashboard", href: "/dashboard" }] },
  {
    label: "Projektek",
    items: [
      { label: "Project Code-ok", href: "/projektek/project-kodok" },
      { label: "Projektek", href: "/projektek" },
    ],
  },
  {
    label: "Ügyfelek",
    items: [{ label: "Ügyfelek", href: "/ugyfelek" }],
  },
  {
    label: "Csapat",
    items: [
      { label: "Külsős", href: "/csapat" },
      { label: "Vágók", href: "/csapat/vagok" },
      { label: "Belsősök", href: "/csapat/belsosok" },
    ],
  },
  {
    label: "Felszerelés",
    items: [
      { label: "Eszközök", href: "/felszereles" },
      { label: "Leltározás", href: "/felszereles/leltarazas" },
    ],
  },
  {
    label: "Naptár / Diszpó",
    items: [{ label: "Diszpó", href: "/naptar" }],
  },
  {
    label: "Utómunka",
    items: [{ label: "Deliverable-ök", href: "/utomunka" }],
  },
  {
    label: "Média & Portál",
    items: [{ label: "Portál", href: "/media-portal" }],
  },
  {
    label: "Pénzügyek",
    items: [
      { label: "Pénzügyek", href: "/penzugyek" },
      { label: "Keretszerződések", href: "/penzugyek/keretszerzodesek" },
    ],
  },
  {
    label: null,
    items: [
      { label: "Alvállalkozók szerződése", href: "/alvallalkozoi-szerzodesek" },
      { label: "Teljesítési igazolások", href: "/teljesitesi-igazolasok" },
      { label: "Utókövetés", href: "/utokovetes" },
      { label: "Kampányok", href: "/kampanyok" },
      { label: "Feladatok", href: "/feladatok" },
      { label: "AI Assistant", href: "/ai-assistant" },
      { label: "Beállítások", href: "/beallitasok" },
    ],
  },
];
