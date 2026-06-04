export type PlannerStepId = "setup" | "input" | "proposal" | "done";

export type ScheduleItemType = "fixed" | "task";

export type InputMode = "natural" | "structured";

export interface PlannerStep {
  id: PlannerStepId;
  index: number;
  label: string;
}

export interface ScheduleItem {
  id: string;
  type: ScheduleItemType;
  title: string;
  dayIndex: number;
  start: string;
  end: string;
  durationMinutes: number;
  note: string;
  priority?: "High" | "Medium" | "Low";
}

export interface ValidationRow {
  label: string;
  status: "ok" | "warning";
  detail: string;
}

export interface PlannerDraft {
  weekStart: string;
  weekLabel: string;
  reason: string;
  items: ScheduleItem[];
  validation: ValidationRow[];
  replanCount: number;
  lastFeedback?: string;
  backend?: {
    planInput?: unknown;
  };
}

export interface PlannerMutationResult {
  draft: PlannerDraft | null;
  agentMessage?: string;
}

export interface NaturalPlanInput {
  mode: "natural";
  text: string;
  bufferRatio: number;
  conversation?: AgentConversationMessage[];
}

export interface StructuredPlanInput {
  mode: "structured";
  bufferRatio: number;
  fixedEvents: string[];
  tasks: string[];
}

export type CreatePlanInput = NaturalPlanInput | StructuredPlanInput;

export interface AgentConversationMessage {
  role: "agent" | "user";
  text: string;
}

export interface ReplanInput {
  reason: string;
  snoozeTaskId?: string;
  snoozeDays: number;
  conversation?: AgentConversationMessage[];
}
