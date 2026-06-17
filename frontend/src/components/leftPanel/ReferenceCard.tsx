import type { IntakeMode, ReferenceUseCase } from "../../api/types";

type Props = {
  mode: IntakeMode;
  reference?: ReferenceUseCase;
};

export function ReferenceCard({ mode, reference }: Props) {
  if (mode === "CREATE_NEW") {
    return (
      <section className="panel-card">
        <div className="card-header"><h2>Reference</h2></div>
        <p className="empty-state">No reference selected.</p>
      </section>
    );
  }

  return (
    <section className="panel-card">
      <div className="card-header">
        <h2>Reference</h2>
        <span className="small-pill attention">{reference?.status ?? "Loaded"}</span>
      </div>
      <dl className="signal-list">
        <div><dt>Reference</dt><dd>{reference?.name}</dd></div>
        <div><dt>Use Case ID</dt><dd>{reference?.id}</dd></div>
        <div><dt>Source System</dt><dd>{reference?.source_system}</dd></div>
        <div><dt>Reference Channel</dt><dd>{reference?.channel}</dd></div>
      </dl>
      <div className="reference-stats">
        <div><strong>1</strong><span>Changed from reference</span></div>
        <div><strong>2</strong><span>Needs confirmation</span></div>
        <div><strong>1</strong><span>Missing required</span></div>
      </div>
    </section>
  );
}
