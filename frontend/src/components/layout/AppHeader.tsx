import type { IntakeMode, ValidationResult } from "../../api/types";

type Props = {
  intakeId: string;
  mode: IntakeMode;
  validation?: ValidationResult;
  loading: boolean;
  onValidate: () => void;
  onExport: () => void;
};

export function AppHeader({ intakeId, mode, validation, loading, onValidate, onExport }: Props) {
  const status = validation?.ready_for_ac ? "Ready for AC" : validation?.blocking_issues.length ? "Needs Input" : "Draft";

  return (
    <header className="app-header">
      <div>
        <p className="eyebrow">Requirement Intake</p>
        <h1>{intakeId}</h1>
      </div>
      <div className="header-meta">
        <span className="meta-chip">{mode.replace("_", " ")}</span>
        <span className={`meta-chip status-${status.toLowerCase().replaceAll(" ", "-")}`}>{status}</span>
      </div>
      <div className="header-actions">
        <button className="button ghost" type="button">Save Draft</button>
        <button className="button secondary" type="button" onClick={onValidate} disabled={loading}>Validate</button>
        <button
          className="button primary"
          type="button"
          onClick={onExport}
          disabled={loading || !validation?.ready_for_ac}
        >
          Export for AC
        </button>
      </div>
    </header>
  );
}
