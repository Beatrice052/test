import type { ActionPreviewCard as ActionPreviewCardType } from "../../api/types";

type Props = {
  card: ActionPreviewCardType;
  onApply: (previewId: string) => void;
};

export function ActionPreviewCard({ card, onApply }: Props) {
  return (
    <article className="assistant-card action-preview-card">
      <h3>{card.title}</h3>
      <p>The following update will be applied after confirmation:</p>
      <div className="preview-list">
        {card.action_preview.user_facing_updates.map((update) => (
          <div key={update.field_name} className="preview-row">
            <strong>{update.display_name}</strong>
            <span>{update.old_value} -&gt; {update.new_value}</span>
            <small>{update.reason}</small>
          </div>
        ))}
      </div>
      {card.action_preview.follow_up_summary && <p className="muted">{card.action_preview.follow_up_summary}</p>}
      <div className="preview-actions">
        <button className="button primary" type="button" onClick={() => onApply(card.action_preview.preview_id)}>
          Confirm and apply
        </button>
        <button className="button secondary" type="button">Edit before applying</button>
      </div>
    </article>
  );
}
