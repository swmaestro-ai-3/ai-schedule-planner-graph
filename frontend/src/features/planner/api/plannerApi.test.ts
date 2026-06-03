import { describe, expect, it } from "vitest";
import { createHttpPlannerApi } from "./plannerApi";
import type { PlannerDraft } from "../types/planner";

const responseDraft: PlannerDraft = {
  weekStart: "2026-06-01",
  weekLabel: "2026.06.01 - 06.07",
  reason: "배치 완료",
  items: [],
  validation: [],
  replanCount: 0,
  backend: { planInput: { date: "2026-06-01" } },
};

describe("http planner api", () => {
  it("posts natural input to the backend plan endpoint", async () => {
    const calls: Array<{ url: string; body: unknown }> = [];
    const api = createHttpPlannerApi({
      baseUrl: "http://planner.test",
      fetcher: async (url, init) => {
        calls.push({ url: String(url), body: JSON.parse(String(init?.body)) });
        return new Response(JSON.stringify(responseDraft), { status: 200 });
      },
    });

    const result = await api.createPlan({
      mode: "natural",
      text: "매일 회고 넣어줘",
      bufferRatio: 15,
    });

    expect(result.reason).toBe("배치 완료");
    expect(calls).toEqual([
      {
        url: "http://planner.test/api/plans",
        body: { mode: "natural", text: "매일 회고 넣어줘", bufferRatio: 15 },
      },
    ]);
  });

  it("posts current draft and chat feedback to the replan endpoint", async () => {
    const calls: Array<{ url: string; body: unknown }> = [];
    const api = createHttpPlannerApi({
      baseUrl: "http://planner.test",
      fetcher: async (url, init) => {
        calls.push({ url: String(url), body: JSON.parse(String(init?.body)) });
        return new Response(JSON.stringify({ ...responseDraft, replanCount: 1 }), {
          status: 200,
        });
      },
    });

    const result = await api.replan(responseDraft, {
      reason: "기획서 하루 뒤로",
      snoozeTaskId: "task-1",
      snoozeDays: 1,
    });

    expect(result.replanCount).toBe(1);
    expect(calls[0]).toEqual({
      url: "http://planner.test/api/replans",
      body: {
        draft: responseDraft,
        reason: "기획서 하루 뒤로",
        snoozeTaskId: "task-1",
        snoozeDays: 1,
      },
    });
  });
});
