import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import {
  createResearchTask,
  getHealth,
  getResearchTask,
  resumeResearchTask,
  subscribeToResearchEvents,
} from "./api";
import { AgentTimeline } from "./components/AgentTimeline";
import { ResearchResult } from "./components/ResearchResult";
import { ResearchSidebar } from "./components/ResearchSidebar";
import { SystemHeader } from "./components/SystemHeader";
import type {
  HealthResponse,
  ResearchStreamEvent,
  ResearchTaskAccepted,
  ResearchTaskView,
  TaskStatus,
} from "./types";
import { mergeEvents } from "./utils";

type ConnectionState = "idle" | "sse" | "polling" | "closed";

export default function App() {
  const [question, setQuestion] = useState("");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [taskMeta, setTaskMeta] = useState<ResearchTaskAccepted | null>(null);
  const [task, setTask] = useState<ResearchTaskView | null>(null);
  const [events, setEvents] = useState<ResearchStreamEvent[]>([]);
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pollingRef = useRef<number | null>(null);

  const loadHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      setHealth(await getHealth());
    } catch (healthError) {
      setHealth(null);
      setError(healthError instanceof Error ? healthError.message : "无法检查系统状态");
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHealth();
    const interval = window.setInterval(() => void loadHealth(), 30_000);
    return () => window.clearInterval(interval);
  }, [loadHealth]);

  const stopConnections = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    if (pollingRef.current !== null) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  useEffect(() => stopConnections, [stopConnections]);

  const loadTask = useCallback(
    async (taskUrl: string): Promise<ResearchTaskView> => {
      const snapshot = await getResearchTask(taskUrl);
      setTask(snapshot);
      setStatus(snapshot.status);
      if (
        snapshot.status === "interrupted" ||
        snapshot.status === "succeeded" ||
        snapshot.status === "failed"
      ) {
        stopConnections();
        setConnection("closed");
      }
      return snapshot;
    },
    [stopConnections],
  );

  const startPolling = useCallback(
    (taskUrl: string) => {
      if (pollingRef.current !== null) return;
      setConnection("polling");
      const poll = async () => {
        try {
          await loadTask(taskUrl);
        } catch (pollError) {
          setError(pollError instanceof Error ? pollError.message : "任务状态查询失败");
        }
      };
      void poll();
      pollingRef.current = window.setInterval(() => void poll(), 2000);
    },
    [loadTask],
  );

  const connectEvents = useCallback(
    (accepted: ResearchTaskAccepted, after = 0) => {
      let terminalReached = false;
      setConnection("sse");
      const source = subscribeToResearchEvents(
        accepted.events_url,
        (incoming) => {
          setEvents((current) => mergeEvents(current, incoming));
          setStatus(incoming.status);
          if (
            incoming.event_type === "task_interrupted" ||
            incoming.event_type === "task_succeeded" ||
            incoming.event_type === "task_failed"
          ) {
            terminalReached = true;
            source.close();
            eventSourceRef.current = null;
            void loadTask(accepted.task_url);
          }
        },
        () => {
          source.close();
          eventSourceRef.current = null;
          if (!terminalReached) startPolling(accepted.task_url);
        },
        after,
      );
      eventSourceRef.current = source;
    },
    [loadTask, startPolling],
  );

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (question.trim().length < 5) return;
    stopConnections();
    setSubmitting(true);
    setError(null);
    setTask(null);
    setTaskMeta(null);
    setEvents([]);
    try {
      const accepted = await createResearchTask(question);
      setTaskMeta(accepted);
      setStatus(accepted.status);
      connectEvents(accepted);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "研究任务提交失败");
      setStatus(null);
    } finally {
      setSubmitting(false);
    }
  };

  const resume = async () => {
    if (!task || task.status !== "interrupted") return;
    stopConnections();
    setResuming(true);
    setError(null);
    try {
      const accepted = await resumeResearchTask(`/api/v1/research/${task.task_id}`);
      setTaskMeta(accepted);
      setStatus(accepted.status);
      connectEvents(accepted, Math.max(0, ...events.map((item) => item.sequence)));
    } catch (resumeError) {
      setError(resumeError instanceof Error ? resumeError.message : "任务恢复失败");
    } finally {
      setResuming(false);
    }
  };

  const reset = () => {
    stopConnections();
    setQuestion("");
    setTaskMeta(null);
    setTask(null);
    setEvents([]);
    setStatus(null);
    setConnection("idle");
    setError(null);
  };

  const active = status === "queued" || status === "running";

  return (
    <div className="app-shell">
      <SystemHeader health={health} loading={healthLoading} onRefresh={() => void loadHealth()} />
      <div className="workspace">
        <ResearchSidebar
          question={question}
          onQuestionChange={setQuestion}
          onSubmit={(event) => void submit(event)}
          submitting={submitting}
          resuming={resuming}
          active={active}
          taskMeta={taskMeta}
          task={task}
          status={status}
          connection={connection}
          error={error ?? task?.error ?? null}
          onReset={reset}
          onResume={() => void resume()}
        />
        <AgentTimeline events={events} />
        <ResearchResult task={task} active={active} />
      </div>
    </div>
  );
}
