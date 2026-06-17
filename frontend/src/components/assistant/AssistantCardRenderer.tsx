import type { AssistantCard } from "../../api/types";
import { ActionPreviewCard } from "./ActionPreviewCard";
import { FindingCard } from "./FindingCard";
import { QuestionCard } from "./QuestionCard";
import { SummaryCard } from "./SummaryCard";

type Props = {
  card: AssistantCard;
  onAnswer: (questionId: string, answer: string) => void;
  onApplyPreview: (previewId: string) => void;
};

export function AssistantCardRenderer({ card, onAnswer, onApplyPreview }: Props) {
  if (card.type === "summary") return <SummaryCard card={card} />;
  if (card.type === "finding") return <FindingCard card={card} />;
  if (card.type === "question") return <QuestionCard card={card} onAnswer={onAnswer} />;
  if (card.type === "action_preview") return <ActionPreviewCard card={card} onApply={onApplyPreview} />;
  if (card.type === "validation") {
    return (
      <article className="assistant-card">
        <h3>{card.title}</h3>
        <p>{card.body}</p>
      </article>
    );
  }
  return (
    <article className="assistant-card">
      <h3>{card.title}</h3>
      <p>{card.body}</p>
    </article>
  );
}
