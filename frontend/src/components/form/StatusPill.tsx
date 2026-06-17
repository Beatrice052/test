import type { FieldStatus } from "../../api/types";

export function StatusPill({ status }: { status: FieldStatus }) {
  return <span className={`status-pill status-${status.toLowerCase().replaceAll(" ", "-")}`}>{status}</span>;
}
