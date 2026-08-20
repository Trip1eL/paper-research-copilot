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

export interface AgentAcquisitionSummary {
  query: string;
  acquisition_id: string | null;
  status: "running" | "succeeded" | "partial" | "failed";
  candidate_count: number;
  selected_count: number;
  downloaded_count: number;
  indexed_count: number;
  asset_ids: string[];
  paper_titles: string[];
  error: string | null;
}

export interface QuestionScreening {
  decision: "clear" | "ambiguous";
  rule_id: string | null;
  reason: string;
}

export interface ClarificationRequest {
  rule_id: string;
  prompt: string;
  required_information: string[];
}

export interface ClaimAssessment {
  claim_id: string;
  claim: string;
  citation_ids: string[];
  verdict: "supported" | "partially_supported" | "unsupported";
  rationale: string;
}

export interface ClaimVerification {
  status: "passed" | "revised" | "skipped" | "error";
  claims: ClaimAssessment[];
  rationale: string;
  needs_human_review: boolean;
  model: string | null;
  prompt_version: string | null;
  latency_ms: number;
  attempts: number;
  error: string | null;
}

export interface AgentResult {
  question: string;
  screening: QuestionScreening | null;
  clarification: ClarificationRequest | null;
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
  acquisition_rounds: number;
  acquisition: AgentAcquisitionSummary | null;
  verification: ClaimVerification | null;
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
  parent_task_id: string | null;
  parent_question: string | null;
  clarification_response: string | null;
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
  dynamic_qdrant_collection: string;
  dynamic_acquisition_enabled: boolean;
  claim_verification_enabled: boolean;
  task_store: "memory" | "sqlite";
  checkpoint_ready: boolean;
  checkpoint_error: string | null;
  queued_tasks: number;
  running_tasks: number;
  completed_tasks: number;
}
