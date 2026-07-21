import {
  Briefcase,
  Building2,
  Calendar,
  Clapperboard,
  DollarSign,
  FileText,
  Info,
  MessagesSquare,
  MoreHorizontal,
  Package,
  Send,
  Settings,
  Users,
  Wallet,
  Wrench,
  type LucideIcon,
} from "lucide-react";

/** A DetailTabConfig.icon adatbázis-oszlop (lásd backend/app/models/detail_tab.py)
 * egy lucide-react ikon NEVÉT tárolja stringként (nem magát a komponenst,
 * mert a Beállítások oldal admin fül-szerkesztője JSON-t ír/olvas) - ez a
 * térkép fordítja vissza a tényleges komponensre a részletnézeteken. Csak a
 * ténylegesen felkínált ikonokat kell itt felsorolni (lásd beallitasok
 * DetailTabEditor ikon-választója) - ismeretlen név esetén nincs ikon. */
export const ICON_MAP: Record<string, LucideIcon> = {
  Info,
  Send,
  Wrench,
  Wallet,
  MessagesSquare,
  Users,
  Clapperboard,
  FileText,
  MoreHorizontal,
  Calendar,
  DollarSign,
  Building2,
  Briefcase,
  Package,
  Settings,
};

export const ICON_NAMES = Object.keys(ICON_MAP);
