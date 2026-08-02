import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { workspaceApi } from "./api/client";
import type { AnalysisProgressEvent } from "./api/client";
import type { AnswerSnapshot } from "./api/generated";
import { Dashboard } from "./components/Dashboard";
import { AnalysisProgress } from "./components/AnalysisProgress";
import { EvidenceDrawer } from "./components/EvidenceDrawer";
import { SessionSidebar } from "./components/SessionSidebar";
import { formatTime } from "./lib/format";

function newClientTurnId(): string {
  return typeof crypto.randomUUID === "function"
    ? `client_${crypto.randomUUID()}`
    : `client_${Date.now().toString(36)}`;
}

function AnswerCard({ answer, onEvidence }: { answer: AnswerSnapshot; onEvidence: (id: string) => void }) {
  const question = answer.analysis_plan?.analysis_goal ?? "继续分析";
  return (
    <article className="answer-card">
      <div className="question-row">
        <span className="question-avatar" aria-hidden="true">你</span>
        <div><span className="message-label">分析请求</span><p>{question}</p></div>
      </div>
      <div className="answer-heading">
        <div>
          <span className="answer-status">{answer.status}</span>
          <span>{formatTime(answer.created_at)}</span>
        </div>
        {answer.evidence_package === undefined || answer.evidence_package === null ? null : (
          <button className="evidence-button" type="button" onClick={() => onEvidence(answer.object_id)}>
            <span aria-hidden="true">◎</span> 查看证据
          </button>
        )}
      </div>
      <Dashboard answer={answer} />
    </article>
  );
}

export function App() {
  const queryClient = useQueryClient();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [evidenceAnswerId, setEvidenceAnswerId] = useState<string | null>(null);
  const [progressEvents, setProgressEvents] = useState<AnalysisProgressEvent[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const requestController = useRef<AbortController | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["sessions"],
    queryFn: ({ signal }) => workspaceApi.listSessions(signal),
  });
  const runtimeQuery = useQuery({
    queryKey: ["runtime-health"],
    queryFn: ({ signal }) => workspaceApi.getRuntimeHealth(signal),
    staleTime: 30_000,
  });
  const sessions = sessionsQuery.data ?? [];
  const currentSessionId = activeSessionId ?? sessions[0]?.object_id ?? null;

  const detailQuery = useQuery({
    queryKey: ["session", currentSessionId],
    queryFn: ({ signal }) => workspaceApi.getSession(currentSessionId ?? "", signal),
    enabled: currentSessionId !== null,
  });

  const createMutation = useMutation({
    mutationFn: () => workspaceApi.createSession({ title: "New analysis" }),
    onSuccess: async (session) => {
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setActiveSessionId(session.object_id);
      setDraft("");
    },
  });

  const archiveMutation = useMutation({
    mutationFn: (sessionId: string) => workspaceApi.archiveSession(sessionId),
    onSuccess: async (_, archivedId) => {
      if (currentSessionId === archivedId) setActiveSessionId(null);
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  const chatMutation = useMutation({
    mutationFn: ({ sessionId, message, signal }: { sessionId: string; message: string; signal: AbortSignal }) =>
      workspaceApi.chatStream(
        { session_id: sessionId, message, client_turn_id: newClientTurnId() },
        (event) => setProgressEvents((current) => [...current, event]),
        signal,
      ),
    onSuccess: async (result) => {
      setDraft("");
      setActiveSessionId(result.session_id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sessions"] }),
        queryClient.invalidateQueries({ queryKey: ["session", result.session_id] }),
      ]);
    },
    onSettled: () => {
      requestController.current = null;
      setProgressEvents([]);
      setPendingQuestion("");
    },
  });

  function submitQuestion() {
    const message = draft.trim();
    if (message.length === 0 || currentSessionId === null || chatMutation.isPending) return;
    const controller = new AbortController();
    requestController.current = controller;
    setProgressEvents([]);
    setPendingQuestion(message);
    chatMutation.mutate({ sessionId: currentSessionId, message, signal: controller.signal });
  }

  function cancelQuestion() {
    requestController.current?.abort();
    chatMutation.reset();
    requestController.current = null;
    setProgressEvents([]);
    setPendingQuestion("");
  }

  const activeSession = detailQuery.data?.session;
  const answers = detailQuery.data?.answers ?? [];
  const busy = createMutation.isPending || archiveMutation.isPending;

  return (
    <div className="workspace-shell">
      <SessionSidebar
        sessions={sessions}
        activeId={currentSessionId}
        busy={busy}
        onSelect={setActiveSessionId}
        onCreate={() => createMutation.mutate()}
        onArchive={(id) => archiveMutation.mutate(id)}
        runtimeProfile={runtimeQuery.data?.profile}
        llmMode={runtimeQuery.data?.llm_mode}
      />
      <main className="workspace-main">
        <header className="workspace-header">
          <div>
            <span className="header-kicker">Session Workspace</span>
            <h1>{activeSession?.title ?? "OpenSearch ChatBI"}</h1>
          </div>
          <div className="runtime-status">
            <span />
            {runtimeQuery.data === undefined
              ? "正在检测运行适配器"
              : `${runtimeQuery.data.llm_mode ?? "未知 LLM"} · ${runtimeQuery.data.gateway_mode ?? "未知 Gateway"}`}
          </div>
        </header>

        <div className="timeline" aria-live="polite">
          {sessionsQuery.isPending || detailQuery.isPending ? (
            <div className="loading-panel"><span className="spinner" />正在恢复分析现场…</div>
          ) : null}
          {sessionsQuery.isError || detailQuery.isError ? (
            <div className="error-panel">工作区暂时无法读取。请确认 API 服务已启动后重试。</div>
          ) : null}
          {!sessionsQuery.isPending && currentSessionId === null ? (
            <section className="welcome-panel">
              <div className="welcome-orbit" aria-hidden="true"><span>BI</span></div>
              <span className="header-kicker">Mock-first · Adapter-based</span>
              <h2>从一个可验证的问题开始</h2>
              <p>每次分析都会保留指标口径、数据质量记录和行级证据。Mock 模式无需真实凭证。</p>
              <button className="primary-button" type="button" onClick={() => createMutation.mutate()}>新建分析会话</button>
            </section>
          ) : null}
          {currentSessionId !== null && !detailQuery.isPending && answers.length === 0 ? (
            <section className="session-empty">
              <span className="header-kicker">Ready</span>
              <h2>这是一张干净的分析画布</h2>
              <p>试试：“按服务查看最近 24 小时的消息量和失败率”。</p>
            </section>
          ) : null}
          {answers.map((answer) => <AnswerCard key={answer.object_id} answer={answer} onEvidence={setEvidenceAnswerId} />)}
          {chatMutation.isPending ? (
            <AnalysisProgress question={pendingQuestion} events={progressEvents} />
          ) : null}
          {chatMutation.isError ? (
            <div className="error-panel">本次请求未完成：{chatMutation.error.message}</div>
          ) : null}
        </div>

        <footer className="composer-zone">
          <div className="composer">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submitQuestion();
                }
              }}
              placeholder={currentSessionId === null ? "先新建一个分析会话" : "输入分析问题，Enter 发送，Shift + Enter 换行"}
              aria-label="分析问题"
              disabled={currentSessionId === null || chatMutation.isPending}
              rows={2}
            />
            {chatMutation.isPending ? (
              <button className="cancel-button" type="button" onClick={cancelQuestion}>取消</button>
            ) : (
              <button className="send-button" type="button" onClick={submitQuestion} disabled={draft.trim().length === 0 || currentSessionId === null} aria-label="发送分析问题">↑</button>
            )}
          </div>
          <p>回答由受控语义包与确定性 Analytics 生成，请结合证据确认业务决策。</p>
        </footer>
      </main>
      <EvidenceDrawer key={evidenceAnswerId ?? "closed"} answerId={evidenceAnswerId} onClose={() => setEvidenceAnswerId(null)} />
    </div>
  );
}
