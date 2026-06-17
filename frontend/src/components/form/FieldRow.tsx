import { useState } from "react";
import type { FormField } from "../../api/types";
import { StatusPill } from "./StatusPill";

type Props = {
  field: FormField;
  onHelp: (field: FormField) => void;
  onUpdate: (fieldName: string, value: string) => void;
};

export function FieldRow({ field, onHelp, onUpdate }: Props) {
  const [draft, setDraft] = useState(field.value);
  const editable = field.status === "Missing Required" || field.status === "Needs Confirmation" || field.status === "Optional";

  return (
    <div className="field-row">
      <div className="field-main">
        <button className="help-button" type="button" onClick={() => onHelp(field)} aria-label={`Explain ${field.displayName}`}>?</button>
        <div>
          <label htmlFor={field.name}>{field.displayName}</label>
          <span className="source-label">{field.source}</span>
        </div>
      </div>
      <div className="field-value">
        {editable ? (
          <input
            id={field.name}
            value={draft}
            placeholder="Add value"
            onChange={(event) => setDraft(event.target.value)}
            onBlur={() => onUpdate(field.name, draft)}
          />
        ) : (
          <span>{field.value || "Not set"}</span>
        )}
      </div>
      <StatusPill status={field.status} />
      <button className="button tiny" type="button" onClick={() => onUpdate(field.name, draft || field.value)}>
        {field.status === "Confirmed" ? "Update" : "Confirm"}
      </button>
    </div>
  );
}
