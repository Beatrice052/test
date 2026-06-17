import type { ExtractedSignals } from "../../api/types";

type Props = {
  requirement: string;
  extractedSignals: ExtractedSignals;
};

export function RequirementCard({ requirement, extractedSignals }: Props) {
  return (
    <section className="panel-card">
      <div className="card-header">
        <h2>Requirement</h2>
      </div>
      <p className="requirement-text">{requirement}</p>
      <dl className="signal-list">
        <div><dt>LOB</dt><dd>{extractedSignals.lob ?? "Not detected"}</dd></div>
        <div><dt>Channel</dt><dd>{extractedSignals.channel ?? "Not detected"}</dd></div>
        <div><dt>Trigger</dt><dd>{extractedSignals.trigger ?? "Not detected"}</dd></div>
        <div><dt>Audience</dt><dd>{extractedSignals.audience ?? "Not detected"}</dd></div>
      </dl>
    </section>
  );
}
