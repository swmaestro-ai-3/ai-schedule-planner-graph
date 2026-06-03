import { describe, expect, it } from "vitest";
import { aiStatusButtonLabel } from "../../shared/components/AppShell";
import { mockPlannerApi } from "./api/plannerApi";
import { agentBusyCopy, agentPreviewItems, agentProposalSummary } from "./components/AgentChat";
import { plannerSteps } from "./data/plannerSteps";
import { calendarBlocks, weekDateLabels } from "./lib/calendar";
import type { ScheduleItem } from "./types/planner";

describe("planner frontend contracts", () => {
  it("keeps the one-purpose workflow order", () => {
    expect(plannerSteps.map((step) => step.label)).toEqual([
      "시작",
      "입력",
      "제안",
      "완료",
    ]);
  });

  it("renders a fixed monday-to-sunday week", () => {
    expect(weekDateLabels("2026-06-01")).toEqual([
      "06/01 월",
      "06/02 화",
      "06/03 수",
      "06/04 목",
      "06/05 금",
      "06/06 토",
      "06/07 일",
    ]);
  });

  it("maps schedule items to calendar block positions", () => {
    const items: ScheduleItem[] = [
      {
        id: "task-1",
        type: "task",
        title: "기획서",
        dayIndex: 2,
        start: "12:00",
        end: "14:00",
        durationMinutes: 120,
        note: "집중",
      },
    ];

    expect(calendarBlocks(items, "09:00", "21:00")).toEqual([
      {
        id: "task-1",
        dayIndex: 2,
        title: "기획서",
        time: "12:00 - 14:00",
        type: "task",
        topPercent: 25,
        heightPercent: 16.666666666666664,
        note: "집중",
      },
    ]);
  });

  it("creates recurring reflection tasks from natural language", async () => {
    const draft = await mockPlannerApi.createPlan({
      mode: "natural",
      text: "매일 오후 11시에 하루 회고 일정으로 1시간 넣어줘",
      bufferRatio: 15,
    });

    expect(draft.items.filter((item) => item.title === "하루 회고")).toHaveLength(7);
    expect(draft.items.some((item) => item.dayIndex === 6 && item.start === "23:00")).toBe(true);
  });

  it("moves a snoozed task during replan", async () => {
    const draft = await mockPlannerApi.createPlan({
      mode: "structured",
      bufferRatio: 15,
      fixedEvents: [],
      tasks: [],
    });
    const before = draft.items.find((item) => item.id === "task-plan");
    const next = await mockPlannerApi.replan(draft, {
      reason: "기획서를 하루 뒤로",
      snoozeTaskId: "task-plan",
      snoozeDays: 1,
    });
    const after = next.items.find((item) => item.id === "task-plan");

    expect(before?.dayIndex).toBe(0);
    expect(after?.dayIndex).toBe(1);
    expect(next.replanCount).toBe(1);
  });

  it("uses explicit agent progress copy for create and replan states", () => {
    expect(agentBusyCopy(false)).toEqual({
      title: "일정안을 쓰는 중",
      detail: "요청을 구조화하고 초안으로 보여줄 캘린더 배치를 준비하고 있습니다.",
    });
    expect(agentBusyCopy(true)).toEqual({
      title: "수정안을 쓰는 중",
      detail: "현재 제안과 피드백을 비교해서 반영 전 수정안을 준비하고 있습니다.",
    });
  });

  it("summarizes an agent proposal before it is committed to the calendar", async () => {
    const draft = await mockPlannerApi.createPlan({
      mode: "structured",
      bufferRatio: 15,
      fixedEvents: [],
      tasks: [],
    });

    expect(agentProposalSummary(draft)).toBe("고정 일정 1개, 작업 3개를 배치한 초안입니다.");
    expect(agentPreviewItems(draft, 2)).toEqual([
      "월 09:00-10:00 팀 미팅",
      "월 10:30-12:30 기획서 작성",
    ]);
  });

  it("labels the disconnected AI status pill as a connection action", () => {
    expect(aiStatusButtonLabel(false)).toBe("AI 미연결, 클릭해서 연결");
    expect(aiStatusButtonLabel(false, true)).toBe("AI 연결 확인 중");
    expect(aiStatusButtonLabel(true)).toBe("AI 연결됨");
  });
});
