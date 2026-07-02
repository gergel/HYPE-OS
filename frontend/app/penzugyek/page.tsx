import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function PenzugyekPage() {
  return (
    <PlaceholderPage
      title="Pénzügyek"
      description="Kiadások, bevételek, szerződések és a KP forgalom. A backend API (GET/POST /api/v1/expenses, /api/v1/revenues, /api/v1/kp-forgalom, /api/v1/contracts) már működik, az összesítő UI a Fázis 1 munka része."
      entities={["Expense", "Revenue", "Contract", "KpForgalom"]}
    />
  );
}
