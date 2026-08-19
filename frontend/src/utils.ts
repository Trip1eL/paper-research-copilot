import type { ResearchStreamEvent, TaskStatus } from "./types";

const EVENT_LABELS: Record<string, string> = {
  task_queued: "任务已进入队列",
  task_started: "开始研究",
  plan_research: "规划研究任务",
  retrieve_evidence: "检索论文证据",
  assess_evidence: "评估证据充分性",
  revise_queries: "修订检索查询",
  write_report: "生成研究报告",
  validate_citations: "验证引用",
  task_succeeded: "研究完成",
  task_failed: "研究失败",
};

export const statusLabel = (status: TaskStatus): string =>
  ({
    queued: "排队中",
    running: "研究中",
    succeeded: "已完成",
    failed: "失败",
  })[status];

export const eventLabel = (event: ResearchStreamEvent): string => {
  const key = event.agent_event?.node ?? event.event_type;
  return EVENT_LABELS[key] ?? key;
};

export const formatDuration = (milliseconds: number): string => {
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;
  if (milliseconds < 60_000) return `${(milliseconds / 1000).toFixed(1)} s`;
  const minutes = Math.floor(milliseconds / 60_000);
  const seconds = Math.round((milliseconds % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
};

export const formatClock = (value: string): string =>
  new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));

export const mergeEvents = (
  current: ResearchStreamEvent[],
  incoming: ResearchStreamEvent,
): ResearchStreamEvent[] => {
  if (current.some((event) => event.sequence === incoming.sequence)) return current;
  return [...current, incoming].sort((a, b) => a.sequence - b.sequence);
};

export const shortTaskId = (taskId: string): string => taskId.slice(0, 8);
