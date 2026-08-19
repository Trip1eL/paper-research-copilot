import { describe, expect, it } from "vitest";

import type { ResearchStreamEvent } from "./types";
import { eventLabel, formatDuration, mergeEvents } from "./utils";

const event = (sequence: number): ResearchStreamEvent => ({
  sequence,
  event_type: "agent_node",
  task_id: "task",
  created_at: "2026-08-18T00:00:00Z",
  status: "running",
  agent_event: {
    sequence,
    node: "retrieve_evidence",
    outcome: "retrieved",
    latency_ms: 1200,
    details: {},
  },
  message: null,
});

describe("research UI utilities", () => {
  it("deduplicates and orders SSE events", () => {
    const merged = mergeEvents([event(2)], event(1));
    expect(merged.map((item) => item.sequence)).toEqual([1, 2]);
    expect(mergeEvents(merged, event(2))).toBe(merged);
  });

  it("formats node labels and durations", () => {
    expect(eventLabel(event(1))).toBe("检索论文证据");
    expect(formatDuration(1200)).toBe("1.2 s");
    expect(formatDuration(61_000)).toBe("1m 1s");
  });
});
