import type { FindingCard as FindingCardType } from "../../api/types";

export function FindingCard({ card }: { card: FindingCardType }) {
  return (
    <article className="assistant-card finding-card">
      <span className="small-pill attention">Finding</span>
      <h3>{card.title}</h3>
      <p>{card.body}</p>
    </article>
  );
}
