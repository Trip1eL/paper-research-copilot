import {
  BadgeCheck,
  CircleCheck,
  Clock3,
  Download,
  FileCheck2,
  FileText,
  LoaderCircle,
  RefreshCw,
  Route,
  Search,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import type { ComponentType } from "react";

import type { ResearchStreamEvent } from "../types";
import { eventLabel, formatClock, formatDuration } from "../utils";

const NODE_ICONS: Record<string, ComponentType<{ size?: number; strokeWidth?: number }>> = {
  task_queued: Clock3,
  task_started: LoaderCircle,
  task_interrupted: TriangleAlert,
  task_resumed: RefreshCw,
  plan_research: Route,
  retrieve_evidence: Search,
  assess_evidence: ShieldCheck,
  revise_queries: RefreshCw,
  acquire_evidence: Download,
  write_report: FileText,
  validate_citations: FileCheck2,
  task_succeeded: CircleCheck,
  task_failed: TriangleAlert,
};

const DETAIL_LABELS: Record<string, string> = {
  question_type: "Route",
  task_count: "Tasks",
  strategy: "Strategy",
  evidence_count: "Evidence",
  dynamic_evidence_count: "Dynamic",
  distinct_papers: "Papers",
  retry_recommended: "Retry",
  citation_count: "Citations",
  planner_attempts: "Attempts",
  answer_attempts: "Attempts",
  candidates: "Candidates",
  selected: "Selected",
  downloaded: "Downloaded",
  indexed: "Indexed",
};

const visibleDetails = (event: ResearchStreamEvent): [string, string | number | boolean][] => {
  if (!event.agent_event) return [];
  return Object.entries(event.agent_event.details).filter(([key]) => key in DETAIL_LABELS);
};

export function AgentTimeline({ events }: { events: ResearchStreamEvent[] }) {
  return (
    <section className="panel timeline-panel" aria-label="Agent 执行过程">
      <div className="panel-heading timeline-heading">
        <div>
          <p className="eyebrow">AGENT TRACE</p>
          <h2>执行过程</h2>
        </div>
        <span className="event-count">{events.length} events</span>
      </div>

      {events.length === 0 ? (
        <div className="quiet-state timeline-empty">
          <Route size={24} aria-hidden="true" />
          <span>等待 Agent Trace</span>
        </div>
      ) : (
        <ol className="timeline-list">
          {events.map((event, index) => {
            const node = event.agent_event?.node ?? event.event_type;
            const Icon = NODE_ICONS[node] ?? BadgeCheck;
            const details = visibleDetails(event);
            const failed =
              event.event_type === "task_failed" || event.event_type === "task_interrupted";
            const complete = event.status === "succeeded" || event.event_type === "task_succeeded";
            return (
              <li
                key={event.sequence}
                className={`timeline-item ${failed ? "failed" : complete ? "complete" : ""}`}
              >
                <div className="timeline-rail" aria-hidden="true">
                  <span className="timeline-icon">
                    <Icon size={16} strokeWidth={2} />
                  </span>
                  {index < events.length - 1 ? <span className="timeline-line" /> : null}
                </div>
                <div className="timeline-content">
                  <div className="timeline-title-row">
                    <strong>{eventLabel(event)}</strong>
                    <time>{formatClock(event.created_at)}</time>
                  </div>
                  <div className="timeline-outcome">
                    <span>{event.agent_event?.outcome ?? event.status}</span>
                    {event.agent_event ? (
                      <span>{formatDuration(event.agent_event.latency_ms)}</span>
                    ) : null}
                  </div>
                  {details.length ? (
                    <div className="timeline-details">
                      {details.map(([key, value]) => (
                        <span key={key}>
                          {DETAIL_LABELS[key]}: {String(value)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {failed && event.message ? <p className="timeline-error">{event.message}</p> : null}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
