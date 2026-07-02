import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";

export function PlaceholderPage({
  title,
  description,
  entities,
}: {
  title: string;
  description: string;
  entities: string[];
}) {
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={title}>
          <p className="mb-3 text-[13px] text-text-secondary">{description}</p>
          <div className="flex flex-wrap gap-2">
            {entities.map((entity) => (
              <span
                key={entity}
                className="rounded-[var(--radius)] bg-surface-3 px-2.5 py-1 text-xs text-text-secondary"
              >
                {entity}
              </span>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
