import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function FeladatokPage() {
  return (
    <PlaceholderPage
      title="Feladatok"
      description="Egyesített TODO-lista (TEENDŐK + Ági to do list + HYPE TO-DO LIST). A backend API (GET/POST /api/v1/tasks) már működik, a lista UI a Fázis 1 munka része."
      entities={["Task"]}
    />
  );
}
