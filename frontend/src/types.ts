export type TaskStatus = "queued" | "running" | "interrupted" | "succeeded" | "failed";

export type EventType =
  | "task_queued"
  | "task_started"
  | "task_interrupted"
  | "task_resumed"
  | "agent_node"
  | "task_succeeded"
  | "task_failed";

export interface AgentEvent {
  sequence: number;
  node: string;
  outcome: string;
  latency_ms: number;
  details: Record<string, string | number | boolean>;
}

export interface ResearchStreamEvent {
  sequence: number;
  event_type: EventType;
  task_id: string;
  created_at: string;
  status: TaskStatus;
  agent_event: AgentEvent | null;
  message: string | null;
}

export interface ResearchTaskAccepted {
  task_id: string;
  status: TaskStatus;
  created_at: string;
  task_url: string;
  events_url: string;
}

export interface ResearchPlanTask {
  task_id: string;
  query: string;
  goal: string;
}

export interface ResearchPlan {
  question: string;
  question_type: "single_paper" | "cross_paper";
  rationale: string;
  tasks: ResearchPlanTask[];
  revision: number;
}

export interface PaperChunk {
  chunk_id: string;
  paper_id: string | null;
  title: string;
  source_path: string;
  page_number: number;
  section_title: string | null;
  text: string;
}

export interface RetrievedChunk {
  citation_id: string;
  score: number;
  chunk: PaperChunk;
}

export interface Citation {
  citation_id: string;
  chunk_id: string;
  paper_id: string | null;
  title: string;
  source_path: string;
  page_number: number;
  excerpt: string;
  retrieval_score: number;
}

export interface EvidenceAssessment {
  sufficient: boolean;
  reason: string;
  task_candidate_counts: Record<string, number>;
  task_selected_counts: Record<string, number>;
  missing_task_ids: string[];
  distinct_paper_count: number;
  retry_recommended: boolean;
}

export interface AgentResult {
  question: string;
  plan: ResearchPlan;
  evidence: RetrievedChunk[];
  assessment: EvidenceAssessment;
  answer: {
    question: string;
    text: string;
    citations: Citation[];
    status: "answered" | "insufficient_evidence";
  };
  retry_count: number;
  trace: AgentEvent[];
}

export interface ResearchTaskView {
  task_id: string;
  question: string;
  status: TaskStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  event_count: number;
  result: AgentResult | null;
  error: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  runtime_ready: boolean;
  runtime_error: string | null;
  corpus_version: number;
  qdrant_collection: string;
  task_store: "memory" | "sqlite";
  checkpoint_ready: boolean;
  checkpoint_error: string | null;
  queued_tasks: number;
  running_tasks: number;
  completed_tasks: number;
}
