import {
  CheckCircle2,
  FileSearch,
  FileText,
  ListTree,
  Quote,
  ShieldAlert,
} from "lucide-react";
import { useEffect, useState } from "react";

import type { AgentResult, ResearchTaskView } from "../types";

type ResultTab = "report" | "evidence" | "plan";

interface ResearchResultProps {
  task: ResearchTaskView | null;
  active: boolean;
}

export function ResearchResult({ task, active }: ResearchResultProps) {
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
        <ReportView result={task.result} onOpenEvidence={openEvidence} />
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
  onOpenEvidence,
}: {
  result: AgentResult;
  onOpenEvidence: (citationId: string) => void;
}) {
  const answered = result.answer.status === "answered";
  return (
    <div className="result-scroll report-view">
      <div className={`answer-status ${answered ? "answered" : "insufficient"}`}>
        {answered ? <CheckCircle2 size={17} aria-hidden="true" /> : <ShieldAlert size={17} />}
        <span>{answered ? "证据充分，已生成回答" : "证据不足"}</span>
        <span>{result.assessment.distinct_paper_count} papers</span>
      </div>
      <article className="answer-copy">
        <h3>{result.question}</h3>
        <div className="answer-text">{result.answer.text}</div>
      </article>

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
