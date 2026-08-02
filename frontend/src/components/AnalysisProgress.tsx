import type {
  AnalysisProgressEvent,
  AnalysisProgressStage,
} from "../api/client";

const stageOrder: AnalysisProgressStage[] = [
  "request",
  "guardrails",
  "context",
  "intent",
  "query_plan",
  "dsl",
  "search",
  "analytics",
  "dashboard",
  "complete",
];

export function AnalysisProgress({
  question,
  events,
}: {
  question: string;
  events: AnalysisProgressEvent[];
}) {
  const latestByStage = new Map<AnalysisProgressStage, AnalysisProgressEvent>();
  for (const event of events) latestByStage.set(event.stage, event);
  const visible = stageOrder.flatMap((stage) => {
    const event = latestByStage.get(stage);
    return event === undefined ? [] : [event];
  });
  const current = events.at(-1);

  return (
    <section className="analysis-progress" aria-label="分析进度" aria-live="polite">
      <div className="progress-question">
        <span className="question-avatar" aria-hidden="true">你</span>
        <div><span className="message-label">分析请求</span><p>{question}</p></div>
      </div>
      <div className="progress-panel">
        <header className="progress-header">
          <div>
            <span className="header-kicker">Live analysis</span>
            <h2>{current?.stage === "complete" ? "正在加载最终结果" : "正在分析"}</h2>
          </div>
          <span className="progress-live"><i />实时</span>
        </header>
        {current === undefined ? (
          <div className="progress-awaiting"><span className="spinner" />正在建立安全分析流…</div>
        ) : (
          <div className="progress-current">
            <span className={current.status === "running" ? "spinner" : "progress-check"}>
              {current.status === "completed" ? "✓" : null}
            </span>
            <div><strong>{current.title}</strong><p>{current.detail}</p></div>
          </div>
        )}
        <ol className="progress-steps">
          {visible.map((event) => (
            <li key={event.stage} className={event.status}>
              <span aria-hidden="true">{event.status === "completed" ? "✓" : ""}</span>
              <div><strong>{event.title}</strong><small>{event.detail}</small></div>
            </li>
          ))}
        </ol>
        <p className="progress-privacy">
          这里展示可审计执行阶段与已确认的结构化中间结果，不展示模型私有推理、提示词或原始 DSL。
        </p>
      </div>
    </section>
  );
}
