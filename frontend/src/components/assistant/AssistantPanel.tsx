import type { AssistantCard } from "../../api/types";
import type { ChatMessage } from "../../state/intakeStore";
import { AssistantCardRenderer } from "./AssistantCardRenderer";
import { AssistantInput } from "./AssistantInput";

type Props = {
  cards: AssistantCard[];
  messages: ChatMessage[];
  loading: boolean;
  onAnswer: (questionId: string, answer: string) => void;
  onApplyPreview: (previewId: string) => void;
};

export function AssistantPanel({ cards, messages, loading, onAnswer, onApplyPreview }: Props) {
  const latestQuestion = [...cards].reverse().find((card) => card.type === "question");

  return (
    <section className="assistant-panel">
      <div className="assistant-header">
        <div>
          <p className="eyebrow">Assistant Copilot</p>
          <h2>Guided intake</h2>
        </div>
        {loading && <span className="small-pill">Working</span>}
      </div>
      <div className="assistant-feed">
        {messages.map((message) => (
          <div key={message.id} className={`chat-bubble ${message.role}`}>{message.text}</div>
        ))}
        {cards.map((card, index) => (
          <AssistantCardRenderer
            key={`${card.type}-${index}`}
            card={card}
            onAnswer={onAnswer}
            onApplyPreview={onApplyPreview}
          />
        ))}
      </div>
      <AssistantInput latestQuestionId={latestQuestion?.type === "question" ? latestQuestion.question_id : undefined} onSend={onAnswer} />
    </section>
  );
}
