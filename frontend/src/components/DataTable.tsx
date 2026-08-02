import type { DatasetRowsResponse } from "../api/generated";
import { formatValue } from "../lib/format";

function columnLabel(name: string, displayName?: string | null): string {
  if (displayName) return displayName;
  if (name === "record_count") return "记录数";
  if (name === "raw_metrics") return "原始指标";
  if (name === "metric_metadata") return "指标口径信息";
  const parts = name.split(".");
  return parts[parts.length - 1] ?? name;
}

export function DataTable({
  dataset,
  hiddenColumns = [],
}: {
  dataset: DatasetRowsResponse;
  hiddenColumns?: string[];
}) {
  const columns = dataset.columns.filter((column) => !hiddenColumns.includes(column.name));
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.name} scope="col">{columnLabel(column.name, column.display_name)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataset.rows.map((row) => (
            <tr key={row.row_id}>
              {columns.map((column) => (
                <td key={column.name}>{formatValue(row.values[column.name], column)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {dataset.rows.length === 0 ? <p className="empty-inline">当前范围没有数据。</p> : null}
      {dataset.total > dataset.rows.length ? (
        <p className="table-note">显示前 {dataset.rows.length} 行，共 {dataset.total} 行。可下载 CSV 查看全部。</p>
      ) : null}
    </div>
  );
}
