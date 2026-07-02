import type { ReactNode } from "react";

export type Column<T> = {
  header: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
};

export function DataTable<T extends { id: number }>({
  columns,
  rows,
  emptyText,
}: {
  columns: Column<T>[];
  rows: T[];
  emptyText: string;
}) {
  if (rows.length === 0) {
    return <p className="text-[13px] text-text-muted">{emptyText}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col.header}
                className={`whitespace-nowrap py-1.5 font-medium text-text-secondary ${
                  col.align === "right" ? "text-right" : "text-left"
                }`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-border last:border-0">
              {columns.map((col) => (
                <td
                  key={col.header}
                  className={`py-2 pr-4 ${col.align === "right" ? "text-right" : "text-left"}`}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
