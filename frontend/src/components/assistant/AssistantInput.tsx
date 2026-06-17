import { useState } from "react";

type Props = {
  latestQuestionId?: string;
  onSend: (questionId: string, answer: string) => void;
};

export function AssistantInput({ latestQuestionId, onSend }: Props) {
  const [value, setValue] = useState("");
  const disabled = !latestQuestionId || !value.trim();

  return (
    <form
      className="assistant-input"
      onSubmit={(event) => {
        event.preventDefault();
        if (!latestQuestionId || !value.trim()) return;
        onSend(latestQuestionId, value.trim());
        setValue("");
      }}
    >
      <textarea
        value={value}
        rows={3}
        onChange={(event) => setValue(event.target.value)}
        placeholder={'Reply to the Assistant, for example: "Use Email only and sender name is HSBC Wealth."'}
      />
      <button className="button primary" type="submit" disabled={disabled}>Send</button>
    </form>
  );
}
