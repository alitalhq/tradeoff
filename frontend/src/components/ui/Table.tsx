import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Numbers are right aligned with tabular figures so columns line up. */
  numeric?: boolean;
}

export function Table<T>({ columns, rows, rowKey, caption, empty }: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  caption?: string;
  empty?: ReactNode;
}) {
  if (rows.length === 0 && empty) return <>{empty}</>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-rule text-left text-xs text-muted">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`px-2 py-2 font-medium ${c.numeric ? "text-right" : ""}`}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-rule/60 last:border-0 hover:bg-paper/60">
              {columns.map((c) => (
                <td key={c.key} className={`px-2 py-2 ${c.numeric ? "text-right tabular-nums" : ""}`}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
