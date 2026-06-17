import type { SummaryCard as SummaryCardType } from "../../api/types";

export function SummaryCard({ card }: { card: SummaryCardType }) {
  return (
    <article className="assistant-card summary-card">
      <h3>{card.title}</h3>
      <p>{card.body}</p>
    </article>
  );
}
