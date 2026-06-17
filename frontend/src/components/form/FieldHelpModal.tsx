import type { FormField } from "../../api/types";

type Props = {
  field?: FormField;
  onClose: () => void;
};

export function FieldHelpModal({ field, onClose }: Props) {
  if (!field) return null;
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="field-help-title" onClick={(event) => event.stopPropagation()}>
        <div className="card-header">
          <h2 id="field-help-title">{field.displayName}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close help">x</button>
        </div>
        <p>{field.help}</p>
        <dl className="signal-list compact">
          <div><dt>Status</dt><dd>{field.status}</dd></div>
          <div><dt>Source</dt><dd>{field.source}</dd></div>
        </dl>
      </div>
    </div>
  );
}
