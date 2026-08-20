import type {
  HealthResponse,
  ResearchStreamEvent,
  ResearchTaskAccepted,
  ResearchTaskView,
} from "./types";

const parseResponse = async <T>(response: Response): Promise<T> => {
  if (response.ok) return (await response.json()) as T;
  let message = `请求失败（HTTP ${response.status}）`;
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) message = payload.detail;
  } catch {
    // Keep the HTTP fallback when the response is not JSON.
  }
  throw new Error(message);
};

export const getHealth = async (): Promise<HealthResponse> =>
  parseResponse<HealthResponse>(await fetch("/health"));

export const createResearchTask = async (
  question: string,
): Promise<ResearchTaskAccepted> =>
  parseResponse<ResearchTaskAccepted>(
    await fetch("/api/v1/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  );

export const getResearchTask = async (taskUrl: string): Promise<ResearchTaskView> =>
  parseResponse<ResearchTaskView>(await fetch(taskUrl));

export const resumeResearchTask = async (taskUrl: string): Promise<ResearchTaskAccepted> =>
  parseResponse<ResearchTaskAccepted>(
    await fetch(`${taskUrl}/resume`, { method: "POST" }),
  );

export const clarifyResearchTask = async (
  taskUrl: string,
  response: string,
): Promise<ResearchTaskAccepted> =>
  parseResponse<ResearchTaskAccepted>(
    await fetch(`${taskUrl}/clarify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ response }),
    }),
  );

const EVENT_TYPES = [
  "task_queued",
  "task_started",
  "task_interrupted",
  "task_resumed",
  "agent_node",
  "task_succeeded",
  "task_failed",
] as const;

export const subscribeToResearchEvents = (
  eventsUrl: string,
  onEvent: (event: ResearchStreamEvent) => void,
  onConnectionError: () => void,
  after = 0,
): EventSource => {
  const separator = eventsUrl.includes("?") ? "&" : "?";
  const source = new EventSource(`${eventsUrl}${separator}after=${after}`);
  for (const eventType of EVENT_TYPES) {
    source.addEventListener(eventType, (message) => {
      onEvent(JSON.parse((message as MessageEvent<string>).data) as ResearchStreamEvent);
    });
  }
  source.onerror = onConnectionError;
  return source;
};
