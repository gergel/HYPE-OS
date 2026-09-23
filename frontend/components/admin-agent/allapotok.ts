/** Lara feladat-állapotok magyar címkéi (a backend TaskState
 * értékeihez — lásd admin_agent/enums.py). Egy helyen, hogy a Munkasor és az
 * Áttekintés ugyanazt a szót mutassa. */
export const ALLAPOT_CIMKE: Record<string, string> = {
  new: "Új",
  analyzing: "Elemzés alatt",
  needs_info: "Adat hiányzik",
  proposal_ready: "Javaslat kész",
  awaiting_approval: "Jóváhagyásra vár",
  queued: "Sorban",
  executing: "Végrehajtás alatt",
  completed: "Lezárt",
  rejected: "Elutasítva",
  blocked: "Blokkolt",
  failed: "Hibás",
  cancelled: "Visszavonva",
};

/** A feladattípusok magyar címkéi (a backend TaskType értékeihez). */
export const TIPUS_CIMKE: Record<string, string> = {
  szamla: "Számla-felvezetés",
  email: "E-mail-válasz",
  tig: "TIG-előkészítés",
  szerzodes: "Szerződés-előkészítés",
  // Megszűnt típus (Lara utalással nem foglalkozik) — csak a régi, visszavont
  // feladatok felirata miatt marad.
  utalas: "Utalás (megszűnt)",
  egyeb: "Egyéb",
};

/** A felületről kézzel beállítható, MELLÉKHATÁS-MENTES állapotok (a backend
 * _KEZI_ALLAPOTOK párja — routes/admin_agent.py). Csak ezeket ajánljuk fel. */
export const KEZI_ALLAPOTOK = ["new", "needs_info", "blocked", "rejected", "cancelled"] as const;

/** A számla-célok (backend: bejovo_szamla.CEL_TIPUSOK) magyar címkéi. */
export const CEL_CIMKE: Record<string, string> = {
  kiadas_uj: "Új kiadás (projekthez)",
  kiadas_csatolas: "Csatolás meglévő kiadáshoz",
  kulsos_tig: "Meglévő külsős TIG",
  belsos_tig: "Meglévő belsős TIG",
  erezsi: "E-Rezsi",
  auto: "Autóköltség",
  kp: "KP-tétel bizonylata",
  mukodesi: "Általános működési költség (projekt nélkül)",
  kimeno: "Kimenő számla",
};
