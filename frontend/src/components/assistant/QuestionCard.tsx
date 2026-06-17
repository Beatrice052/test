import type { QuestionCard as QuestionCardType } from "../../api/types";

type Props = {
  card: QuestionCardType;
  onAnswer: (questionId: string, answer: string) => void;
};

export function QuestionCard({ card, onAnswer }: Props) {
  return (
    <article className="assistant-card question-card">
      <div className="card-header">
        <h3>{card.title}</h3>
        {card.priority && <span className="small-pill critical">{card.priority}</span>}
      </div>
      <p>{card.question}</p>
      {card.options && (
        <div className="option-stack">
          {card.options.map((option) => (
            <button key={option.value} className="button option" type="button" onClick={() => onAnswer(card.question_id, option.label)}>
              {option.label}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
