import type { SessionContext } from "../api/generated";
import { formatTime } from "../lib/format";

type SessionSidebarProps = {
  sessions: Array<SessionContext>;
  activeId: string | null;
  busy: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onArchive: (id: string) => void;
  runtimeProfile?: string | undefined;
  llmMode?: string | undefined;
};

export function SessionSidebar({
  sessions,
  activeId,
  busy,
  onSelect,
  onCreate,
  onArchive,
  runtimeProfile,
  llmMode,
}: SessionSidebarProps) {
  const mockRuntime = ["rule_based", "fixture", "recorded"].includes(llmMode ?? "");
  return (
    <aside className="session-sidebar" aria-label="分析会话">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true"><span /></div>
        <div><strong>OpenSearch</strong><span>ChatBI · V6.1</span></div>
      </div>
      <button className="new-session" type="button" onClick={onCreate} disabled={busy}>
        <span aria-hidden="true">＋</span> 新建分析
      </button>
      <div className="session-label">最近会话</div>
      <nav className="session-list">
        {sessions.map((session) => (
          <div className={`session-row${session.object_id === activeId ? " active" : ""}`} key={session.object_id}>
            <button type="button" onClick={() => onSelect(session.object_id)} aria-current={session.object_id === activeId ? "page" : undefined}>
              <span className="session-title">{session.title}</span>
              <span className="session-time">{formatTime(session.updated_at)}</span>
            </button>
            <button className="archive-button" type="button" title="归档会话" aria-label={`归档 ${session.title}`} onClick={() => onArchive(session.object_id)}>×</button>
          </div>
        ))}
        {sessions.length === 0 ? <p className="sidebar-empty">还没有分析会话</p> : null}
      </nav>
      <div className="profile-chip">
        <span className="profile-avatar">{mockRuntime ? "M" : "T"}</span>
        <div>
          <strong>{mockRuntime ? "Mock Analyst" : "Trusted Analyst"}</strong>
          <span>{mockRuntime ? `本地 ${llmMode ?? "Mock"} 适配器` : `${runtimeProfile ?? "受信"}运行身份`}</span>
        </div>
      </div>
    </aside>
  );
}
