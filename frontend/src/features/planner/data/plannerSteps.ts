import type { PlannerStep } from "../types/planner";

export const plannerSteps: PlannerStep[] = [
  { id: "setup", index: 1, label: "시작" },
  { id: "input", index: 2, label: "입력" },
  { id: "proposal", index: 3, label: "제안" },
  { id: "done", index: 4, label: "완료" },
];
