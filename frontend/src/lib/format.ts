import type { DatasetColumn, JsonValue } from "../api/generated";

export function formatValue(value: JsonValue | undefined, column?: DatasetColumn): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    const percent = column?.unit === "ratio";
    const displayed = percent ? value * 100 : value;
    const number = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(displayed);
    return percent || column?.unit === "%" || column?.unit === "percent" ? `${number}%` : number;
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "string") {
    if (column?.data_type === "datetime" || column?.semantic_type === "time_dimension") {
      const date = new Date(value);
      if (!Number.isNaN(date.valueOf())) {
        return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
      }
    }
    return value;
  }
  return JSON.stringify(value);
}

export function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("zh-CN", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
}

export function contentText(content: Record<string, unknown> | undefined): string {
  const value = content?.text;
  return typeof value === "string" ? value : "";
}
