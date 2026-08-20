import {
  CheckCircle2,
  FileSearch,
  FileText,
  ListTree,
  MessageSquareText,
  Quote,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";

import type { AgentResult, ResearchTaskView } from "../types";

type ResultTab = "report" | "evidence" | "plan";

interface ResearchResultProps {
  task: ResearchTaskView | null;
  active: boolean;
  clarifying: boolean;
  clarificationError: string | null;
  onClarify: (response: string) => void;
}

export function ResearchResult({
  task,
  active,
  clarifying,
  clarificationError,
  onClarify,
}: ResearchResultProps) {
  const [tab, setTab] = useState<ResultTab>("report");
  useEffect(() => setTab("report"), [task?.task_id]);

  const openEvidence = (citationId: string) => {
    setTab("evidence");
    window.setTimeout(() => {
      document
        .getElementById(`evidence-${citationId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  };

  return (
    <main className="panel result-panel" aria-label="研究结果">
      <div className="result-header">
        <div>
          <p className="eyebrow">RESEARCH OUTPUT</p>
          <h2>研究结果</h2>
        </div>
        {task?.result ? (
          <div className="result-tabs" role="tablist" aria-label="结果视图">
            <TabButton active={tab === "report"} onClick={() => setTab("report")}>
              <FileText size={15} aria-hidden="true" />报告
            </TabButton>
            <TabButton active={tab === "evidence"} onClick={() => setTab("evidence")}>
              <FileSearch size={15} aria-hidden="true" />证据
            </TabButton>
            <TabButton active={tab === "plan"} onClick={() => setTab("plan")}>
              <ListTree size={15} aria-hidden="true" />规划
            </TabButton>
          </div>
        ) : null}
      </div>

      {!task?.result ? (
        <EmptyResult active={active} failed={task?.status === "failed"} error={task?.error} />
      ) : tab === "report" ? (
        <ReportView
          result={task.result}
          task={task}
          clarifying={clarifying}
          clarificationError={clarificationError}
          onClarify={onClarify}
          onOpenEvidence={openEvidence}
        />
      ) : tab === "evidence" ? (
        <EvidenceView result={task.result} />
      ) : (
        <PlanView result={task.result} />
      )}
    </main>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      className={active ? "active" : ""}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function EmptyResult({
  active,
  failed,
  error,
}: {
  active: boolean;
  failed: boolean;
  error?: string | null;
}) {
  return (
    <div className={`quiet-state result-empty ${failed ? "failed" : ""}`}>
      {failed ? (
        <ShieldAlert size={30} aria-hidden="true" />
      ) : active ? (
        <FileSearch size={30} aria-hidden="true" />
      ) : (
        <FileText size={30} aria-hidden="true" />
      )}
      <strong>{failed ? "研究任务失败" : active ? "正在构建证据链" : "尚无研究报告"}</strong>
      {error ? <span>{error}</span> : null}
    </div>
  );
}

function ReportView({
  result,
  task,
  clarifying,
  clarificationError,
  onClarify,
  onOpenEvidence,
}: {
  result: AgentResult;
  task: ResearchTaskView;
  clarifying: boolean;
  clarificationError: string | null;
  onClarify: (response: string) => void;
  onOpenEvidence: (citationId: string) => void;
}) {
  if (result.clarification) {
    return (
      <ClarificationView
        result={result}
        clarifying={clarifying}
        error={clarificationError}
        onSubmit={onClarify}
      />
    );
  }
  const answered = result.answer.status === "answered";
  return (
    <div className="result-scroll report-view">
      {task.parent_task_id ? (
        <div className="clarification-provenance">
          <MessageSquareText size={15} aria-hidden="true" />
          <span>此结果来自补充后的研究任务</span>
          <code>{task.parent_task_id.slice(0, 8)}</code>
        </div>
      ) : null}
      <div className={`answer-status ${answered ? "answered" : "insufficient"}`}>
        {answered ? <CheckCircle2 size={17} aria-hidden="true" /> : <ShieldAlert size={17} />}
        <span>{answered ? "证据充分，已生成回答" : "证据不足"}</span>
        <span>{result.assessment.distinct_paper_count} papers</span>
      </div>
      <article className="answer-copy">
        <h3>{task.parent_question ?? result.question}</h3>
        {task.clarification_response ? (
          <p className="clarified-context">
            <span>用户补充</span>
            {task.clarification_response}
          </p>
        ) : null}
        <div className="answer-text">{result.answer.text}</div>
      </article>

      {result.verification ? (
        <ClaimVerificationView
          verification={result.verification}
          onOpenEvidence={onOpenEvidence}
        />
      ) : null}

      <section className="citation-section">
        <div className="section-title-row">
          <h3>引用来源</h3>
          <span>{result.answer.citations.length}</span>
        </div>
        {result.answer.citations.length === 0 ? (
          <p className="muted-copy">没有生成引用。</p>
        ) : (
          <div className="citation-list">
            {result.answer.citations.map((citation) => (
              <button
                type="button"
                className="citation-row"
                key={citation.citation_id}
                onClick={() => onOpenEvidence(citation.citation_id)}
              >
                <span className="citation-id">{citation.citation_id}</span>
                <span>
                  <strong>{citation.title}</strong>
                  <small>Page {citation.page_number}</small>
                </span>
                <Quote size={15} aria-hidden="true" />
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ClaimVerificationView({
  verification,
  onOpenEvidence,
}: {
  verification: NonNullable<AgentResult["verification"]>;
  onOpenEvidence: (citationId: string) => void;
}) {
  const revised = verification.status === "revised";
  const failed = verification.status === "error";
  const StatusIcon = failed ? ShieldAlert : revised ? RefreshCw : ShieldCheck;
  const statusLabel = failed
    ? "验证不可用"
    : revised
      ? "已移除或降级无充分支撑的内容"
      : verification.status === "skipped"
        ? "无需验证"
        : "关键陈述已通过证据核验";
  const verdictLabels = {
    supported: "支持",
    partially_supported: "部分支持",
    unsupported: "不支持",
  } as const;

  return (
    <section className={`verification-section ${verification.status}`}>
      <div className="section-title-row verification-title">
        <h3>Claim Verification</h3>
        <span>
          <StatusIcon size={15} aria-hidden="true" />
          {statusLabel}
        </span>
      </div>
      <p className="verification-rationale">{verification.rationale}</p>
      {verification.claims.length ? (
        <ol className="claim-list">
          {verification.claims.map((claim) => (
            <li key={claim.claim_id} className={`claim-row ${claim.verdict}`}>
              <div className="claim-heading">
                <span>{claim.claim_id}</span>
                <strong>{verdictLabels[claim.verdict]}</strong>
              </div>
              <p>{claim.claim}</p>
              <small>{claim.rationale}</small>
              {claim.citation_ids.length ? (
                <div className="claim-citations">
                  {claim.citation_ids.map((citationId) => (
                    <button
                      type="button"
                      key={citationId}
                      onClick={() => onOpenEvidence(citationId)}
                    >
                      {citationId}
                    </button>
                  ))}
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
      {verification.needs_human_review ? (
        <p className="verification-review">需要人工复核</p>
      ) : null}
      {verification.error ? <p className="verification-error">{verification.error}</p> : null}
    </section>
  );
}

function ClarificationView({
  result,
  clarifying,
  error,
  onSubmit,
}: {
  result: AgentResult;
  clarifying: boolean;
  error: string | null;
  onSubmit: (response: string) => void;
}) {
  const [response, setResponse] = useState("");
  const clarification = result.clarification;
  if (!clarification) return null;

  return (
    <div className="result-scroll clarification-view">
      <div className="clarification-heading">
        <MessageSquareText size={22} aria-hidden="true" />
        <div>
          <p>需要补充信息</p>
          <h3>{clarification.prompt}</h3>
        </div>
      </div>
      <div className="clarification-context">
        <span>原研究问题</span>
        <p>{result.question}</p>
      </div>
      <form
        className="clarification-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (response.trim().length >= 2) onSubmit(response);
        }}
      >
        <label htmlFor="clarification-response">你的补充</label>
        <textarea
          id="clarification-response"
          value={response}
          onChange={(event) => setResponse(event.target.value)}
          placeholder={clarification.required_information.join("；")}
          rows={5}
          maxLength={2000}
          disabled={clarifying}
        />
        <div className="clarification-actions">
          <span>{clarification.required_information.join(" · ")}</span>
          <button type="submit" disabled={clarifying || response.trim().length < 2}>
            <Send size={15} aria-hidden="true" />
            {clarifying ? "正在提交" : "继续研究"}
          </button>
        </div>
        {error ? <p className="clarification-error">{error}</p> : null}
      </form>
    </div>
  );
}

function EvidenceView({ result }: { result: AgentResult }) {
  return (
    <div className="result-scroll evidence-list">
      <div className="evidence-summary">
        <span>{result.evidence.length} chunks</span>
        <span>{result.assessment.distinct_paper_count} papers</span>
        <span>{result.assessment.sufficient ? "Evidence gate passed" : "Evidence insufficient"}</span>
      </div>
      {result.evidence.map((evidence) => (
        <article
          className="evidence-card"
          id={`evidence-${evidence.citation_id}`}
          key={evidence.citation_id}
        >
          <div className="evidence-card-header">
            <span className="citation-id">{evidence.citation_id}</span>
            <div>
              <h3>{evidence.chunk.title}</h3>
              <p>
                Page {evidence.chunk.page_number}
                {evidence.chunk.section_title ? ` · ${evidence.chunk.section_title}` : ""}
              </p>
            </div>
            <span className="score">{evidence.score.toFixed(3)}</span>
          </div>
          <p className="evidence-text">{evidence.chunk.text}</p>
        </article>
      ))}
    </div>
  );
}

function PlanView({ result }: { result: AgentResult }) {
  return (
    <div className="result-scroll plan-view">
      <div className="plan-overview">
        <span className="route-label">
          {result.plan.question_type === "cross_paper" ? "Cross-paper" : "Single-paper"}
        </span>
        <span>Revision {result.plan.revision}</span>
      </div>
      <section className="rationale-block">
        <h3>规划依据</h3>
        <p>{result.plan.rationale}</p>
      </section>
      <section className="plan-tasks">
        <h3>Research Tasks</h3>
        {result.plan.tasks.map((task) => (
          <article key={task.task_id}>
            <span>{task.task_id}</span>
            <div>
              <strong>{task.query}</strong>
              <p>{task.goal}</p>
            </div>
          </article>
        ))}
      </section>
      <section className="assessment-block">
        <h3>Evidence Assessment</h3>
        <p>{result.assessment.reason}</p>
      </section>
      {result.acquisition ? (
        <section className="assessment-block">
          <h3>Dynamic Acquisition</h3>
          <p>
            {result.acquisition.status} · {result.acquisition.indexed_count} indexed · {result.acquisition.query}
          </p>
          {result.acquisition.paper_titles.map((title) => <p key={title}>{title}</p>)}
          {result.acquisition.error ? <p>{result.acquisition.error}</p> : null}
        </section>
      ) : null}
    </div>
  );
}
