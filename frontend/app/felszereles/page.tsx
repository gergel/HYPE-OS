import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function FelszerelesPage() {
  return (
    <PlaceholderPage
      title="Felszerelés"
      description="Eszközök és kivitel/visszahozás, a HYPE_Technika ütközés-detektáló mintája alapján. A backend API (GET/POST /api/v1/equipment, /api/v1/assignments) már működik és blokkolja az ütköző foglalásokat (409), a naptár-nézet UI a Fázis 1 munka része."
      entities={["Equipment", "Assignment"]}
    />
  );
}
