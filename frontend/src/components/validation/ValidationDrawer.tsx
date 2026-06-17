import type { ExportForAcResponse, ValidationResult } from "../../api/types";

type Props = {
  validation?: ValidationResult;
  exportResult?: ExportForAcResponse;
};

export function ValidationDrawer({ validation, exportResult }: Props) {
  if (!validation) return null;

  return (
    <section className="workspace-card validation-drawer">
      <div className="workspace-header">
        <div>
          <p className="eyebrow">Validation</p>
          <h2>{validation.ready_for_ac ? "Ready for AC" : "Needs Input"}</h2>
        </div>
        <span className={`small-pill ${validation.ready_for_ac ? "success" : "attention"}`}>
          {validation.blocking_issues.length} blockers
        </span>
      </div>
      {validation.blocking_issues.length ? (
        <ul className="issue-list">
          {validation.blocking_issues.map((issue) => (
            <li key={issue.field_name}>
              <strong>{issue.display_name}</strong>
              <span>{issue.message}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-state">No blocking issues. This use case can be exported for AC.</p>
      )}
      {exportResult && (
        <div className="export-box">
          <strong>AC Summary</strong>
          <p>{exportResult.semantic_summary}</p>
        </div>
      )}
    </section>
  );
}
