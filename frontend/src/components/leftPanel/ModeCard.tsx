import type { IntakeMode } from "../../api/types";

export function ModeCard({ mode }: { mode: IntakeMode }) {
  const edit = mode === "EDIT_REFERENCE";
  return (
    <section className="panel-card">
      <div className="card-header">
        <h2>{edit ? "Edit Reference" : "Create New"}</h2>
      </div>
      <p className="muted">
        {edit
          ? "Using RDP 004 as the base. I will only ask about conflicts, missing required fields, and fields that need confirmation."
          : "No historical values are inherited. I will guide you through required fields progressively."}
      </p>
    </section>
  );
}
