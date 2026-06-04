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

    expect(result.draft?.reason).toBe("배치 완료");
    expect(calls).toEqual([
      {
        url: "http://planner.test/api/plans",
        body: { mode: "natural", text: "매일 회고 넣어줘", bufferRatio: 15 },
      },
    ]);
  });

  it("normalizes message-only create responses from the backend", async () => {
    const api = createHttpPlannerApi({
      baseUrl: "http://planner.test",
      fetcher: async () =>
        new Response(
          JSON.stringify({
            agentMessage: "예: 월요일 15시에 운동 1시간처럼 말하면 됩니다.",
          }),
          { status: 200 },
        ),
    });

    const result = await api.createPlan({
      mode: "natural",
      text: "어떤 식으로 말하면 돼?",
      bufferRatio: 15,
    });

    expect(result).toEqual({
      draft: null,
      agentMessage: "예: 월요일 15시에 운동 1시간처럼 말하면 됩니다.",
    });
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
      conversation: [
        { role: "user", text: "기획서 작성 내일로 미뤄줘" },
        { role: "agent", text: "초안을 준비했습니다." },
        { role: "user", text: "그거 오후로 바꿔줘" },
      ],
    });

    expect(result.draft?.replanCount).toBe(1);
    expect(calls[0]).toEqual({
      url: "http://planner.test/api/replans",
      body: {
        draft: responseDraft,
        reason: "기획서 하루 뒤로",
        snoozeTaskId: "task-1",
        snoozeDays: 1,
        conversation: [
          { role: "user", text: "기획서 작성 내일로 미뤄줘" },
          { role: "agent", text: "초안을 준비했습니다." },
          { role: "user", text: "그거 오후로 바꿔줘" },
        ],
      },
    });
  });

  it("normalizes message-only replan responses from the backend", async () => {
    const api = createHttpPlannerApi({
      baseUrl: "http://planner.test",
      fetcher: async () =>
        new Response(
          JSON.stringify({
            agentMessage: "아니요. 현재 작업은 고정 일정과 겹치지 않습니다.",
          }),
          { status: 200 },
        ),
    });

    const result = await api.replan(responseDraft, {
      reason: "고정 일정을 침범했어?",
      snoozeDays: 1,
    });

    expect(result).toEqual({
      draft: null,
      agentMessage: "아니요. 현재 작업은 고정 일정과 겹치지 않습니다.",
    });
  });

  it("gets OpenAI OAuth status from the backend", async () => {
    const calls: Array<{ url: string; method: string }> = [];
    const api = createHttpPlannerApi({
      baseUrl: "http://planner.test",
      fetcher: async (url, init) => {
        calls.push({ url: String(url), method: init?.method ?? "GET" });
        return new Response(
          JSON.stringify({
            connected: true,
            message: "openai-oauth proxy is reachable.",
            models: ["gpt-5.1"],
            authFileExists: true,
          }),
          { status: 200 },
        );
      },
    });

    const status = await api.getOpenAIStatus();

    expect(status.connected).toBe(true);
    expect(status.models).toEqual(["gpt-5.1"]);
    expect(calls).toEqual([{ url: "http://planner.test/api/openai/status", method: "GET" }]);
  });

  it("posts to the OpenAI OAuth connect endpoint", async () => {
    const calls: Array<{ url: string; body: unknown }> = [];
    const api = createHttpPlannerApi({
      baseUrl: "http://planner.test",
      fetcher: async (url, init) => {
        calls.push({ url: String(url), body: JSON.parse(String(init?.body)) });
        return new Response(
          JSON.stringify({
            connected: false,
            action: "login_started",
            message: "OpenAI OAuth 로그인 페이지를 열었습니다. 로그인 후 다시 연결을 확인하세요.",
            pid: 1234,
          }),
          { status: 200 },
        );
      },
    });

    const result = await api.connectOpenAI();

    expect(result.action).toBe("login_started");
    expect(calls).toEqual([{ url: "http://planner.test/api/openai/connect", body: {} }]);
  });
});
