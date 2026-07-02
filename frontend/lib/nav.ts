export type NavItem = {
  label: string;
  href: string;
};

export type NavGroup = {
  label: string | null;
  items: NavItem[];
};

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
    items: [{ label: "Crew", href: "/csapat" }],
  },
  {
    label: "Felszerelés",
    items: [{ label: "Eszközök", href: "/felszereles" }],
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
    items: [{ label: "Pénzügyek", href: "/penzugyek" }],
  },
  {
    label: null,
    items: [
      { label: "Kampányok", href: "/kampanyok" },
      { label: "Feladatok", href: "/feladatok" },
      { label: "AI Assistant", href: "/ai-assistant" },
      { label: "Beállítások", href: "/beallitasok" },
    ],
  },
];
