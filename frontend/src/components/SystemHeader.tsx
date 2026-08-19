import { BookOpenText, Database, RefreshCw } from "lucide-react";

import type { HealthResponse } from "../types";

interface SystemHeaderProps {
  health: HealthResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export function SystemHeader({ health, loading, onRefresh }: SystemHeaderProps) {
  const ready = health?.status === "ok";
  return (
    <header className="topbar">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">
          <BookOpenText size={21} strokeWidth={1.8} />
        </span>
        <div>
          <div className="brand-name">Paper Research Copilot</div>
          <div className="brand-subtitle">Agentic RAG Research Workspace</div>
        </div>
      </div>

      <div className="system-status">
        <div className="corpus-label">
          <Database size={15} aria-hidden="true" />
          <span>Corpus v{health?.corpus_version ?? 3}</span>
        </div>
        <button
          type="button"
          className="health-button"
          onClick={onRefresh}
          title="刷新系统状态"
          aria-label="刷新系统状态"
        >
          <span className={`status-dot ${ready ? "ready" : "degraded"}`} />
          <span>{loading ? "检查中" : ready ? "系统就绪" : "系统异常"}</span>
          <RefreshCw size={14} className={loading ? "spin" : ""} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
