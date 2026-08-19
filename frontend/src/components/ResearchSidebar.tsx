import { Clock3, Play, RotateCcw, Waypoints } from "lucide-react";
import type { FormEvent } from "react";

import type { ResearchTaskAccepted, ResearchTaskView, TaskStatus } from "../types";
import { formatClock, shortTaskId, statusLabel } from "../utils";

const EXAMPLES = [
  "这些论文中，哪一种方法使用类似操作系统 paging 的机制管理有限上下文？",
  "比较一种把环境反馈写入跨回合记忆的方法，和另一种在单次生成中反复批评初稿的方法，它们分别迭代什么对象？",
  "ReAct 如何将推理轨迹与外部行动交错起来？",
];

interface ResearchSidebarProps {
  question: string;
  onQuestionChange: (question: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  submitting: boolean;
  active: boolean;
  taskMeta: ResearchTaskAccepted | null;
  task: ResearchTaskView | null;
  status: TaskStatus | null;
  connection: "idle" | "sse" | "polling" | "closed";
  error: string | null;
  onReset: () => void;
}

export function ResearchSidebar({
  question,
  onQuestionChange,
  onSubmit,
  submitting,
  active,
  taskMeta,
  task,
  status,
  connection,
  error,
  onReset,
}: ResearchSidebarProps) {
  const result = task?.result;
  return (
    <aside className="panel research-sidebar" aria-label="研究任务">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">RESEARCH QUERY</p>
          <h1>研究任务</h1>
        </div>
        {(taskMeta || task) && !active ? (
          <button
            type="button"
            className="icon-button"
            onClick={onReset}
            title="新建研究任务"
            aria-label="新建研究任务"
          >
            <RotateCcw size={17} aria-hidden="true" />
          </button>
        ) : null}
      </div>

      <form onSubmit={onSubmit} className="research-form">
        <label htmlFor="research-question">研究问题</label>
        <textarea
          id="research-question"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="输入需要从论文语料中研究的问题"
          minLength={5}
          maxLength={2000}
          rows={8}
          disabled={active}
          required
        />
        <div className="input-meta">
          <select
            aria-label="选择示例问题"
            defaultValue=""
            disabled={active}
            onChange={(event) => {
              if (event.target.value) onQuestionChange(event.target.value);
              event.target.value = "";
            }}
          >
            <option value="">选择示例问题</option>
            {EXAMPLES.map((example) => (
              <option key={example} value={example}>
                {example}
              </option>
            ))}
          </select>
          <span>{question.length}/2000</span>
        </div>
        <button
          className="primary-button"
          type="submit"
          disabled={active || submitting || question.trim().length < 5}
        >
          <Play size={17} fill="currentColor" aria-hidden="true" />
          <span>{active ? "研究进行中" : submitting ? "正在提交" : "开始研究"}</span>
        </button>
      </form>

      <div className="task-overview" aria-live="polite">
        <div className="section-title-row">
          <h2>任务状态</h2>
          {status ? <span className={`status-badge ${status}`}>{statusLabel(status)}</span> : null}
        </div>

        {!taskMeta && !task ? (
          <div className="quiet-state compact">
            <Waypoints size={20} aria-hidden="true" />
            <span>尚无研究任务</span>
          </div>
        ) : (
          <dl className="task-metadata">
            <div>
              <dt>Task ID</dt>
              <dd>{shortTaskId(task?.task_id ?? taskMeta?.task_id ?? "")}</dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd>{formatClock(task?.created_at ?? taskMeta?.created_at ?? "")}</dd>
            </div>
            <div>
              <dt>事件连接</dt>
              <dd>{connection === "sse" ? "SSE" : connection === "polling" ? "轮询" : "已结束"}</dd>
            </div>
          </dl>
        )}

        {error ? <div className="error-message">{error}</div> : null}
      </div>

      {result ? (
        <div className="result-metrics">
          <div>
            <span>Tasks</span>
            <strong>{result.plan.tasks.length}</strong>
          </div>
          <div>
            <span>Evidence</span>
            <strong>{result.evidence.length}</strong>
          </div>
          <div>
            <span>Citations</span>
            <strong>{result.answer.citations.length}</strong>
          </div>
          <div>
            <span>Retries</span>
            <strong>{result.retry_count}</strong>
          </div>
        </div>
      ) : null}

      <div className="runtime-note">
        <Clock3 size={15} aria-hidden="true" />
        <span>单任务串行执行</span>
      </div>
    </aside>
  );
}
